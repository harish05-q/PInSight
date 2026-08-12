"""Synthetic Data Generator (Phase 2 & 5).

Populates the database with healthy transactions and the 6 specific
failure classes defined in SRS §4.4. Also generates ground-truth
Incidents and EvalCases for Phase 5.
"""

import argparse
import asyncio
import random
import uuid
from collections.abc import Sequence
from decimal import Decimal

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db import engine
from app.models.eval import EvalCase
from app.models.incident import Incident
from app.models.merchant import Merchant
from app.services import transaction_service, webhook_service

log = structlog.get_logger()
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def ensure_merchants() -> Sequence[Merchant]:
    """Ensure we have some merchants to attach transactions to."""
    async with async_session_factory() as session:
        result = await session.execute(select(Merchant))
        merchants = result.scalars().all()
        if not merchants:
            log.info("Creating initial merchants...")
            merchants = [
                Merchant(id=uuid.uuid4(), name="Acme Corp"),
                Merchant(id=uuid.uuid4(), name="Globex Corporation"),
                Merchant(id=uuid.uuid4(), name="Soylent Corp"),
            ]
            session.add_all(merchants)
            await session.commit()
            result = await session.execute(select(Merchant))
            merchants = result.scalars().all()
    return merchants


async def create_eval_case(
    tx_id: uuid.UUID, desc: str, expected_cause: str, expected_evidence: list
):
    """Helper to create an incident and its ground-truth eval case."""
    async with async_session_factory() as session:
        incident = Incident(transaction_id=tx_id, description=desc, status="open")
        session.add(incident)
        await session.flush()

        eval_case = EvalCase(
            incident_id=incident.id,
            expected_root_cause=expected_cause,
            expected_evidence=expected_evidence,
        )
        session.add(eval_case)
        await session.commit()


async def generate_healthy(merchant_id: uuid.UUID):
    """Generate a standard Authorized -> Captured -> Settled transaction."""
    async with async_session_factory() as session:
        idem_key = f"idem-{uuid.uuid4()}"
        amount = Decimal(random.randint(1000, 50000)) / 100
        tx, _ = await transaction_service.create_transaction(session, idem_key, merchant_id, amount)
        await session.commit()

    async with async_session_factory() as session:
        await webhook_service.process_webhook(
            session,
            f"evt-{uuid.uuid4()}",
            tx.id,
            "payment.captured",
            {"capture_amount": str(amount)},
        )
        await session.commit()

    async with async_session_factory() as session:
        await webhook_service.process_webhook(
            session,
            f"evt-{uuid.uuid4()}",
            tx.id,
            "payment.settled",
            {"settled_amount": str(amount)},
        )
        await session.commit()


async def generate_class1_idempotency_collision(merchant_id: uuid.UUID):
    """Failure Class 1: Idempotency key collision under concurrent retry."""
    idem_key = f"idem-{uuid.uuid4()}"
    amount = Decimal("99.99")

    async def create_attempt():
        async with async_session_factory() as session:
            try:
                tx, created = await transaction_service.create_transaction(
                    session, idem_key, merchant_id, amount
                )
                await session.commit()
                return tx, created
            except Exception:
                return None, False

    results = await asyncio.gather(create_attempt(), create_attempt())
    tx = next((r[0] for r in results if r[0] is not None), None)
    if tx:
        await create_eval_case(
            tx.id,
            "Customer claims they tried to checkout twice and got an error.",
            "Idempotency collision",
            [{"source_tool": "query_transaction_db", "source_ref": "transaction_events"}],
        )


async def generate_class2_webhook_retry_storm(merchant_id: uuid.UUID):
    """Failure Class 2: Webhook retry storm (provider redelivers event 5+ times)."""
    async with async_session_factory() as session:
        idem_key = f"idem-{uuid.uuid4()}"
        amount = Decimal("45.00")
        tx, _ = await transaction_service.create_transaction(session, idem_key, merchant_id, amount)
        await session.commit()

    event_id = f"evt-storm-{uuid.uuid4()}"

    async def process_storm_webhook():
        async with async_session_factory() as session:
            await webhook_service.process_webhook(
                session, event_id, tx.id, "payment.captured", {"capture_amount": str(amount)}
            )
            await session.commit()

    await asyncio.gather(*(process_storm_webhook() for _ in range(6)))

    await create_eval_case(
        tx.id,
        "System alerts show a spike in webhook processing for this transaction.",
        "Webhook retry storm",
        [
            {
                "source_tool": "check_failure_signatures",
                "source_ref": "SIGNATURE_MATCH: Webhook retry storm detected (duplicate provider_event_ids).",
            }
        ],
    )


