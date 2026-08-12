"""Service for generating semantic embeddings.

Uses Sentence-Transformers locally to avoid external API calls for embeddings,
keeping the external LLM API strictly for agentic reasoning.
"""

import structlog
from sentence_transformers import SentenceTransformer

log = structlog.get_logger()

# Load the model globally so it stays in memory for the worker process.
# This will be baked into the Docker image, so it won't download at runtime.
MODEL_NAME = "all-MiniLM-L6-v2"

_model = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        log.info("Loading sentence transformer model...", model=MODEL_NAME)
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def generate_embedding(text: str) -> list[float]:
    """Generate a 384-dimensional embedding for the given text."""
    model = get_model()
    # encode() returns a numpy array, we convert to a python list of floats
    embedding = model.encode(text).tolist()
    return embedding
