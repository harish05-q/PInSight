from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""

    pass


# Import all models so Alembic autogenerate can discover them
from app.models.agent import AgentTrace, IncidentEvidence  # noqa: E402, F401
from app.models.eval import EvalCase, EvalResult, EvalRun  # noqa: E402, F401
from app.models.incident import Incident, IncidentEmbedding  # noqa: E402, F401
from app.models.merchant import Merchant  # noqa: E402, F401
from app.models.runbook import Runbook  # noqa: E402, F401
from app.models.transaction import Transaction, TransactionState  # noqa: E402, F401
from app.models.transaction_event import TransactionEvent  # noqa: E402, F401
from app.models.webhook_event import WebhookEvent  # noqa: E402, F401
