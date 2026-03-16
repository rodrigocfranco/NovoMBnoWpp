"""Tests for WhatsApp Cloud API client (AC3, AC6)."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from workflows.providers.whatsapp import (
    _get_client,
    download_media,
    mark_as_read,
    send_interactive_buttons,
    send_text_message,
)
from workflows.utils.errors import ExternalServiceError


class TestGetClient:
    """Tests for _get_client singleton."""

    def setup_method(self):
        import workflows.providers.whatsapp as mod

        self._original = mod._client
        mod._client = None

    def teardown_method(self):
        import workflows.providers.whatsapp as mod

        mod._client = self._original

    @patch("workflows.providers.whatsapp._get_whatsapp_timeout", new_callable=AsyncMock)
    async def test_returns_async_client(self, mock_timeout):
        """AC6: _get_client retorna httpx.AsyncClient."""
        mock_timeout.return_value = 10.0
        client = await _get_client()
        assert isinstance(client, httpx.AsyncClient)

    @patch("workflows.providers.whatsapp._get_whatsapp_timeout", new_callable=AsyncMock)
    async def test_singleton_returns_same_instance(self, mock_timeout):
        """AC6: _get_client retorna singleton."""
        mock_timeout.return_value = 10.0
        c1 = await _get_client()
        c2 = await _get_client()
        assert c1 is c2

    @patch("workflows.providers.whatsapp._get_whatsapp_timeout", new_callable=AsyncMock)
    async def test_client_has_correct_timeout(self, mock_timeout):
        """AC6: Client tem timeout de 10s."""
        mock_timeout.return_value = 10.0
        client = await _get_client()
        assert client.timeout.connect == 10.0
        assert client.timeout.read == 10.0

    @patch("workflows.providers.whatsapp._get_whatsapp_timeout", new_callable=AsyncMock)
    async def test_client_has_auth_header(self, mock_timeout):
        """AC6: Client tem Bearer token de autenticação."""
        mock_timeout.return_value = 10.0
        client = await _get_client()
        assert "Authorization" in client.headers
        assert client.headers["Authorization"].startswith("Bearer ")


def _make_mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    """Create a mock httpx.Response with sync methods."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


class TestSendTextMessage:
    """Tests for send_text_message function."""

    @pytest.fixture(autouse=True)
    def _reset_client(self):
        import workflows.providers.whatsapp as mod

        original = mod._client
        mod._client = None
        yield
        mod._client = original

    @patch("workflows.providers.whatsapp._get_client")
    async def test_sends_correct_payload(self, mock_get_client):
        """AC6: send_text_message faz POST correto."""
        response_data = {
            "messaging_product": "whatsapp",
            "contacts": [{"input": "5511999999999", "wa_id": "5511999999999"}],
            "messages": [{"id": "wamid.HBg123", "message_status": "accepted"}],
        }
        mock_response = _make_mock_response(response_data)

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = await send_text_message("5511999999999", "Hello World")

        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs["json"]
        assert payload["messaging_product"] == "whatsapp"
        assert payload["to"] == "5511999999999"
        assert payload["type"] == "text"
        assert payload["text"]["body"] == "Hello World"
        assert result["messages"][0]["id"] == "wamid.HBg123"

    @patch("workflows.providers.whatsapp._get_client")
    async def test_strips_plus_from_phone(self, mock_get_client):
        """AC6: Remove + do número de telefone."""
        response_data = {"messages": [{"id": "wamid.test"}]}
        mock_response = _make_mock_response(response_data)
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        await send_text_message("+5511999999999", "test")

        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["to"] == "5511999999999"

    @patch("workflows.providers.whatsapp._get_client")
    async def test_http_500_raises_external_service_error(self, mock_get_client):
        """AC6: Erro HTTP 500 dispara ExternalServiceError."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.HTTPStatusError(
            "Server Error",
            request=httpx.Request("POST", "https://example.com"),
            response=httpx.Response(500, text="Internal Server Error"),
        )
        mock_get_client.return_value = mock_client

        with pytest.raises(ExternalServiceError) as exc_info:
            await send_text_message("5511999999999", "test")

        assert "whatsapp" in str(exc_info.value).lower()

    @patch("workflows.providers.whatsapp._get_client")
    async def test_timeout_raises_external_service_error(self, mock_get_client):
        """AC6: Timeout dispara ExternalServiceError."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("Connection timeout")
        mock_get_client.return_value = mock_client

        with pytest.raises(ExternalServiceError) as exc_info:
            await send_text_message("5511999999999", "test")

        assert "timeout" in str(exc_info.value).lower()


