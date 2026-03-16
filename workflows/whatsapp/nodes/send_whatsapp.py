"""Graph node: send formatted response via WhatsApp Cloud API."""

import structlog

from workflows.providers.whatsapp import (
    mark_as_read,
    send_interactive_buttons,
    send_text_message,
)
from workflows.services.config_service import ConfigService
from workflows.whatsapp.state import WhatsAppState

logger = structlog.get_logger(__name__)

DEFAULT_WELCOME_MESSAGE = (
    "Olá! Sou o Medbrain, seu tutor médico pelo WhatsApp. "
    "Pode me perguntar qualquer dúvida médica — respondo com fontes verificáveis."
)

DEFAULT_FEEDBACK_PROMPT = "Como você avalia esta resposta?"

FEEDBACK_BUTTONS = [
    {"id": "feedback_positive", "title": "\U0001f44d Útil"},
    {"id": "feedback_negative", "title": "\U0001f44e Não útil"},
    {"id": "feedback_comment", "title": "\U0001f4ac Comentar"},
]


async def send_whatsapp(state: WhatsAppState) -> dict:
    """Send formatted response to user via WhatsApp Cloud API.

    Steps:
    1. Mark incoming message as read (typing indicator, fire-and-forget).
    2. Send ``formatted_response`` as first message.
    3. Send each ``additional_responses`` part sequentially (best-effort).

    The main send (step 2) lets ExternalServiceError propagate so that
    LangGraph's RetryPolicy can retry on 429/5xx errors (AC4).
    Additional responses (step 3) are best-effort: partial delivery is
    preferable to retrying the entire node and re-sending the main message.

    Returns partial state dict with ``response_sent`` boolean.
    """
    phone = state["phone_number"]
    wamid = state["wamid"]

    # Typing indicator (best-effort, don't block on failure)
    await mark_as_read(wamid)

    # Welcome message for new users (best-effort — don't block main response)
    if state["is_new_user"]:
        try:
            try:
                welcome_text = await ConfigService.get("message:welcome")
            except Exception:
                logger.warning("welcome_config_fallback", phone=phone)
                welcome_text = DEFAULT_WELCOME_MESSAGE
            await send_text_message(phone, welcome_text)
            logger.info("welcome_message_sent", phone=phone)
        except Exception:
            logger.warning("welcome_message_failed", phone=phone, exc_info=True)

    # Send main response — let ExternalServiceError propagate for RetryPolicy
    await send_text_message(phone, state["formatted_response"])

    # Send additional parts (best-effort — partial is better than nothing)
    additional = state.get("additional_responses", [])
    sent_additional = 0
    for part in additional:
        try:
            await send_text_message(phone, part)
            sent_additional += 1
        except Exception:
            logger.exception(
                "whatsapp_additional_send_failed",
                phone=phone,
                part_index=sent_additional + 1,
                total_parts=len(additional),
            )
            break

    total_parts = 1 + sent_additional
    total_chars = len(state["formatted_response"]) + sum(
        len(p) for p in additional[:sent_additional]
    )

    logger.info(
        "whatsapp_response_sent",
        phone=phone,
        message_count=total_parts,
        total_chars=total_chars,
    )

    # Send feedback buttons as separate message (best-effort)
    try:
        try:
            feedback_body = await ConfigService.get("message:feedback_prompt")
        except Exception:
            feedback_body = DEFAULT_FEEDBACK_PROMPT
        await send_interactive_buttons(phone, feedback_body, FEEDBACK_BUTTONS)
        logger.info("feedback_buttons_sent", phone=phone)
    except Exception:
        logger.warning("feedback_buttons_failed", phone=phone, exc_info=True)

    return {"response_sent": True}
