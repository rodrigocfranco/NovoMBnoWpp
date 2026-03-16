"""WhatsApp Cloud API client using httpx async."""

import httpx
import structlog
from django.conf import settings

from workflows.services.config_service import ConfigService
from workflows.utils.errors import ExternalServiceError

logger = structlog.get_logger(__name__)

_client: httpx.AsyncClient | None = None

WHATSAPP_API_BASE = "https://graph.facebook.com"
FALLBACK_WHATSAPP_TIMEOUT = 10.0


async def _get_whatsapp_timeout() -> float:
    """Load WhatsApp timeout from ConfigService with hardcoded fallback."""
    try:
        return float(await ConfigService.get("timeout:whatsapp"))
    except Exception:
        logger.warning("whatsapp_timeout_config_not_found", fallback=FALLBACK_WHATSAPP_TIMEOUT)
        return FALLBACK_WHATSAPP_TIMEOUT


async def _get_client() -> httpx.AsyncClient:
    """Singleton httpx.AsyncClient for WhatsApp Cloud API.

    Loads timeout from ConfigService on first creation.
    """
    global _client
    if _client is None or _client.is_closed:
        timeout = await _get_whatsapp_timeout()
        _client = httpx.AsyncClient(
            base_url=f"{WHATSAPP_API_BASE}/{settings.WHATSAPP_API_VERSION}",
            headers={
                "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )
    return _client


async def send_text_message(phone: str, text: str) -> dict:
    """Send a text message via WhatsApp Cloud API.

    Args:
        phone: Recipient phone number (with or without '+' prefix).
        text: Message body text (max 4096 chars).

    Returns:
        WhatsApp API response dict.

    Raises:
        ExternalServiceError: On HTTP errors or timeout.
    """
    client = await _get_client()
    phone = phone.lstrip("+")
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "text",
        "text": {"body": text},
    }
    try:
        response = await client.post(
            f"/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        logger.info(
            "whatsapp_message_sent",
            phone=phone,
            wamid=data["messages"][0]["id"],
        )
        return data
    except httpx.HTTPStatusError as exc:
        raise ExternalServiceError(
            service="whatsapp",
            message=f"HTTP {exc.response.status_code}: {exc.response.text}",
        ) from exc
    except httpx.TimeoutException as exc:
        raise ExternalServiceError(
            service="whatsapp",
            message="Timeout sending message",
        ) from exc


async def download_media(
    media_id: str, mime_type: str, *, timeout: float | None = None
) -> tuple[bytes, str]:
    """Download media content from WhatsApp Cloud API.

    Two-step process:
    1. GET media URL from graph.facebook.com/{media_id}
    2. GET binary content from the temporary URL

    Args:
        media_id: WhatsApp media ID from the webhook payload.
        mime_type: MIME type of the media (e.g. "audio/ogg; codecs=opus").
        timeout: Optional per-request timeout in seconds for content download.
            When None, uses the client default timeout.

    Returns:
        Tuple of (content_bytes, mime_type).

    Raises:
        ExternalServiceError: On HTTP errors or timeout.
    """
    client = await _get_client()
    try:
        # Step 1: Get temporary media URL
        url_response = await client.get(f"/{media_id}")
        url_response.raise_for_status()
        url_data = url_response.json()
        media_url = url_data.get("url")
        if not media_url:
            raise ExternalServiceError(
                service="whatsapp",
                message=f"No 'url' in media response for {media_id}",
            )
        logger.info("media_url_fetched", media_id=media_id, mime_type=mime_type)

        # Step 2: Download binary content from temporary URL
        content_response = await client.get(media_url, timeout=timeout)
        content_response.raise_for_status()
        content = content_response.content
        logger.info(
            "media_downloaded",
            media_id=media_id,
            mime_type=mime_type,
            size_bytes=len(content),
        )
        return content, mime_type
    except httpx.HTTPStatusError as exc:
        raise ExternalServiceError(
            service="whatsapp",
            message=f"HTTP {exc.response.status_code}: media download failed for {media_id}",
        ) from exc
    except httpx.TimeoutException as exc:
        raise ExternalServiceError(
            service="whatsapp",
            message=f"Timeout downloading media {media_id}",
        ) from exc


async def send_interactive_buttons(
    phone: str,
    body_text: str,
    buttons: list[dict],
    footer_text: str | None = None,
) -> dict:
    """Send interactive message with Reply Buttons via WhatsApp Cloud API.

    Args:
        phone: Recipient phone number (E.164, with or without '+').
        body_text: Main text (max 1024 chars).
        buttons: List of 1-3 dicts with {id: str, title: str}.
        footer_text: Footer text (max 60 chars, optional).

    Returns:
        WhatsApp API response dict.

    Raises:
        ExternalServiceError: On HTTP errors or timeout.
    """
    client = await _get_client()
    phone = phone.lstrip("+")
    interactive: dict = {
        "type": "button",
        "body": {"text": body_text[:1024]},
        "action": {
            "buttons": [
                {"type": "reply", "reply": {"id": b["id"], "title": b["title"][:20]}}
                for b in buttons
            ]
        },
    }
    if footer_text:
        interactive["footer"] = {"text": footer_text[:60]}

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "interactive",
        "interactive": interactive,
    }
    try:
        response = await client.post(
            f"/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        logger.info(
            "whatsapp_interactive_sent",
            phone=phone,
            wamid=data["messages"][0]["id"],
        )
        return data
    except httpx.HTTPStatusError as exc:
        raise ExternalServiceError(
            service="whatsapp",
            message=f"HTTP {exc.response.status_code}: {exc.response.text}",
        ) from exc
    except httpx.TimeoutException as exc:
        raise ExternalServiceError(
            service="whatsapp",
            message="Timeout sending interactive message",
        ) from exc


async def mark_as_read(wamid: str) -> bool:
    """Mark a message as read (shows typing indicator).

    Best-effort: returns False on failure instead of raising.
    """
    client = await _get_client()
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": wamid,
    }
    try:
        response = await client.post(
            f"/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages",
            json=payload,
        )
        response.raise_for_status()
        logger.info("whatsapp_message_read_marked", wamid=wamid)
        return True
    except Exception:
        logger.warning("whatsapp_mark_read_failed", wamid=wamid)
        return False
