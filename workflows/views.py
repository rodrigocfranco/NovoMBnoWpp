"""WhatsApp webhook views."""

import asyncio
import re
import uuid
from collections.abc import Callable
from typing import Any

import structlog
from adrf.views import APIView
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from langfuse import propagate_attributes
from rest_framework.request import Request

from workflows.models import ErrorLog, Feedback, Message, User
from workflows.providers.langfuse import get_langfuse_handler, update_trace_metadata
from workflows.providers.redis import get_redis_client
from workflows.providers.whatsapp import send_text_message
from workflows.serializers import WhatsAppMessageSerializer
from workflows.services.config_service import ConfigService
from workflows.services.debounce import schedule_processing
from workflows.services.feature_flags import is_feature_enabled
from workflows.utils.deduplication import is_duplicate_message
from workflows.utils.errors import GraphNodeError
from workflows.whatsapp.graph import get_graph

FALLBACK_ERROR_MESSAGE = (
    "Desculpe, tive um problema ao processar sua mensagem. Pode tentar novamente?"
)

DEFAULT_UNSUPPORTED_MESSAGE = (
    "Desculpe, no momento só consigo processar mensagens de texto, áudio e imagem."
)

logger = structlog.get_logger(__name__)

SUPPORTED_TYPES = {"text", "audio", "image", "interactive"}
UNSUPPORTED_RESPONSE_TYPES = {"sticker", "location", "document", "contacts", "video"}
PROCESSABLE_MESSAGE_TYPES = SUPPORTED_TYPES | UNSUPPORTED_RESPONSE_TYPES

FEEDBACK_BUTTON_IDS = {"feedback_positive", "feedback_negative", "feedback_comment"}

DEFAULT_FEEDBACK_THANKS = "Obrigado pelo feedback! \U0001f64f"
DEFAULT_FEEDBACK_COMMENT_PROMPT = "Obrigado! Pode me contar o motivo da sua avaliação?"
DEFAULT_FEEDBACK_COMMENT_THANKS = (
    "Obrigado pelo seu comentário! Vamos usar para melhorar. \U0001f64f"
)

# NFR4: Limit concurrent graph executions to 50
_concurrency_semaphore = asyncio.Semaphore(50)


