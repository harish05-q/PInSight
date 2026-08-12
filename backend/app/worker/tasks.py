import uuid

import structlog

from app.db import sync_session_factory
from app.models.incident import Incident, IncidentEmbedding
from app.models.runbook import Runbook
from app.services import embedding_service

log = structlog.get_logger()


def embed_and_save_incident(incident_id: str) -> None:
    """Generate and save an embedding for an incident synchronously."""
    log.info("Starting embedding job for incident", incident_id=incident_id)

    with sync_session_factory() as session:
        incident = session.get(Incident, uuid.UUID(incident_id))
        if not incident:
            log.error("Incident not found", incident_id=incident_id)
            return

        # Combine fields that would be useful for semantic search
        text_to_embed = f"Status: {incident.status} Description: {incident.description}"
        embedding_vector = embedding_service.generate_embedding(text_to_embed)

        # Upsert embedding
        if incident.embedding:
            incident.embedding.embedding = embedding_vector
        else:
            new_embedding = IncidentEmbedding(incident_id=incident.id, embedding=embedding_vector)
            session.add(new_embedding)

        session.commit()
    log.info("Finished embedding job for incident", incident_id=incident_id)


def embed_and_save_runbook(runbook_id: str) -> None:
    """Generate and save an embedding for a runbook synchronously."""
    log.info("Starting embedding job for runbook", runbook_id=runbook_id)

    with sync_session_factory() as session:
        runbook = session.get(Runbook, uuid.UUID(runbook_id))
        if not runbook:
            log.error("Runbook not found", runbook_id=runbook_id)
            return

        text_to_embed = f"Title: {runbook.title} Content: {runbook.content}"
        embedding_vector = embedding_service.generate_embedding(text_to_embed)

        runbook.embedding = embedding_vector
        session.commit()
    log.info("Finished embedding job for runbook", runbook_id=runbook_id)


def run_eval_job(run_id: str, limit: int = 14) -> None:
    """Execute an asynchronous evaluation run over a batch of eval cases."""
    import asyncio

    from app.agent.orchestrator import run_investigation_and_save
    from app.config import settings
    from app.models.eval import EvalCase, EvalResult, EvalRun
    from app.services.eval_service import compute_precision_recall

    log.info("Starting evaluation job", run_id=run_id, limit=limit)

    # We must run the async orchestrator from a synchronous context,
    # but run_investigation_and_save requires an AsyncSession.
    # We'll create a single async function and run it.
    async def _do_eval():
        from sqlalchemy import select

        from app.db import async_session_factory

        async with async_session_factory() as session:
            run = await session.get(EvalRun, uuid.UUID(run_id))
            if not run:
                log.error("EvalRun not found", run_id=run_id)
                return

            cases_result = await session.execute(
                select(EvalCase).order_by(EvalCase.created_at.desc()).limit(limit)
            )
            cases = cases_result.scalars().all()

            run.total_cases = len(cases)
            await session.commit()

            if not cases:
                run.status = "completed"
                await session.commit()
                return

            cases_data = [
                {
                    "incident_id": str(case.incident_id),
                    "expected_root_cause": case.expected_root_cause,
                    "expected_evidence": case.expected_evidence,
                }
                for case in cases
            ]

            total_passes = 0
            total_precision = 0.0
            total_recall = 0.0
            total_latency = 0
            total_tokens = 0
            total_hallucinations = 0

            for case_data in cases_data:
                log.info("Evaluating case", incident_id=case_data["incident_id"])
                try:
                    final_answer = await run_investigation_and_save(session, case_data["incident_id"])
                    meta = final_answer.get("_meta", {})

                    actual_root_cause = final_answer.get("root_cause", "")
                    passed = actual_root_cause.lower() == case_data["expected_root_cause"].lower()

                    precision, recall = compute_precision_recall(
                        final_answer.get("evidence", []), case_data["expected_evidence"]
                    )

                    result = EvalResult(
                        run_id=run.id,
                        incident_id=uuid.UUID(case_data["incident_id"]),
                        passed=passed,
                        actual_root_cause=actual_root_cause[:255],
                        precision=precision,
                        recall=recall,
                        latency_ms=meta.get("latency_ms", 0),
                        tokens_used=meta.get("tokens_used", 0),
                        steps=meta.get("steps", 0),
                        hallucinated_citations=meta.get("hallucination_count", 0),
                    )
                    session.add(result)

                    total_passes += 1 if passed else 0
                    total_precision += precision
                    total_recall += recall
                    total_latency += meta.get("latency_ms", 0)
                    total_tokens += meta.get("tokens_used", 0)
                    total_hallucinations += meta.get("hallucination_count", 0)
                    
                    # Need to commit each result so we don't hold a massive transaction,
                    # and also to clear any pending rollbacks if an error occurred.
                    await session.commit()

                except Exception as e:
                    log.error(
                        "Failed to eval case", incident_id=case_data["incident_id"], error=str(e)
                    )
                    await session.rollback()

            run.accuracy = total_passes / len(cases)
            run.avg_precision = total_precision / len(cases)
            run.avg_recall = total_recall / len(cases)
            run.hallucination_rate = total_hallucinations / len(cases)
            run.avg_latency_ms = total_latency // len(cases)
            run.avg_tokens = total_tokens // len(cases)
            run.total_cost_usd = total_tokens * settings.groq_cost_per_token
            run.status = "completed"

            await session.commit()

    asyncio.run(_do_eval())
    log.info("Finished evaluation job", run_id=run_id)
