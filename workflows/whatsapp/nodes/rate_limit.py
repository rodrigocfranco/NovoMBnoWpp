"""Graph node: check rate limits (burst + daily) before processing."""

import structlog
from langgraph.graph import END

from workflows.providers.whatsapp import send_text_message
from workflows.services.config_service import ConfigService
from workflows.services.rate_limiter import RateLimiter
from workflows.whatsapp.state import WhatsAppState

logger = structlog.get_logger(__name__)

DEFAULT_DAILY_MESSAGE = (
    "Você atingiu seu limite de {limit} interações por hoje. "
    "Seu limite reseta amanhã às 00h. Até lá!"
)
DEFAULT_BURST_MESSAGE = "Muitas mensagens em sequência. Aguarde 1 minuto."
DEFAULT_WARNING_THRESHOLD = 2


async def rate_limit(state: WhatsAppState) -> dict:
    """Check rate limits and block or warn the user.

    When rate limited, sends message directly via WhatsApp (pipeline ends at END).
    When within limits, returns remaining count and optional warning.
    """
    user_id = state["user_id"]
    tier = state["subscription_tier"]
    phone = state["phone_number"]

    result = await RateLimiter.check(user_id, tier)

    if not result.allowed:
        # Send rate limit message directly (pipeline will end via conditional edge)
        if result.reason == "burst_exceeded":
            try:
                msg = await ConfigService.get("message:rate_limit_burst")
            except Exception:
                logger.warning("rate_limit_burst_config_fallback")
                msg = DEFAULT_BURST_MESSAGE
        else:
            try:
                msg = await ConfigService.get("message:rate_limit_daily")
            except Exception:
                logger.warning("rate_limit_daily_config_fallback")
                msg = DEFAULT_DAILY_MESSAGE
            msg = msg.format(limit=result.daily_limit)

        try:
            await send_text_message(phone, msg)
        except Exception:
            logger.exception("rate_limit_message_send_failed", phone_suffix=phone[-4:])

        return {
            "rate_limit_exceeded": True,
            "remaining_daily": 0,
            "rate_limit_warning": "",
        }

    # Calculate warning if close to daily limit
    warning = ""
    try:
        threshold = await ConfigService.get("rate_limit:warning_threshold")
        if isinstance(threshold, str):
            threshold = int(threshold)
    except Exception:
        logger.warning("rate_limit_warning_threshold_config_fallback")
        threshold = DEFAULT_WARNING_THRESHOLD

    if result.remaining_daily == 0:
        warning = "⚠️ Esta foi sua última pergunta hoje. Seu limite reseta amanhã às 00h."
    elif result.remaining_daily <= threshold:
        warning = (
            f"⚠️ Você ainda tem {result.remaining_daily} "
            f"pergunta{'s' if result.remaining_daily != 1 else ''} "
            f"disponível(is) hoje. Seu limite reseta amanhã às 00h."
        )

    return {
        "rate_limit_exceeded": False,
        "remaining_daily": result.remaining_daily,
        "rate_limit_warning": warning,
    }


def check_rate_limit(state: WhatsAppState) -> str:
    """Conditional edge function: END if rate limited, else continue to process_media."""
    if state.get("rate_limit_exceeded", False):
        return END
    return "process_media"