async def generate_class3_gateway_timeout(merchant_id: uuid.UUID):
    """Failure Class 3: Gateway timeout -> ambiguous state (stuck in authorized)."""
    async with async_session_factory() as session:
        idem_key = f"idem-{uuid.uuid4()}"
        amount = Decimal("150.00")
        tx, _ = await transaction_service.create_transaction(session, idem_key, merchant_id, amount)
        await session.execute(
            text(
                "UPDATE transactions SET created_at = created_at - interval '10 days' WHERE id = :id"
            ),
            {"id": str(tx.id)},
        )
        await session.commit()

    await create_eval_case(
        tx.id,
        "Order is stuck pending for 10 days.",
        "Gateway timeout / stuck auth",
        [{"source_tool": "query_transaction_db", "source_ref": "transaction"}],
    )


async def generate_class4_partial_capture(merchant_id: uuid.UUID):
    """Failure Class 4: Partial capture failure (multi-item order, one item fails)."""
    async with async_session_factory() as session:
        idem_key = f"idem-{uuid.uuid4()}"
        amount = Decimal("200.00")
        tx, _ = await transaction_service.create_transaction(session, idem_key, merchant_id, amount)
        await session.commit()

    async with async_session_factory() as session:
        await webhook_service.process_webhook(
            session,
            f"evt-{uuid.uuid4()}",
            tx.id,
            "payment.captured",
            {"capture_amount": "100.00", "note": "partial"},
        )
        await session.commit()

    await create_eval_case(
        tx.id,
        "Customer says order was 200 but they were only charged 100.",
        "Partial capture failure",
        [
            {
                "source_tool": "check_failure_signatures",
                "source_ref": "SIGNATURE_MATCH: Partial capture (captured amount < authorized amount).",
            }
        ],
    )


async def generate_class5_settlement_mismatch(merchant_id: uuid.UUID):
    """Failure Class 5: Settlement mismatch (captured != settled, e.g. FX rounding)."""
    async with async_session_factory() as session:
        idem_key = f"idem-{uuid.uuid4()}"
        amount = Decimal("100.00")
        tx, _ = await transaction_service.create_transaction(session, idem_key, merchant_id, amount)
        await session.commit()

    async with async_session_factory() as session:
        await webhook_service.process_webhook(
            session, f"evt-{uuid.uuid4()}", tx.id, "payment.captured", {"capture_amount": "100.00"}
        )
        await session.commit()

    async with async_session_factory() as session:
        await webhook_service.process_webhook(
            session,
            f"evt-{uuid.uuid4()}",
            tx.id,
            "payment.settled",
            {"settled_amount": "99.85", "fee": "0.15"},
        )
        await session.commit()

    await create_eval_case(
        tx.id,
        "Merchant reconciliation missing 15 cents.",
        "Settlement mismatch",
        [
            {
                "source_tool": "check_failure_signatures",
                "source_ref": "SIGNATURE_MATCH: Settlement mismatch (settled amount != captured amount).",
            }
        ],
    )


async def generate_class6_refund_capture_race(merchant_id: uuid.UUID):
    """Failure Class 6: Refund/capture race (optimistic concurrency hit)."""
    async with async_session_factory() as session:
        idem_key = f"idem-{uuid.uuid4()}"
        amount = Decimal("75.00")
        tx, _ = await transaction_service.create_transaction(session, idem_key, merchant_id, amount)
        await session.commit()

    async def attempt_refund():
        async with async_session_factory() as session:
            try:
                fresh_tx = await transaction_service.get_transaction(session, tx.id)
                await transaction_service.refund_transaction(session, fresh_tx.id, fresh_tx.version)
                await session.commit()
            except Exception:
                pass

    async def attempt_capture():
        async with async_session_factory() as session:
            try:
                await webhook_service.process_webhook(
                    session,
                    f"evt-{uuid.uuid4()}",
                    tx.id,
                    "payment.captured",
                    {"capture_amount": "75.00"},
                )
                await session.commit()
            except Exception:
                pass

    await asyncio.gather(attempt_refund(), attempt_capture())

    await create_eval_case(
        tx.id,
        "Customer asked for refund but still got charged.",
        "Refund/capture race condition",
        [{"source_tool": "query_transaction_db", "source_ref": "transaction_events"}],
    )


async def main(total_count: int):
    log.info("Starting synthetic data generation", target_count=total_count)
    merchants = await ensure_merchants()

    tasks = []
    healthy_target = int(total_count * 0.7)
    anomalies_target = total_count - healthy_target
    per_class = max(1, anomalies_target // 6)

    for _ in range(healthy_target):
        mid = random.choice(merchants).id
        tasks.append(generate_healthy(mid))

    for _ in range(per_class):
        mid = random.choice(merchants).id
        tasks.append(generate_class1_idempotency_collision(mid))
        tasks.append(generate_class2_webhook_retry_storm(mid))
        tasks.append(generate_class3_gateway_timeout(mid))
        tasks.append(generate_class4_partial_capture(mid))
        tasks.append(generate_class5_settlement_mismatch(mid))
        tasks.append(generate_class6_refund_capture_race(mid))

    log.info("Executing generation tasks in parallel...", task_count=len(tasks))
    await asyncio.gather(*tasks)

    log.info("Synthetic data generation complete.")
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic transaction data.")
    parser.add_argument("--count", type=int, default=100)
    args = parser.parse_args()

    asyncio.run(main(args.count))
