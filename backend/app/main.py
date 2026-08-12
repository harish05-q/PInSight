import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.deps import rate_limit
from app.api.eval import router as eval_router
from app.api.health import router as health_router
from app.api.incidents import router as incidents_router
from app.api.investigations import router as investigations_router
from app.api.runbooks import router as runbooks_router
from app.api.search import router as search_router
from app.api.transactions import router as transactions_router
from app.api.webhooks import router as webhooks_router
from app.config import settings
from app.db import engine

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        getattr(logging, settings.log_level.upper(), logging.INFO)
    ),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    log.info("pinsight_starting", env=settings.env)
    yield
    await engine.dispose()
    log.info("pinsight_shutdown")


app = FastAPI(
    title="PInSight API",
    description="Agentic Payment Incident Investigation Platform",
    version="0.1.0",
    lifespan=lifespan,
    dependencies=[Depends(rate_limit)],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(health_router)
app.include_router(transactions_router)
app.include_router(webhooks_router)
app.include_router(incidents_router)
app.include_router(runbooks_router)
app.include_router(investigations_router)
app.include_router(eval_router)
app.include_router(search_router)
app.include_router(dashboard_router)
