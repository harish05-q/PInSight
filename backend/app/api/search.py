from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query
from sentence_transformers import SentenceTransformer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.incident import Incident, IncidentEmbedding
from app.models.runbook import Runbook

log = structlog.get_logger()
router = APIRouter(prefix="/v1/search", tags=["search"])

# We can re-use the same model loaded by the worker/tools
_model = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


@router.get("")
async def semantic_search(
    q: str = Query(..., description="The search query"),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Semantic search over Incidents and Runbooks."""
    model = get_model()
    query_embedding = model.encode(q).tolist()

    results = []

    # 1. Search Incidents
    # Using L2 distance (<->) via pgvector
    incident_stmt = (
        select(IncidentEmbedding, Incident)
        .join(Incident, IncidentEmbedding.incident_id == Incident.id)
        .order_by(IncidentEmbedding.embedding.l2_distance(query_embedding))
        .limit(5)
    )
    inc_res = await session.execute(incident_stmt)
    for row in inc_res:
        emb, inc = row
        results.append(
            {
                "type": "incident",
                "id": str(inc.id),
                "title": f"Incident {inc.id}",
                "description": inc.description,
                "status": inc.status,
                "score": emb.embedding,  # We don't have direct access to the computed distance without annotating it, so we skip score for simplicity or compute it in python
            }
        )

    # 2. Search Runbooks
    runbook_stmt = (
        select(Runbook)
        .where(Runbook.embedding.is_not(None))
        .order_by(Runbook.embedding.l2_distance(query_embedding))
        .limit(5)
    )
    rb_res = await session.execute(runbook_stmt)
    for rb in rb_res.scalars().all():
        results.append(
            {
                "type": "runbook",
                "id": str(rb.id),
                "title": rb.title,
                "description": rb.content[:200] + "...",
                "score": None,
            }
        )

    # We could sort the combined list here, but without extracting the exact distance from the query,
    # it's simpler to just return them grouped or rely on the frontend to display them.
    # We'll just return the combined list.

    return {"query": q, "results": results}
