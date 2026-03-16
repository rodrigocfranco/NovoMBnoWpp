"""Pinecone Assistant provider for RAG knowledge base queries."""

import asyncio
import time
from typing import Any

import structlog
from django.conf import settings
from pinecone import Pinecone

from workflows.services.config_service import ConfigService
from workflows.utils.errors import ExternalServiceError

logger = structlog.get_logger(__name__)

_instance: "PineconeProvider | None" = None
_lock = asyncio.Lock()

MIN_SCORE_THRESHOLD = 0.5
FALLBACK_PINECONE_TIMEOUT = 8.0


async def _get_pinecone_timeout() -> float:
    """Load Pinecone timeout from ConfigService with hardcoded fallback."""
    try:
        return float(await ConfigService.get("timeout:pinecone"))
    except Exception:
        logger.warning("pinecone_timeout_config_not_found", fallback=FALLBACK_PINECONE_TIMEOUT)
        return FALLBACK_PINECONE_TIMEOUT


class PineconeProvider:
    """Pinecone Assistant provider with singleton pattern.

    Uses the Pinecone Assistant context() API to retrieve relevant
    document chunks without generating an AI response.
    """

    def __init__(self, assistant: Any) -> None:
        self._assistant = assistant

    async def query_similar(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = MIN_SCORE_THRESHOLD,
    ) -> list[dict]:
        """Query Pinecone Assistant for relevant document chunks.

        Args:
            query: The text query to search for.
            top_k: Number of top results to return.
            min_score: Minimum relevance score threshold (0-1).

        Returns:
            List of dicts with keys: title, text, source, section, score.

        Raises:
            ExternalServiceError: On any Pinecone failure.
        """
        from pinecone_plugins.assistant.models.chat import Message

        timeout = await _get_pinecone_timeout()
        start = time.perf_counter()
        try:
            msg = Message(content=query)
            ctx = await asyncio.wait_for(
                asyncio.to_thread(self._assistant.context, messages=[msg]),
                timeout=timeout,
            )
        except TimeoutError as exc:
            raise ExternalServiceError(
                service="Pinecone",
                message=f"Context query timed out after {timeout}s",
            ) from exc
        except Exception as exc:
            raise ExternalServiceError(
                service="Pinecone",
                message=f"Context query failed: {exc}",
            ) from exc

        latency_ms = (time.perf_counter() - start) * 1000

        results = []
        filtered_count = 0
        for snippet in ctx.snippets[: top_k * 2]:
            if snippet.score < min_score:
                filtered_count += 1
                continue
            if len(results) >= top_k:
                break

            ref = snippet.reference or {}
            file_info = ref.get("file", {}) if isinstance(ref, dict) else getattr(ref, "file", None)
            file_name = ""
            if file_info:
                file_name = (
                    file_info.get("name", "")
                    if isinstance(file_info, dict)
                    else getattr(file_info, "name", "")
                )

            pages = ""
            ref_pages = ref.get("pages", []) if isinstance(ref, dict) else getattr(ref, "pages", [])
            if ref_pages:
                pages = f"pp. {ref_pages[0]}-{ref_pages[-1]}"

            results.append(
                {
                    "title": file_name,
                    "text": snippet.content[:500] if snippet.content else "",
                    "source": file_name,
                    "section": pages,
                    "score": snippet.score,
                }
            )

        logger.info(
            "pinecone_query_executed",
            results_count=len(results),
            filtered_below_threshold=filtered_count,
            top_k=top_k,
            min_score=min_score,
            latency_ms=round(latency_ms, 1),
        )

        return results


async def get_pinecone() -> PineconeProvider:
    """Return PineconeProvider singleton with lazy initialization."""
    global _instance

    if _instance is not None:
        return _instance

    async with _lock:
        if _instance is not None:
            return _instance

        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        assistant = pc.assistant.Assistant(
            assistant_name=settings.PINECONE_ASSISTANT_NAME,
        )

        _instance = PineconeProvider(assistant=assistant)

        logger.info(
            "pinecone_provider_initialized",
            assistant_name=settings.PINECONE_ASSISTANT_NAME,
        )

    return _instance
