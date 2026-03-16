"""Tests for WhatsApp webhook view, serializer, deduplication, and event filtering."""

import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, patch

import pytest
from django.test import AsyncClient

from workflows.serializers import WhatsAppMessageSerializer
from workflows.views import should_process_event

WEBHOOK_SECRET = "test-webhook-secret"
VERIFY_TOKEN = "test-verify-token"


def _sign_payload(body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    """Generate valid HMAC SHA-256 signature for a payload."""
    return (
        "sha256="
        + hmac.new(
            secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
    )


def _make_webhook_payload(
    phone: str = "5511999999999",
    message_id: str = "wamid.test123",
    message_type: str = "text",
    body: str = "Olá Medbrain!",
    timestamp: str | None = None,
) -> dict:
    """Build a realistic WhatsApp webhook payload."""
    if timestamp is None:
        timestamp = str(int(time.time()))

    msg: dict = {
        "from": phone,
        "id": message_id,
        "timestamp": timestamp,
        "type": message_type,
    }
    if message_type == "text":
        msg["text"] = {"body": body}

    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "BUSINESS_ACCOUNT_ID",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": "PHONE_ID",
                            },
                            "contacts": [{"profile": {"name": "Test User"}, "wa_id": phone}],
                            "messages": [msg],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


def _make_status_update_payload() -> dict:
    """Build a WhatsApp status update payload (delivered/read)."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "BUSINESS_ACCOUNT_ID",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": "PHONE_ID",
                            },
                            "statuses": [
                                {
                                    "id": "wamid.status123",
                                    "status": "delivered",
                                    "timestamp": str(int(time.time())),
                                    "recipient_id": "5511999999999",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


async def _post_webhook(client: AsyncClient, payload: dict) -> object:
    """POST a signed webhook payload."""
    body = json.dumps(payload).encode()
    signature = _sign_payload(body)
    return await client.post(
        "/webhook/whatsapp/",
        data=body,
        content_type="application/json",
        headers={"X-Hub-Signature-256": signature},
    )


# ─── Webhook View Tests (AC1, AC3) ───


@pytest.mark.django_db
class TestWhatsAppWebhookGet:
    """Tests for webhook verification handshake (GET)."""

    async def test_valid_handshake_returns_challenge(self):
        """AC3: Valid GET handshake returns 200 + challenge echo."""
        client = AsyncClient()
        response = await client.get(
            "/webhook/whatsapp/",
            {
                "hub.mode": "subscribe",
                "hub.verify_token": VERIFY_TOKEN,
                "hub.challenge": "CHALLENGE_STRING_123",
            },
        )
        assert response.status_code == 200
        assert response.content.decode() == "CHALLENGE_STRING_123"

    async def test_wrong_token_returns_403(self):
        """AC3: Wrong verify token returns 403."""
        client = AsyncClient()
        response = await client.get(
            "/webhook/whatsapp/",
            {
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong-token",
                "hub.challenge": "CHALLENGE_STRING_123",
            },
        )
        assert response.status_code == 403

    async def test_missing_hub_mode_returns_403(self):
        """AC3: Missing hub.mode parameter returns 403."""
        client = AsyncClient()
        response = await client.get(
            "/webhook/whatsapp/",
            {
                "hub.verify_token": VERIFY_TOKEN,
                "hub.challenge": "CHALLENGE_STRING_123",
            },
        )
        assert response.status_code == 403


@pytest.mark.django_db
class TestWhatsAppWebhookPost:
    """Tests for webhook message processing (POST)."""

    @pytest.fixture(autouse=True)
    def _mock_pending_comment(self):
        with patch(
            "workflows.views.get_pending_comment",
            new_callable=AsyncMock,
            return_value=None,
        ):
            yield

    @pytest.fixture(autouse=True)
    def _mock_feature_flag(self):
        with patch(
            "workflows.views.is_feature_enabled",
            new_callable=AsyncMock,
            return_value=True,
        ):
            yield

    @patch("workflows.views.is_duplicate_message", new_callable=AsyncMock, return_value=False)
    @patch("workflows.views.schedule_processing", new_callable=AsyncMock)
    async def test_valid_message_returns_200(self, mock_schedule, mock_dedup):
        """AC1: Valid HMAC + valid message returns 200 OK."""
        client = AsyncClient()
        payload = _make_webhook_payload()
        response = await _post_webhook(client, payload)
        assert response.status_code == 200

    @patch("workflows.views.is_duplicate_message", new_callable=AsyncMock, return_value=True)
    async def test_duplicate_message_ignored(self, mock_dedup):
        """AC1: Duplicate message (same ID) is ignored silently."""
        client = AsyncClient()
        payload = _make_webhook_payload(message_id="wamid.duplicate")

        with patch("workflows.views.schedule_processing", new_callable=AsyncMock) as mock_schedule:
            response = await _post_webhook(client, payload)
            assert response.status_code == 200
            mock_schedule.assert_not_called()

    async def test_status_updates_ignored(self):
        """AC1: Status updates (delivered, read) are filtered and ignored."""
        client = AsyncClient()
        payload = _make_status_update_payload()

        with patch("workflows.views.schedule_processing", new_callable=AsyncMock) as mock_schedule:
            response = await _post_webhook(client, payload)
            assert response.status_code == 200
            mock_schedule.assert_not_called()

    @patch("workflows.views.is_duplicate_message", new_callable=AsyncMock, return_value=False)
    @patch("workflows.views.schedule_processing", new_callable=AsyncMock)
    async def test_system_and_unknown_messages_ignored(self, mock_schedule, mock_dedup):
        """AC1: System and unknown message types are filtered."""
        client = AsyncClient()

        for msg_type in ("system", "unknown"):
            payload = _make_webhook_payload(
                message_type=msg_type,
                message_id=f"wamid.{msg_type}",
            )
            response = await _post_webhook(client, payload)
            assert response.status_code == 200

        mock_schedule.assert_not_called()

    @patch("workflows.views.is_duplicate_message", new_callable=AsyncMock, return_value=False)
    @patch("workflows.views.schedule_processing", new_callable=AsyncMock)
    async def test_multiple_entries_and_changes_processed(self, mock_schedule, mock_dedup):
        """AC1: Multiple entries/changes are all processed (array handling)."""
        client = AsyncClient()
        ts = str(int(time.time()))
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "ACCOUNT_1",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "15551234567",
                                    "phone_number_id": "PHONE_ID",
                                },
                                "messages": [
                                    {
                                        "from": "5511999999991",
                                        "id": "wamid.msg1",
                                        "timestamp": ts,
                                        "type": "text",
                                        "text": {"body": "Msg 1"},
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                },
                {
                    "id": "ACCOUNT_2",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "15551234567",
                                    "phone_number_id": "PHONE_ID",
                                },
                                "messages": [
                                    {
                                        "from": "5511999999992",
                                        "id": "wamid.msg2",
                                        "timestamp": ts,
                                        "type": "text",
                                        "text": {"body": "Msg 2"},
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                },
            ],
        }

        response = await _post_webhook(client, payload)
        assert response.status_code == 200
        assert mock_schedule.call_count == 2

    @patch("workflows.views.is_duplicate_message", new_callable=AsyncMock, return_value=False)
    @patch("workflows.views.schedule_processing", new_callable=AsyncMock)
    async def test_expired_timestamp_rejected(self, mock_schedule, mock_dedup):
        """AC1: Expired timestamp (>300s) message is rejected by serializer."""
        client = AsyncClient()
        payload = _make_webhook_payload(
            timestamp=str(int(time.time()) - 400),
        )
        response = await _post_webhook(client, payload)
        assert response.status_code == 200  # Webhook still returns 200
        mock_schedule.assert_not_called()


# ─── Serializer Tests ───


class TestWhatsAppMessageSerializer:
    """Tests for message validation (phone, timestamp, type)."""

    def test_valid_message(self):
        """Valid message data passes validation."""
        data = {
            "phone": "5511999999999",
            "message_id": "wamid.test123",
            "timestamp": str(int(time.time())),
            "message_type": "text",
            "body": "Hello!",
        }
        serializer = WhatsAppMessageSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_expired_timestamp_rejected(self):
        """Timestamp older than 300s is rejected (anti-replay)."""
        data = {
            "phone": "5511999999999",
            "message_id": "wamid.test123",
            "timestamp": str(int(time.time()) - 400),
            "message_type": "text",
            "body": "Old message",
        }
        serializer = WhatsAppMessageSerializer(data=data)
        assert not serializer.is_valid()
        assert "timestamp" in serializer.errors

    def test_future_timestamp_rejected(self):
        """Timestamp from the future (>300s ahead) is rejected (anti-replay)."""
        data = {
            "phone": "5511999999999",
            "message_id": "wamid.test123",
            "timestamp": str(int(time.time()) + 400),
            "message_type": "text",
            "body": "Future message",
        }
        serializer = WhatsAppMessageSerializer(data=data)
        assert not serializer.is_valid()
        assert "timestamp" in serializer.errors

    def test_system_type_rejected(self):
        """System message type is rejected."""
        data = {
            "phone": "5511999999999",
            "message_id": "wamid.test123",
            "timestamp": str(int(time.time())),
            "message_type": "system",
        }
        serializer = WhatsAppMessageSerializer(data=data)
        assert not serializer.is_valid()
        assert "message_type" in serializer.errors

    def test_unknown_type_rejected(self):
        """Unknown message type is rejected."""
        data = {
            "phone": "5511999999999",
            "message_id": "wamid.test123",
            "timestamp": str(int(time.time())),
            "message_type": "unknown",
        }
        serializer = WhatsAppMessageSerializer(data=data)
        assert not serializer.is_valid()
        assert "message_type" in serializer.errors

    def test_invalid_phone_rejected(self):
        """Phone with letters is rejected."""
        data = {
            "phone": "abc123",
            "message_id": "wamid.test123",
            "timestamp": str(int(time.time())),
            "message_type": "text",
        }
        serializer = WhatsAppMessageSerializer(data=data)
        assert not serializer.is_valid()
        assert "phone" in serializer.errors


# ─── Event Filtering Tests ───


class TestShouldProcessEvent:
    """Tests for should_process_event filtering function."""

    def test_extracts_text_messages(self):
        """Text messages are extracted from entry."""
        entry = {
            "changes": [
                {
                    "value": {
                        "messages": [
                            {
                                "from": "5511999999999",
                                "id": "wamid.1",
                                "timestamp": str(int(time.time())),
                                "type": "text",
                                "text": {"body": "Hello"},
                            }
                        ],
                    }
                }
            ],
        }
        result = should_process_event(entry)
        assert len(result) == 1
        assert result[0]["message_type"] == "text"
        assert result[0]["body"] == "Hello"

    def test_filters_status_updates(self):
        """Status updates (delivered/read) are filtered out."""
        entry = {
            "changes": [
                {
                    "value": {
                        "statuses": [{"id": "wamid.s1", "status": "delivered"}],
                    }
                }
            ],
        }
        result = should_process_event(entry)
        assert len(result) == 0

    def test_filters_system_messages(self):
        """System messages are filtered out."""
        entry = {
            "changes": [
                {
                    "value": {
                        "messages": [
                            {
                                "from": "5511999999999",
                                "id": "wamid.sys",
                                "timestamp": str(int(time.time())),
                                "type": "system",
                            }
                        ],
                    }
                }
            ],
        }
        result = should_process_event(entry)
        assert len(result) == 0

    def test_filters_unknown_messages(self):
        """Unknown message types are filtered out."""
        entry = {
            "changes": [
                {
                    "value": {
                        "messages": [
                            {
                                "from": "5511999999999",
                                "id": "wamid.unk",
                                "timestamp": str(int(time.time())),
                                "type": "unknown",
                            }
                        ],
                    }
                }
            ],
        }
        result = should_process_event(entry)
        assert len(result) == 0

    def test_multiple_messages_in_changes(self):
        """Multiple messages across changes are all extracted."""
        ts = str(int(time.time()))
        entry = {
            "changes": [
                {
                    "value": {
                        "messages": [
                            {
                                "from": "5511111111111",
                                "id": "wamid.a",
                                "timestamp": ts,
                                "type": "text",
                                "text": {"body": "A"},
                            },
                            {
                                "from": "5522222222222",
                                "id": "wamid.b",
                                "timestamp": ts,
                                "type": "text",
                                "text": {"body": "B"},
                            },
                        ],
                    }
                },
                {
                    "value": {
                        "messages": [
                            {
                                "from": "5533333333333",
                                "id": "wamid.c",
                                "timestamp": ts,
                                "type": "text",
                                "text": {"body": "C"},
                            },
                        ],
                    }
                },
            ],
        }
        result = should_process_event(entry)
        assert len(result) == 3


# ─── Media ID Extraction Tests (Story 0.1, AC2) ───


class TestMediaIdExtraction:
    """Tests for media_id and mime_type extraction from webhook payload."""

    def test_audio_payload_extracts_media_id(self):
        """AC2: Audio message extracts media_id and mime_type."""
        ts = str(int(time.time()))
        entry = {
            "changes": [
                {
                    "value": {
                        "messages": [
                            {
                                "from": "5511999999999",
                                "id": "wamid.audio1",
                                "timestamp": ts,
                                "type": "audio",
                                "audio": {
                                    "id": "media-audio-123",
                                    "mime_type": "audio/ogg; codecs=opus",
                                },
                            }
                        ],
                    }
                }
            ],
        }
        result = should_process_event(entry)
        assert len(result) == 1
        assert result[0]["media_id"] == "media-audio-123"
        assert result[0]["mime_type"] == "audio/ogg; codecs=opus"
        assert result[0]["message_type"] == "audio"

    def test_image_payload_extracts_media_id(self):
        """AC2: Image message extracts media_id and mime_type."""
        ts = str(int(time.time()))
        entry = {
            "changes": [
                {
                    "value": {
                        "messages": [
                            {
                                "from": "5511999999999",
                                "id": "wamid.image1",
                                "timestamp": ts,
                                "type": "image",
                                "image": {
                                    "id": "media-image-456",
                                    "mime_type": "image/jpeg",
                                },
                            }
                        ],
                    }
                }
            ],
        }
        result = should_process_event(entry)
        assert len(result) == 1
        assert result[0]["media_id"] == "media-image-456"
        assert result[0]["mime_type"] == "image/jpeg"
        assert result[0]["message_type"] == "image"

    def test_text_payload_has_no_media_id(self):
        """AC2: Text message has media_id=None."""
        ts = str(int(time.time()))
        entry = {
            "changes": [
                {
                    "value": {
                        "messages": [
                            {
                                "from": "5511999999999",
                                "id": "wamid.text1",
                                "timestamp": ts,
                                "type": "text",
                                "text": {"body": "Hello"},
                            }
                        ],
                    }
                }
            ],
        }
        result = should_process_event(entry)
        assert len(result) == 1
        assert result[0]["media_id"] is None
        assert result[0]["mime_type"] is None


# ─── Unsupported Message Type Tests (AC5, AC6) ───


@pytest.mark.django_db
class TestUnsupportedMessageTypes:
    """Tests for unsupported message type handling (AC5, AC6)."""

    @pytest.fixture(autouse=True)
    def _mock_pending_comment(self):
        with patch(
            "workflows.views.get_pending_comment",
            new_callable=AsyncMock,
            return_value=None,
        ):
            yield

    @pytest.fixture(autouse=True)
    def _mock_feature_flag(self):
        with patch(
            "workflows.views.is_feature_enabled",
            new_callable=AsyncMock,
            return_value=True,
        ):
            yield

    @pytest.mark.parametrize("msg_type", ["sticker", "location", "document", "contacts", "video"])
    @patch("workflows.views.is_duplicate_message", new_callable=AsyncMock, return_value=False)
    @patch("workflows.views._handle_unsupported_message", new_callable=AsyncMock)
    @patch("workflows.views.schedule_processing", new_callable=AsyncMock)
    async def test_unsupported_type_triggers_handler(
        self, mock_schedule, mock_handle, mock_dedup, msg_type
    ):
        """AC5: Unsupported message type → _handle_unsupported_message called."""
        client = AsyncClient()
        payload = _make_webhook_payload(
            message_type=msg_type,
            message_id=f"wamid.{msg_type}_test",
        )
        response = await _post_webhook(client, payload)

        assert response.status_code == 200
        mock_handle.assert_called_once()
        assert mock_handle.call_args[0][1] == msg_type
        mock_schedule.assert_not_called()

    @patch("workflows.views.is_duplicate_message", new_callable=AsyncMock, return_value=False)
    @patch("workflows.views._handle_unsupported_message", new_callable=AsyncMock)
    @patch("workflows.views.schedule_processing", new_callable=AsyncMock)
    @patch("workflows.views.get_pending_comment", new_callable=AsyncMock, return_value=None)
    async def test_text_message_does_not_trigger_unsupported_handler(
        self, mock_pending, mock_schedule, mock_handle, mock_dedup
    ):
        """AC5: Text message → NÃO envia unsupported message."""
        client = AsyncClient()
        payload = _make_webhook_payload(message_type="text")
        response = await _post_webhook(client, payload)

        assert response.status_code == 200
        mock_handle.assert_not_called()

    @patch("workflows.views.is_duplicate_message", new_callable=AsyncMock, return_value=False)
    @patch("workflows.views._handle_unsupported_message", new_callable=AsyncMock)
    @patch("workflows.views.schedule_processing", new_callable=AsyncMock)
    async def test_unsupported_type_does_not_invoke_graph(
        self, mock_schedule, mock_handle, mock_dedup
    ):
        """AC5: Unsupported type NÃO invoca o grafo LangGraph (schedule_processing not called)."""
        client = AsyncClient()
        payload = _make_webhook_payload(
            message_type="sticker",
            message_id="wamid.sticker_no_graph",
        )
        response = await _post_webhook(client, payload)

        assert response.status_code == 200
        mock_schedule.assert_not_called()


# ─── Unit Tests for _handle_unsupported_message (AC5, AC6) ───


class TestHandleUnsupportedMessageUnit:
    """Direct unit tests for _handle_unsupported_message logic."""

    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    @patch("workflows.views.ConfigService")
    async def test_loads_text_from_config_and_sends(self, mock_config, mock_send):
        """AC6: Carrega texto do ConfigService e envia via send_text_message."""
        from workflows.views import _handle_unsupported_message

        mock_config.get = AsyncMock(return_value="Texto customizado do admin")
        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}

        await _handle_unsupported_message("5511999999999", "sticker")

        mock_config.get.assert_awaited_once_with("message:unsupported_type")
        mock_send.assert_awaited_once_with("5511999999999", "Texto customizado do admin")

    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    @patch("workflows.views.ConfigService")
    async def test_config_failure_uses_default_text(self, mock_config, mock_send):
        """AC6: ConfigService falha → usa texto default hardcoded."""
        from workflows.views import DEFAULT_UNSUPPORTED_MESSAGE, _handle_unsupported_message

        mock_config.get = AsyncMock(side_effect=Exception("Config unavailable"))
        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}

        await _handle_unsupported_message("5511999999999", "video")

        mock_send.assert_awaited_once_with("5511999999999", DEFAULT_UNSUPPORTED_MESSAGE)

    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    @patch("workflows.views.ConfigService")
    async def test_send_failure_is_best_effort(self, mock_config, mock_send):
        """AC5: Falha no envio não re-raise — best-effort."""
        from workflows.views import _handle_unsupported_message

        mock_config.get = AsyncMock(return_value="Texto")
        mock_send.side_effect = Exception("WhatsApp API down")

        # Should NOT raise
        await _handle_unsupported_message("5511999999999", "location")


# ─── Feature Flag Routing Tests (Story 10.1) ───


@pytest.mark.django_db
class TestFeatureFlagRouting:
    """Tests for feature flag-based traffic routing (Story 10.1)."""

    @pytest.fixture(autouse=True)
    def _mock_pending_comment(self):
        with patch(
            "workflows.views.get_pending_comment",
            new_callable=AsyncMock,
            return_value=None,
        ):
            yield

    @patch("workflows.views.is_duplicate_message", new_callable=AsyncMock, return_value=False)
    @patch("workflows.views.is_feature_enabled", new_callable=AsyncMock, return_value=False)
    @patch("workflows.views.schedule_processing", new_callable=AsyncMock)
    async def test_feature_flag_off_skips_processing(self, mock_schedule, mock_ff, mock_dedup):
        """AC2/AC3: Feature flag off → message not processed (n8n handles)."""
        client = AsyncClient()
        payload = _make_webhook_payload()
        response = await _post_webhook(client, payload)

        assert response.status_code == 200
        mock_ff.assert_awaited_once()
        mock_schedule.assert_not_called()

    @patch("workflows.views.is_duplicate_message", new_callable=AsyncMock, return_value=False)
    @patch("workflows.views.is_feature_enabled", new_callable=AsyncMock, return_value=True)
    @patch("workflows.views.schedule_processing", new_callable=AsyncMock)
    async def test_feature_flag_on_processes_message(self, mock_schedule, mock_ff, mock_dedup):
        """AC2: Feature flag on → message processed via new pipeline."""
        client = AsyncClient()
        payload = _make_webhook_payload()
        response = await _post_webhook(client, payload)

        assert response.status_code == 200
        mock_ff.assert_awaited_once()
        mock_schedule.assert_called_once()

    @patch("workflows.views.is_duplicate_message", new_callable=AsyncMock, return_value=False)
    @patch("workflows.views.is_feature_enabled", new_callable=AsyncMock, return_value=False)
    @patch("workflows.views._handle_unsupported_message", new_callable=AsyncMock)
    @patch("workflows.views.schedule_processing", new_callable=AsyncMock)
    async def test_feature_flag_off_skips_unsupported_handler(
        self, mock_schedule, mock_handle, mock_ff, mock_dedup
    ):
        """AC2: Feature flag off → even unsupported types are skipped (n8n handles)."""
        client = AsyncClient()
        payload = _make_webhook_payload(message_type="sticker", message_id="wamid.sticker_ff")
        response = await _post_webhook(client, payload)

        assert response.status_code == 200
        mock_handle.assert_not_called()
        mock_schedule.assert_not_called()

    @patch("workflows.views.is_duplicate_message", new_callable=AsyncMock, return_value=False)
    @patch("workflows.views.is_feature_enabled", new_callable=AsyncMock, return_value=True)
    @patch("workflows.views.schedule_processing", new_callable=AsyncMock)
    async def test_feature_flag_called_with_phone_and_new_pipeline(
        self, mock_schedule, mock_ff, mock_dedup
    ):
        """AC1: is_feature_enabled called with phone and 'new_pipeline'."""
        client = AsyncClient()
        payload = _make_webhook_payload(phone="5511888888888")
        response = await _post_webhook(client, payload)

        assert response.status_code == 200
        mock_ff.assert_awaited_once_with("5511888888888", "new_pipeline")
