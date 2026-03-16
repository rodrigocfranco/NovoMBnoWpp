"""Graph node: process media attachments (audio transcription, image analysis)."""

import base64

import structlog

from workflows.providers.whatsapp import download_media, send_text_message
from workflows.providers.whisper import transcribe_audio
from workflows.utils.errors import ExternalServiceError, GraphNodeError
from workflows.whatsapp.state import WhatsAppState

logger = structlog.get_logger(__name__)

AUDIO_FAILURE_MESSAGE = "Não consegui processar seu áudio. Pode enviar por texto?"
IMAGE_FAILURE_MESSAGE = "Não consegui baixar sua imagem. Pode reenviar ou descrever por texto?"
IMAGE_TOO_LARGE_MESSAGE = "Sua imagem é muito grande (máximo 5 MB). Pode enviar uma imagem menor?"
IMAGE_UNSUPPORTED_TYPE_MESSAGE = (
    "Formato de imagem não suportado. Envie como JPEG, PNG, WebP ou GIF."
)
IMAGE_DEFAULT_PROMPT = "Analise esta imagem e me ajude a entender o conteúdo."

IMAGE_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
IMAGE_DOWNLOAD_TIMEOUT = 15.0  # seconds — images can be larger than audio (AC6/NFR3)
SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


async def process_media(state: WhatsAppState) -> dict:
    """Process media attachments: transcribe audio or prepare image for Vision.

    For audio messages:
        1. Downloads audio via WhatsApp Cloud API
        2. Transcribes via Whisper API
        3. Sets transcribed_text and user_message for downstream nodes

    For image messages:
        1. Downloads image via WhatsApp Cloud API
        2. Validates size (≤ 5 MB) and MIME type
        3. Encodes to base64 and builds multimodal content blocks
        4. Sets image_message for orchestrate_llm

    For text: returns empty dict (no-op).

    On failure: returns fallback user_message so the pipeline continues gracefully.
    """
    message_type = state.get("message_type", "text")

    if message_type == "audio":
        return await _process_audio(state)
    if message_type == "image":
        return await _process_image(state)
    return {}


async def _process_audio(state: WhatsAppState) -> dict:
    """Handle audio messages: download + Whisper transcription."""
    phone = state["phone_number"]
    media_id = state.get("media_id")
    mime_type = state.get("mime_type", "audio/ogg")

    logger.info(
        "process_media_audio_started",
        phone_suffix=phone[-4:],
        media_id=media_id,
        mime_type=mime_type,
    )

    try:
        audio_bytes, _ = await download_media(media_id, mime_type)
        transcription = await transcribe_audio(audio_bytes, mime_type)
    except Exception as exc:
        logger.error(
            "process_media_audio_failed",
            node="process_media",
            phone_suffix=phone[-4:],
            media_id=media_id,
            error_type=type(exc).__name__,
            error_message=str(exc),
            user_id=state.get("user_id", ""),
            trace_id=state.get("trace_id", ""),
        )
        try:
            await send_text_message(phone, AUDIO_FAILURE_MESSAGE)
        except Exception:
            logger.exception(
                "process_media_failure_message_send_failed",
                phone_suffix=phone[-4:],
            )
        raise GraphNodeError(
            node="process_media",
            message=f"Audio transcription failed: {exc}",
        ) from exc

    # Build user_message: concatenate with existing body if debounce accumulated text
    existing_body = state.get("user_message", "").strip()
    if existing_body:
        user_message = f"{existing_body}\n\n[Transcrição do áudio]: {transcription}"
    else:
        user_message = transcription

    logger.info(
        "process_media_audio_completed",
        phone_suffix=phone[-4:],
        transcription_length=len(transcription),
        has_existing_body=bool(existing_body),
    )

    return {
        "transcribed_text": transcription,
        "user_message": user_message,
    }


async def _process_image(state: WhatsAppState) -> dict:
    """Handle image messages: download + base64 + multimodal content blocks.

    On download failure: returns fallback user_message (pipeline continues).
    On size/type validation failure: returns informative user_message.
    """
    phone = state["phone_number"]
    media_id = state.get("media_id")
    mime_type = state.get("mime_type", "image/jpeg")
    user_text = state.get("user_message", "").strip()

    logger.info(
        "process_media_image_started",
        phone_suffix=phone[-4:],
        media_id=media_id,
        mime_type=mime_type,
    )

    # Validate MIME type
    if mime_type not in SUPPORTED_IMAGE_TYPES:
        logger.warning(
            "image_unsupported_mime_type",
            phone_suffix=phone[-4:],
            media_id=media_id,
            mime_type=mime_type,
        )
        return {"user_message": IMAGE_UNSUPPORTED_TYPE_MESSAGE}

    # Download image
    try:
        image_bytes, _ = await download_media(media_id, mime_type, timeout=IMAGE_DOWNLOAD_TIMEOUT)
    except ExternalServiceError as exc:
        logger.error(
            "image_download_failed",
            node="process_media",
            phone_suffix=phone[-4:],
            media_id=media_id,
            mime_type=mime_type,
            error_type=type(exc).__name__,
            error_message=str(exc),
            user_id=state.get("user_id", ""),
            trace_id=state.get("trace_id", ""),
        )
        return {"user_message": IMAGE_FAILURE_MESSAGE}
    except Exception as exc:
        logger.error(
            "image_download_unexpected_error",
            node="process_media",
            phone_suffix=phone[-4:],
            media_id=media_id,
            mime_type=mime_type,
            error_type=type(exc).__name__,
            error_message=str(exc),
            user_id=state.get("user_id", ""),
            trace_id=state.get("trace_id", ""),
        )
        return {"user_message": IMAGE_FAILURE_MESSAGE}

    # Validate size
    if len(image_bytes) > IMAGE_MAX_BYTES:
        logger.warning(
            "image_too_large",
            phone_suffix=phone[-4:],
            media_id=media_id,
            size_bytes=len(image_bytes),
        )
        return {"user_message": IMAGE_TOO_LARGE_MESSAGE}

    # Encode to base64
    base64_data = base64.standard_b64encode(image_bytes).decode("utf-8")

    # Build multimodal content blocks (Anthropic native format)
    text_content = user_text if user_text else IMAGE_DEFAULT_PROMPT
    content_blocks = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mime_type,
                "data": base64_data,
            },
        },
        {"type": "text", "text": text_content},
    ]

    logger.info(
        "image_processed",
        phone_suffix=phone[-4:],
        media_id=media_id,
        mime_type=mime_type,
        size_bytes=len(image_bytes),
        base64_size=len(base64_data),
        has_caption=bool(user_text),
    )

    return {"image_message": content_blocks}
