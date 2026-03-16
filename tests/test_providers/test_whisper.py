"""Tests for Whisper audio transcription provider (AC #1, #2 — Story 3.1)."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from workflows.providers.whisper import transcribe_audio
from workflows.utils.errors import ExternalServiceError


def _make_mock_response(text: str = "Transcrição do áudio", status_code: int = 200):
    """Create a mock httpx.Response for Whisper API."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text
    resp.raise_for_status.return_value = None
    return resp


class TestTranscribeAudio:
    """Tests for transcribe_audio function."""

    @patch("workflows.providers.whisper.httpx.AsyncClient")
    async def test_transcription_success(self, mock_client_cls):
        """AC1: Transcrição de áudio com sucesso retorna texto."""
        mock_response = _make_mock_response("Olá, como vai?")
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await transcribe_audio(b"fake-audio-bytes", "audio/ogg; codecs=opus")

        assert result == "Olá, como vai?"
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert call_kwargs.args[0] == "https://api.openai.com/v1/audio/transcriptions"
        assert call_kwargs.kwargs["data"]["model"] == "whisper-1"
        assert call_kwargs.kwargs["data"]["language"] == "pt"
        assert call_kwargs.kwargs["data"]["response_format"] == "text"

    @patch("workflows.providers.whisper.httpx.AsyncClient")
    async def test_transcription_strips_whitespace(self, mock_client_cls):
        """AC1: Transcrição remove espaços extras no início/fim."""
        mock_response = _make_mock_response("  texto com espaços  \n")
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await transcribe_audio(b"audio-data", "audio/ogg")

        assert result == "texto com espaços"

    @patch("workflows.providers.whisper.httpx.AsyncClient")
    async def test_http_4xx_error_does_not_retry(self, mock_client_cls):
        """AC2: Erro HTTP 4xx (não-retentável) falha imediatamente sem retry."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.HTTPStatusError(
            "Bad Request",
            request=httpx.Request("POST", "https://api.openai.com"),
            response=httpx.Response(400, text="Invalid audio format"),
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(ExternalServiceError) as exc_info:
            await transcribe_audio(b"bad-audio", "audio/ogg")

        assert "whisper" in str(exc_info.value).lower()
        # 4xx errors are not retryable — only 1 call
        assert mock_client.post.call_count == 1

    @patch("workflows.providers.whisper.httpx.AsyncClient")
    async def test_timeout_raises_external_service_error(self, mock_client_cls):
        """AC2: Timeout após retries dispara ExternalServiceError."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("Connection timeout")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(ExternalServiceError) as exc_info:
            await transcribe_audio(b"audio-data", "audio/ogg")

        assert "timeout" in str(exc_info.value).lower()
        assert mock_client.post.call_count == 3

    @patch("workflows.providers.whisper.httpx.AsyncClient")
    async def test_retry_succeeds_on_second_attempt(self, mock_client_cls):
        """AC1: Retry funciona — falha no primeiro, sucesso no segundo."""
        mock_response = _make_mock_response("Texto transcrito")
        mock_client = AsyncMock()
        mock_client.post.side_effect = [
            httpx.TimeoutException("timeout"),
            mock_response,
        ]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await transcribe_audio(b"audio-data", "audio/ogg")

        assert result == "Texto transcrito"
        assert mock_client.post.call_count == 2

    @patch("workflows.providers.whisper.httpx.AsyncClient")
    async def test_sends_correct_mime_type_filename(self, mock_client_cls):
        """AC1: Arquivo enviado com filename correto baseado no mime_type."""
        mock_response = _make_mock_response("texto")
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await transcribe_audio(b"audio-data", "audio/ogg; codecs=opus")

        call_kwargs = mock_client.post.call_args
        files = call_kwargs.kwargs["files"]
        filename = files["file"][0]
        assert filename == "audio.ogg"

    @patch("workflows.providers.whisper.httpx.AsyncClient")
    async def test_uses_bearer_auth(self, mock_client_cls):
        """AC1: Request usa Authorization: Bearer {OPENAI_API_KEY}."""
        mock_response = _make_mock_response("texto")
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await transcribe_audio(b"audio-data", "audio/ogg")

        call_kwargs = mock_client.post.call_args
        headers = call_kwargs.kwargs["headers"]
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")

    @patch("workflows.providers.whisper.httpx.AsyncClient")
    async def test_http_500_retries_and_raises(self, mock_client_cls):
        """AC2: Erro HTTP 500 retenta e finalmente dispara ExternalServiceError."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.HTTPStatusError(
            "Server Error",
            request=httpx.Request("POST", "https://api.openai.com"),
            response=httpx.Response(500, text="Internal Server Error"),
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(ExternalServiceError) as exc_info:
            await transcribe_audio(b"audio-data", "audio/ogg")

        assert "500" in str(exc_info.value)
        assert mock_client.post.call_count == 3

    @patch("workflows.providers.whisper.httpx.AsyncClient")
    async def test_http_429_retries_and_raises(self, mock_client_cls):
        """AC2: Erro HTTP 429 (rate limit) retenta e finalmente dispara ExternalServiceError."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.HTTPStatusError(
            "Too Many Requests",
            request=httpx.Request("POST", "https://api.openai.com"),
            response=httpx.Response(429, text="Rate limit exceeded"),
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(ExternalServiceError) as exc_info:
            await transcribe_audio(b"audio-data", "audio/ogg")

        assert "429" in str(exc_info.value)
        # 429 is retryable: 1 initial + 2 retries = 3 calls
        assert mock_client.post.call_count == 3

    @patch("workflows.providers.whisper.httpx.AsyncClient")
    async def test_connect_error_retries_and_raises(self, mock_client_cls):
        """AC2: Erro de conexão (DNS/refused) retenta e dispara ExternalServiceError."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError("DNS resolution failed")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(ExternalServiceError) as exc_info:
            await transcribe_audio(b"audio-data", "audio/ogg")

        assert "connection" in str(exc_info.value).lower()
        assert mock_client.post.call_count == 3
