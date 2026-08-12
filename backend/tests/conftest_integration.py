"""Integration test fixtures for Phase 1 concurrency tests.

These tests REQUIRE a real PostgreSQL database — SQLite does not support
the concurrency semantics being tested (row-level locking, UNIQUE constraint
behavior under concurrent INSERTs).

Set TEST_DATABASE_URL to point to a Postgres instance, or these tests
will be skipped automatically.
"""

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import get_db
from app.main import app
from app.models import Base

# Integration tests require a real Postgres. Skip if not available.
INTEGRATION_DB_URL = os.environ.get("TEST_DATABASE_URL", "")

requires_postgres = pytest.mark.skipif(
    not INTEGRATION_DB_URL,
    reason="TEST_DATABASE_URL not set — skipping integration tests (need real Postgres)",
)


@pytest.fixture(scope="session")
async def integration_engine():
    """Create a test database engine connected to real Postgres."""
    if not INTEGRATION_DB_URL:
        pytest.skip("TEST_DATABASE_URL not set")

    engine = create_async_engine(INTEGRATION_DB_URL, echo=False, pool_size=20, max_overflow=10)

    # Create all tables
    async with engine.begin() as conn:
        # Enable pgvector extension (needed later)
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(autouse=True)
async def cleanup_tables(integration_engine):
    """Clean all data between tests (autouse for all integration tests)."""
    yield
    if integration_engine:
        async with integration_engine.begin() as conn:
            await conn.execute(text("DELETE FROM transaction_events"))
            await conn.execute(text("DELETE FROM webhook_events"))
            await conn.execute(text("DELETE FROM transactions"))
            await conn.execute(text("DELETE FROM merchants"))


@pytest.fixture
async def integration_session(integration_engine) -> AsyncSession:
    """Direct DB session for test setup/assertions."""
    session_factory = async_sessionmaker(integration_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.commit()


@pytest.fixture
async def integration_client(integration_engine) -> AsyncClient:
    """HTTP client that uses the integration Postgres DB.

    Each HTTP request gets its own session (via get_db override),
    just like production — this is what makes the concurrency tests real.
    """
    session_factory = async_sessionmaker(integration_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def merchant_id(integration_session: AsyncSession) -> uuid.UUID:
    """Create a test merchant and return its ID."""
    mid = uuid.uuid4()
    await integration_session.execute(
        text("INSERT INTO merchants (id, name) VALUES (:id, :name)"),
        {"id": str(mid), "name": "Test Merchant"},
    )
    await integration_session.commit()
    return mid
