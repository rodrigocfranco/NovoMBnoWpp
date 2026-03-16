"""Embedding provider using VertexAI text-embedding-004."""

import json

import structlog
from django.conf import settings
from langchain_google_vertexai import VertexAIEmbeddings

from workflows.utils.errors import ExternalServiceError

logger = structlog.get_logger(__name__)

_embeddings_instance: VertexAIEmbeddings | None = None


def get_embeddings() -> VertexAIEmbeddings:
    """Return VertexAIEmbeddings singleton with text-embedding-004.

    Uses the same GCP project/location as the LLM provider (zero egress).
    """
    global _embeddings_instance

    if _embeddings_instance is not None:
        return _embeddings_instance

    kwargs: dict = {
        "model_name": "text-embedding-004",
        "project": settings.VERTEX_PROJECT_ID,
        "location": settings.VERTEX_LOCATION,
    }

    if settings.GCP_CREDENTIALS:
        from google.oauth2 import service_account

        creds_info = json.loads(settings.GCP_CREDENTIALS)
        kwargs["credentials"] = service_account.Credentials.from_service_account_info(
            creds_info,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )

    _embeddings_instance = VertexAIEmbeddings(**kwargs)

    logger.info(
        "embeddings_provider_initialized",
        model="text-embedding-004",
        project=settings.VERTEX_PROJECT_ID,
    )

    return _embeddings_instance


async def embed_query(text: str) -> list[float]:
    """Generate embedding vector for a text query.

    Args:
        text: The query text to embed.

    Returns:
        List of floats representing the embedding vector.

    Raises:
        ExternalServiceError: On any VertexAI embedding failure.
    """
    embeddings = get_embeddings()
    try:
        return await embeddings.aembed_query(text)
    except Exception as exc:
        raise ExternalServiceError(
            service="VertexAI Embeddings",
            message=f"Embedding query failed: {exc}",
        ) from exc
