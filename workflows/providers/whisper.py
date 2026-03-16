"""OpenAI Whisper API client for audio transcription using httpx async."""

import asyncio
import time

import httpx
import structlog
from django.conf import settings

from workflows.services.config_service import ConfigService
from workflows.utils.errors import ExternalServiceError

logger = structlog.get_logger(__name__)

WHISPER_API_URL = "https://api.openai.com/v1/audio/transcriptions"
FALLBACK_WHISPER_TIMEOUT = 20.0
WHISPER_MAX_RETRIES = 2
WHISPER_BACKOFF_BASE = 1.0


async def _get_whisper_timeout() -> float:
    """Load Whisper timeout from ConfigService with hardcoded fallback."""
    try:
        return float(await ConfigService.get("timeout:whisper"))
    except Exception:
        logger.warning("whisper_timeout_config_not_found", fallback=FALLBACK_WHISPER_TIMEOUT)
        return FALLBACK_WHISPER_TIMEOUT


# Map mime_type to file extension for multipart upload
_MIME_TO_EXT = {
    "audio/ogg": "audio.ogg",
    "audio/ogg; codecs=opus": "audio.ogg",
    "audio/mpeg": "audio.mp3",
    "audio/mp4": "audio.mp4",
    "audio/mp3": "audio.mp3",
    "audio/wav": "audio.wav",
    "audio/webm": "audio.webm",
    "audio/flac": "audio.flac",
    "audio/x-m4a": "audio.m4a",
}

# HTTP status codes worth retrying (transient errors)
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _filename_for_mime(mime_type: str) -> str:
    """Return a filename matching the mime_type for the multipart upload."""
    return _MIME_TO_EXT.get(mime_type, "audio.ogg")


def _is_retryable(exc: Exception) -> bool:
    """Check if an exception represents a transient, retryable error."""
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS_CODES
    return False


async def transcribe_audio(audio_bytes: bytes, mime_type: str) -> str:
    """Transcribe audio bytes via OpenAI Whisper API.

    Args:
        audio_bytes: Raw audio content (downloaded from WhatsApp).
        mime_type: MIME type of the audio (e.g. "audio/ogg; codecs=opus").

    Returns:
        Transcribed text string.

    Raises:
        ExternalServiceError: On HTTP errors, timeout, or connection errors (after retries).
    """
    logger.info(
        "audio_transcription_started",
        audio_size_bytes=len(audio_bytes),
        mime_type=mime_type,
    )
    start = time.monotonic()

    filename = _filename_for_mime(mime_type)
    last_exc: Exception | None = None

    timeout = await _get_whisper_timeout()

    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(1 + WHISPER_MAX_RETRIES):
            if attempt > 0:
                wait = WHISPER_BACKOFF_BASE * (2 ** (attempt - 1))
                logger.info(
                    "audio_transcription_retry",
                    attempt=attempt,
                    wait_seconds=wait,
                )
                await asyncio.sleep(wait)

            try:
                response = await client.post(
                    WHISPER_API_URL,
                    headers={
                        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    },
                    files={
                        "file": (filename, audio_bytes, mime_type),
                    },
                    data={
                        "model": "whisper-1",
                        "language": "pt",
                        "response_format": "text",
                    },
                )
                response.raise_for_status()

                transcription = response.text.strip()
                duration_ms = int((time.monotonic() - start) * 1000)
                logger.info(
                    "audio_transcription_completed",
                    duration_ms=duration_ms,
                    audio_size_bytes=len(audio_bytes),
                    transcription_length=len(transcription),
                )
                return transcription

            except httpx.HTTPStatusError as exc:
                last_exc = exc
                logger.warning(
                    "audio_transcription_http_error",
                    attempt=attempt + 1,
                    status_code=exc.response.status_code,
                    detail=exc.response.text[:200],
                )
                if not _is_retryable(exc):
                    break
            except httpx.TimeoutException as exc:
                last_exc = exc
                logger.warning(
                    "audio_transcription_timeout",
                    attempt=attempt + 1,
                )
            except httpx.ConnectError as exc:
                last_exc = exc
                logger.warning(
                    "audio_transcription_connect_error",
                    attempt=attempt + 1,
                    error=str(exc),
                )

    duration_ms = int((time.monotonic() - start) * 1000)
    logger.error(
        "audio_transcription_failed",
        duration_ms=duration_ms,
        audio_size_bytes=len(audio_bytes),
        error=str(last_exc),
    )

    if isinstance(last_exc, httpx.HTTPStatusError):
        raise ExternalServiceError(
            service="whisper",
            message=f"HTTP {last_exc.response.status_code}: {last_exc.response.text[:200]}",
        ) from last_exc

    if isinstance(last_exc, httpx.ConnectError):
        raise ExternalServiceError(
            service="whisper",
            message=f"Connection error: {last_exc}",
        ) from last_exc

    raise ExternalServiceError(
        service="whisper",
        message=f"Timeout after {WHISPER_MAX_RETRIES} retries",
    ) from last_exc