def should_process_event(entry: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract processable messages from a webhook entry.

    Filters out:
    - Status updates (delivered, read, failed)
    - System messages
    - Unknown message types
    - Entries without messages

    Returns list of dicts with phone, message_id, timestamp, message_type, body.
    """
    messages: list[dict[str, Any]] = []

    for change in entry.get("changes", []):
        value = change.get("value", {})

        if "statuses" in value:
            continue

        for msg in value.get("messages", []):
            msg_type = msg.get("type", "unknown")

            if msg_type not in PROCESSABLE_MESSAGE_TYPES:
                logger.debug("message_type_filtered", message_type=msg_type)
                continue

            phone = msg.get("from", "")
            body = ""
            if msg_type == "text":
                body = msg.get("text", {}).get("body", "")

            # Extract media_id and mime_type for audio/image (AC2 — Story 0.1)
            media_id = None
            mime_type = None
            if msg_type in ("audio", "image"):
                media_data = msg.get(msg_type, {})
                media_id = media_data.get("id")
                mime_type = media_data.get("mime_type")
                # Extract caption for images (AC4 — Story 3.2)
                if msg_type == "image":
                    body = media_data.get("caption") or ""

            # Extract button_reply data for interactive messages (Story 6.1)
            button_reply_id = None
            button_reply_title = None
            if msg_type == "interactive":
                interactive_data = msg.get("interactive", {})
                if interactive_data.get("type") == "button_reply":
                    button_reply = interactive_data.get("button_reply", {})
                    button_reply_id = button_reply.get("id")
                    button_reply_title = button_reply.get("title")

            messages.append(
                {
                    "phone": phone,
                    "message_id": msg.get("id", ""),
                    "timestamp": msg.get("timestamp", ""),
                    "message_type": msg_type,
                    "body": body,
                    "media_id": media_id,
                    "mime_type": mime_type,
                    "button_reply_id": button_reply_id,
                    "button_reply_title": button_reply_title,
                }
            )

    return messages


def _make_task_exception_handler(
    phone: str, message_id: str
) -> Callable[[asyncio.Task[None]], None]:
    """Create a task exception callback with message context (Story 5.2, Task 4.2)."""

    def _handler(task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return
        if exc := task.exception():
            logger.error(
                "message_processing_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                task_name=task.get_name(),
                phone=phone,
                message_id=message_id,
            )

    return _handler


async def _send_fallback(phone: str) -> None:
    """Send a friendly error message to the user (NFR13: zero lost messages)."""
    try:
        try:
            text = await ConfigService.get("message:error_fallback")
        except Exception:
            logger.warning("config_error_fallback_load_failed", phone=phone)
            text = FALLBACK_ERROR_MESSAGE
        await send_text_message(phone, text)
    except Exception:
        logger.exception("fallback_send_failed", phone=phone)


def _sanitize_error_msg(msg: str) -> str:
    """Strip URLs (may contain credentials) and truncate for DB storage."""
    return re.sub(r"https?://\S+", "[REDACTED_URL]", msg)[:1000]


async def set_pending_comment(phone: str, feedback_id: int) -> None:
    """Store pending comment state in Redis (TTL 300s)."""
    redis = get_redis_client()
    await redis.setex(f"feedback_pending:{phone}", 300, str(feedback_id))


async def get_pending_comment(phone: str) -> int | None:
    """Get and clear pending comment feedback_id from Redis."""
    redis = get_redis_client()
    value = await redis.get(f"feedback_pending:{phone}")
    if value:
        await redis.delete(f"feedback_pending:{phone}")
        return int(value)
    return None


async def handle_feedback(phone: str, button_reply_id: str) -> None:
    """Process feedback button click (AC #2, #3).

    - feedback_positive/feedback_negative: upsert Feedback, send thanks
    - feedback_comment: upsert Feedback with rating="comment", set pending, send prompt

    Uses aupdate_or_create to prevent duplicate feedbacks per user+message.
    """
    try:
        user = await User.objects.filter(phone=phone).afirst()
        if not user:
            logger.warning("feedback_user_not_found", phone=phone)
            return

        last_msg = (
            await Message.objects.filter(user=user, role="assistant")
            .order_by("-created_at")
            .afirst()
        )
        if not last_msg:
            logger.warning("feedback_no_assistant_message", phone=phone)
            return

        if button_reply_id == "feedback_comment":
            feedback, _created = await Feedback.objects.aupdate_or_create(
                user=user, message=last_msg, defaults={"rating": "comment"}
            )
            await set_pending_comment(phone, feedback.pk)
            try:
                text = await ConfigService.get("message:feedback_comment_prompt")
            except Exception:
                text = DEFAULT_FEEDBACK_COMMENT_PROMPT
            await send_text_message(phone, text)
            logger.info("feedback_comment_prompt_sent", phone=phone, feedback_id=feedback.pk)
        else:
            rating = "positive" if button_reply_id == "feedback_positive" else "negative"
            feedback, _created = await Feedback.objects.aupdate_or_create(
                user=user, message=last_msg, defaults={"rating": rating}
            )
            try:
                text = await ConfigService.get("message:feedback_thanks")
            except Exception:
                text = DEFAULT_FEEDBACK_THANKS
            await send_text_message(phone, text)
            logger.info("feedback_saved", phone=phone, rating=rating, feedback_id=feedback.pk)
    except Exception:
        logger.exception("handle_feedback_error", phone=phone)


async def handle_pending_comment(phone: str, feedback_id: int, comment_text: str) -> bool:
    """Save comment text on existing Feedback (AC #5)."""
    try:
        feedback = await Feedback.objects.filter(pk=feedback_id).afirst()
        if not feedback:
            logger.warning("pending_comment_feedback_not_found", feedback_id=feedback_id)
            return False

        feedback.comment = comment_text
        await feedback.asave(update_fields=["comment"])

        try:
            text = await ConfigService.get("message:feedback_comment_thanks")
        except Exception:
            text = DEFAULT_FEEDBACK_COMMENT_THANKS
        await send_text_message(phone, text)
        logger.info("feedback_comment_saved", phone=phone, feedback_id=feedback_id)
        return True
    except Exception:
        logger.exception("handle_pending_comment_error", phone=phone, feedback_id=feedback_id)
        return False


async def _handle_unsupported_message(phone: str, message_type: str) -> None:
    """Send informative message for unsupported message types (AC5/AC6).

    Loads text from ConfigService; falls back to hardcoded default on failure.
    Best-effort: errors are logged but never re-raised.
    """
    try:
        try:
            text = await ConfigService.get("message:unsupported_type")
        except Exception:
            logger.warning("config_unsupported_fallback", phone=phone)
            text = DEFAULT_UNSUPPORTED_MESSAGE

        await send_text_message(phone, text)
        logger.info(
            "unsupported_message_handled",
            phone=phone,
            message_type=message_type,
        )
    except Exception:
        logger.exception(
            "unsupported_message_send_failed",
            phone=phone,
            message_type=message_type,
        )


async def _process_message(validated_data: dict[str, Any]) -> None:
    """Process a single validated message via the WhatsApp StateGraph.

    Uses asyncio.Semaphore to limit concurrency to 50 (NFR4).
    """
    phone = validated_data["phone"]
    message_id = validated_data["message_id"]

    async with _concurrency_semaphore:
        # AC2 (Story 7.2): Capture trace_id from middleware contextvars
        ctx = structlog.contextvars.get_contextvars()
        trace_id = ctx.get("trace_id", str(uuid.uuid4()))
        message_type = validated_data["message_type"]

        logger.info(
            "graph_execution_started",
            message_id=message_id,
            phone=phone,
            message_type=message_type,
        )

        try:
            graph = await get_graph()
            initial_state = {
                "phone_number": phone,
                "user_message": validated_data.get("body", ""),
                "message_type": message_type,
                "media_url": None,
                "media_id": validated_data.get("media_id"),
                "mime_type": validated_data.get("mime_type"),
                "wamid": message_id,
                "messages": [],
                "user_id": "",
                "subscription_tier": "",
                "is_new_user": False,
                "formatted_response": "",
                "additional_responses": [],
                "response_sent": False,
                "trace_id": trace_id,
                "cost_usd": 0.0,
                "retrieved_sources": [],
                "cited_source_indices": [],
                "web_sources": [],
                "rate_limit_exceeded": False,
                "remaining_daily": 0,
                "rate_limit_warning": "",
                "transcribed_text": "",
                "image_message": None,
                "provider_used": "",
                # Cost tracking fields (Story 7.1)
                "tokens_input": 0,
                "tokens_output": 0,
                "tokens_cache_read": 0,
                "tokens_cache_creation": 0,
                "model_used": "",
                "tool_executions": [],
            }

            # Story 7.2 (AC1/AC4): Langfuse tracing at graph level
            langfuse_handler = get_langfuse_handler(trace_id=trace_id)
            callbacks = [langfuse_handler] if langfuse_handler else []
            invoke_config: dict[str, Any] = {
                "configurable": {"thread_id": phone},
            }
            if callbacks:
                invoke_config["callbacks"] = callbacks

            with propagate_attributes(
                session_id=phone,
                tags=["whatsapp", message_type],
            ):
                result = await graph.ainvoke(initial_state, config=invoke_config)

            # AC4: Update trace with post-execution metadata
            if langfuse_handler:
                update_trace_metadata(
                    trace_id=trace_id,
                    user_id=result.get("user_id", ""),
                    metadata={
                        "subscription_tier": result.get("subscription_tier", ""),
                        "provider_used": result.get("provider_used", ""),
                    },
                )

            logger.info(
                "graph_execution_completed",
                message_id=message_id,
                phone=phone,
                user_id=result.get("user_id"),
            )
        except GraphNodeError as exc:
            logger.critical(
                "graph_node_error",
                message_id=message_id,
                phone=phone,
                user_id=phone,
                user_message=validated_data.get("body", "")[:200],
                node=exc.node,
                error_type=type(exc).__name__,
                exc_info=True,
            )
            try:
                user_obj = await User.objects.filter(phone=phone).afirst()
                await ErrorLog.objects.acreate(
                    user=user_obj,
                    node=exc.node,
                    error_type=type(exc).__name__,
                    error_message=_sanitize_error_msg(str(exc)),
                    trace_id=trace_id,
                )
            except Exception:
                logger.warning("error_log_persist_failed", phone=phone)
            await _send_fallback(phone)
        except Exception as exc:
            logger.critical(
                "graph_execution_error",
                message_id=message_id,
                phone=phone,
                user_id=phone,
                user_message=validated_data.get("body", "")[:200],
                node="unknown",
                error_type=type(exc).__name__,
                exc_info=True,
            )
            try:
                user_obj = await User.objects.filter(phone=phone).afirst()
                await ErrorLog.objects.acreate(
                    user=user_obj,
                    node="unknown",
                    error_type=type(exc).__name__,
                    error_message=_sanitize_error_msg(str(exc)),
                    trace_id=trace_id,
                )
            except Exception:
                logger.warning("error_log_persist_failed", phone=phone)
            await _send_fallback(phone)


@method_decorator(csrf_exempt, name="dispatch")
class WhatsAppWebhookView(APIView):
    """WhatsApp Cloud API webhook endpoint.

    GET: Verification handshake with Meta.
    POST: Receive and process incoming messages (fire-and-forget).
    """

    authentication_classes: list[Any] = []
    permission_classes: list[Any] = []

    async def get(self, request: Request) -> HttpResponse:
        """Handle Meta webhook verification handshake."""
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN:
            logger.info("webhook_verification_success")
            return HttpResponse(challenge, content_type="text/plain", status=200)

        logger.warning("webhook_verification_failed", mode=mode)
        return JsonResponse({"error": "Verification failed"}, status=403)

    async def post(self, request: Request) -> JsonResponse:
        """Receive webhook events and dispatch processing (fire-and-forget)."""
        payload = request.data

        for entry in payload.get("entry", []):
            extractable_messages = should_process_event(entry)

            for msg_data in extractable_messages:
                serializer = WhatsAppMessageSerializer(data=msg_data)
                if not serializer.is_valid():
                    logger.warning(
                        "message_validation_failed",
                        errors=serializer.errors,
                        message_id=msg_data.get("message_id"),
                    )
                    continue

                validated = serializer.validated_data

                if await is_duplicate_message(validated["message_id"]):
                    continue

                message_type = validated["message_type"]
                phone = validated["phone"]

                # Story 10.1: Feature flag routing (Strangler Fig)
                use_new_pipeline = await is_feature_enabled(phone, "new_pipeline")
                if not use_new_pipeline:
                    logger.info("feature_flag_routed", pipeline="n8n", phone=phone)
                    continue
                logger.info("feature_flag_routed", pipeline="new", phone=phone)

                if message_type in UNSUPPORTED_RESPONSE_TYPES:
                    task = asyncio.create_task(_handle_unsupported_message(phone, message_type))
                elif message_type == "interactive":
                    btn_id = validated.get("button_reply_id", "")
                    if btn_id in FEEDBACK_BUTTON_IDS:
                        task = asyncio.create_task(handle_feedback(phone, btn_id))
                    else:
                        logger.debug("unknown_interactive_button", phone=phone, button_id=btn_id)
                        continue
                elif message_type == "text":
                    # Pending comment check: text only (don't consume on audio/image)
                    pending_feedback_id = await get_pending_comment(phone)
                    if pending_feedback_id:
                        body = validated.get("body", "")
                        task = asyncio.create_task(
                            handle_pending_comment(phone, pending_feedback_id, body)
                        )
                    else:
                        task = asyncio.create_task(
                            schedule_processing(phone, validated, _process_message)
                        )
                else:
                    task = asyncio.create_task(
                        schedule_processing(phone, validated, _process_message)
                    )
                task.add_done_callback(_make_task_exception_handler(phone, validated["message_id"]))

        return JsonResponse({"status": "ok"}, status=200)