class TestMarkAsRead:
    """Tests for mark_as_read function."""

    @pytest.fixture(autouse=True)
    def _reset_client(self):
        import workflows.providers.whatsapp as mod

        original = mod._client
        mod._client = None
        yield
        mod._client = original

    @patch("workflows.providers.whatsapp._get_client")
    async def test_sends_correct_payload(self, mock_get_client):
        """AC6: mark_as_read envia payload correto."""
        mock_response = _make_mock_response({})
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = await mark_as_read("wamid.HBg123")

        assert result is True
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["messaging_product"] == "whatsapp"
        assert payload["status"] == "read"
        assert payload["message_id"] == "wamid.HBg123"

    @patch("workflows.providers.whatsapp._get_client")
    async def test_returns_false_on_error(self, mock_get_client):
        """AC6: mark_as_read retorna False em caso de erro (best-effort)."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("timeout")
        mock_get_client.return_value = mock_client

        result = await mark_as_read("wamid.HBg123")

        assert result is False


class TestDownloadMedia:
    """Tests for download_media function (AC3 — Story 0.1)."""

    @pytest.fixture(autouse=True)
    def _reset_client(self):
        import workflows.providers.whatsapp as mod

        original = mod._client
        mod._client = None
        yield
        mod._client = original

    @patch("workflows.providers.whatsapp._get_client")
    async def test_download_success(self, mock_get_client):
        """AC3: Download de mídia com sucesso retorna (bytes, mime_type)."""
        media_url_response = _make_mock_response({"url": "https://media.example.com/file"})
        media_content_response = MagicMock(spec=httpx.Response)
        media_content_response.status_code = 200
        media_content_response.content = b"audio-binary-data"
        media_content_response.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.get.side_effect = [media_url_response, media_content_response]
        mock_get_client.return_value = mock_client

        content, mime = await download_media("media-123", "audio/ogg")

        assert content == b"audio-binary-data"
        assert mime == "audio/ogg"
        assert mock_client.get.call_count == 2

    @patch("workflows.providers.whatsapp._get_client")
    async def test_download_404_raises_external_service_error(self, mock_get_client):
        """AC3: Media expirada (404) raises ExternalServiceError."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.HTTPStatusError(
            "Not Found",
            request=httpx.Request("GET", "https://example.com"),
            response=httpx.Response(404, text="Media not found"),
        )
        mock_get_client.return_value = mock_client

        with pytest.raises(ExternalServiceError) as exc_info:
            await download_media("media-expired", "audio/ogg")

        assert "whatsapp" in str(exc_info.value).lower()

    @patch("workflows.providers.whatsapp._get_client")
    async def test_download_timeout_raises_external_service_error(self, mock_get_client):
        """AC3: Timeout no download raises ExternalServiceError."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("Connection timeout")
        mock_get_client.return_value = mock_client

        with pytest.raises(ExternalServiceError) as exc_info:
            await download_media("media-timeout", "image/jpeg")

        assert "timeout" in str(exc_info.value).lower()

    @patch("workflows.providers.whatsapp._get_client")
    async def test_download_step2_403_raises_external_service_error(self, mock_get_client):
        """AC3: Step 1 OK mas URL temporária expirada (403) raises ExternalServiceError."""
        media_url_response = _make_mock_response({"url": "https://media.example.com/expired"})
        mock_client = AsyncMock()
        mock_client.get.side_effect = [
            media_url_response,
            httpx.HTTPStatusError(
                "Forbidden",
                request=httpx.Request("GET", "https://media.example.com/expired"),
                response=httpx.Response(403, text="URL expired"),
            ),
        ]
        mock_get_client.return_value = mock_client

        with pytest.raises(ExternalServiceError) as exc_info:
            await download_media("media-step2-403", "audio/ogg")

        assert "whatsapp" in str(exc_info.value).lower()

    @patch("workflows.providers.whatsapp._get_client")
    async def test_download_step2_timeout_raises_external_service_error(self, mock_get_client):
        """AC3: Step 1 OK mas timeout no download binário raises ExternalServiceError."""
        media_url_response = _make_mock_response({"url": "https://media.example.com/file"})
        mock_client = AsyncMock()
        mock_client.get.side_effect = [
            media_url_response,
            httpx.TimeoutException("Download timeout"),
        ]
        mock_get_client.return_value = mock_client

        with pytest.raises(ExternalServiceError) as exc_info:
            await download_media("media-step2-timeout", "image/jpeg")

        assert "timeout" in str(exc_info.value).lower()

    @patch("workflows.providers.whatsapp._get_client")
    async def test_download_missing_url_key_raises_external_service_error(self, mock_get_client):
        """AC3: API retorna JSON sem key 'url' raises ExternalServiceError."""
        media_url_response = _make_mock_response({"error": "invalid media"})
        mock_client = AsyncMock()
        mock_client.get.return_value = media_url_response
        mock_get_client.return_value = mock_client

        with pytest.raises(ExternalServiceError) as exc_info:
            await download_media("media-no-url", "audio/ogg")

        assert "url" in str(exc_info.value).lower()


class TestSendInteractiveButtons:
    """Tests for send_interactive_buttons (Story 6.1, AC #1)."""

    @pytest.fixture(autouse=True)
    def _reset_client(self):
        import workflows.providers.whatsapp as mod

        original = mod._client
        mod._client = None
        yield
        mod._client = original

    @patch("workflows.providers.whatsapp._get_client")
    async def test_sends_correct_interactive_payload(self, mock_get_client):
        """AC1: Payload interativo com Reply Buttons correto."""
        response_data = {"messages": [{"id": "wamid.btn123"}]}
        mock_response = _make_mock_response(response_data)
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        buttons = [
            {"id": "feedback_positive", "title": "Útil"},
            {"id": "feedback_negative", "title": "Não útil"},
        ]
        result = await send_interactive_buttons("5511999999999", "Avalie:", buttons)

        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["messaging_product"] == "whatsapp"
        assert payload["to"] == "5511999999999"
        assert payload["type"] == "interactive"
        interactive = payload["interactive"]
        assert interactive["type"] == "button"
        assert interactive["body"]["text"] == "Avalie:"
        assert len(interactive["action"]["buttons"]) == 2
        assert interactive["action"]["buttons"][0]["type"] == "reply"
        assert interactive["action"]["buttons"][0]["reply"]["id"] == "feedback_positive"
        assert result["messages"][0]["id"] == "wamid.btn123"

    @patch("workflows.providers.whatsapp._get_client")
    async def test_strips_plus_from_phone(self, mock_get_client):
        """AC1: Remove + do número de telefone."""
        mock_response = _make_mock_response({"messages": [{"id": "wamid.test"}]})
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        await send_interactive_buttons("+5511999999999", "Avalie:", [{"id": "a", "title": "A"}])

        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["to"] == "5511999999999"

    @patch("workflows.providers.whatsapp._get_client")
    async def test_includes_footer_when_provided(self, mock_get_client):
        """AC1: Footer opcional incluído no payload."""
        mock_response = _make_mock_response({"messages": [{"id": "wamid.test"}]})
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        await send_interactive_buttons(
            "5511999999999", "Avalie:", [{"id": "a", "title": "A"}], footer_text="Medbrain"
        )

        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["interactive"]["footer"]["text"] == "Medbrain"

    @patch("workflows.providers.whatsapp._get_client")
    async def test_no_footer_when_not_provided(self, mock_get_client):
        """AC1: Sem footer quando não fornecido."""
        mock_response = _make_mock_response({"messages": [{"id": "wamid.test"}]})
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        await send_interactive_buttons("5511999999999", "Avalie:", [{"id": "a", "title": "A"}])

        payload = mock_client.post.call_args.kwargs["json"]
        assert "footer" not in payload["interactive"]

    @patch("workflows.providers.whatsapp._get_client")
    async def test_truncates_body_to_1024(self, mock_get_client):
        """AC1: Body truncado em 1024 chars (constraint da API)."""
        mock_response = _make_mock_response({"messages": [{"id": "wamid.test"}]})
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        long_body = "x" * 2000
        await send_interactive_buttons("5511999999999", long_body, [{"id": "a", "title": "A"}])

        payload = mock_client.post.call_args.kwargs["json"]
        assert len(payload["interactive"]["body"]["text"]) == 1024

    @patch("workflows.providers.whatsapp._get_client")
    async def test_truncates_button_title_to_20(self, mock_get_client):
        """AC1: Título do botão truncado em 20 chars (constraint da API)."""
        mock_response = _make_mock_response({"messages": [{"id": "wamid.test"}]})
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        buttons = [{"id": "test", "title": "A" * 30}]
        await send_interactive_buttons("5511999999999", "Avalie:", buttons)

        payload = mock_client.post.call_args.kwargs["json"]
        assert len(payload["interactive"]["action"]["buttons"][0]["reply"]["title"]) == 20

    @patch("workflows.providers.whatsapp._get_client")
    async def test_http_error_raises_external_service_error(self, mock_get_client):
        """AC1: HTTP error raises ExternalServiceError."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.HTTPStatusError(
            "Server Error",
            request=httpx.Request("POST", "https://example.com"),
            response=httpx.Response(500, text="Internal Server Error"),
        )
        mock_get_client.return_value = mock_client

        with pytest.raises(ExternalServiceError):
            await send_interactive_buttons("5511999999999", "Avalie:", [{"id": "a", "title": "A"}])

    @patch("workflows.providers.whatsapp._get_client")
    async def test_timeout_raises_external_service_error(self, mock_get_client):
        """AC1: Timeout raises ExternalServiceError."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("timeout")
        mock_get_client.return_value = mock_client

        with pytest.raises(ExternalServiceError):
            await send_interactive_buttons("5511999999999", "Avalie:", [{"id": "a", "title": "A"}])
