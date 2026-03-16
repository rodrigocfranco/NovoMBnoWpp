"""Tests for process_media graph node (Story 3.1 audio + Story 3.2 image)."""

from unittest.mock import AsyncMock, patch

import pytest

from workflows.utils.errors import ExternalServiceError, GraphNodeError
from workflows.whatsapp.nodes.process_media import (
    IMAGE_DEFAULT_PROMPT,
    IMAGE_FAILURE_MESSAGE,
    IMAGE_MAX_BYTES,
    IMAGE_TOO_LARGE_MESSAGE,
    IMAGE_UNSUPPORTED_TYPE_MESSAGE,
    process_media,
)


def _make_state(**overrides) -> dict:
    """Thin wrapper over shared make_whatsapp_state with process_media defaults."""
    from tests.test_whatsapp.conftest import make_whatsapp_state

    defaults = {"user_message": "", "user_id": "user-1", "cost_usd": 0.0}
    defaults.update(overrides)
    return make_whatsapp_state(**defaults)


class TestProcessMediaTextMessage:
    """Tests for text message handling (AC #3)."""

    async def test_text_message_returns_empty_dict(self):
        """AC3: Mensagem de texto retorna {} (no-op, zero overhead)."""
        state = _make_state(message_type="text", user_message="Olá")
        result = await process_media(state)
        assert result == {}

    async def test_text_message_does_not_modify_state(self):
        """AC3: Mensagem de texto não modifica nenhum campo do estado."""
        state = _make_state(message_type="text", user_message="Qual é a dose?")
        result = await process_media(state)
        assert "transcribed_text" not in result
        assert "user_message" not in result


class TestProcessMediaImageMessage:
    """Tests for image message handling (Story 3.2 — AC #1, #4, #5, #6)."""

    @patch(
        "workflows.whatsapp.nodes.process_media.download_media",
        new_callable=AsyncMock,
    )
    async def test_image_valid_returns_content_blocks(self, mock_download):
        """AC1: Imagem válida retorna image_message com content blocks base64."""
        fake_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        mock_download.return_value = (fake_bytes, "image/png")

        state = _make_state(
            message_type="image",
            media_id="img-123",
            mime_type="image/png",
        )
        result = await process_media(state)

        assert "image_message" in result
        blocks = result["image_message"]
        assert len(blocks) == 2
        assert blocks[0]["type"] == "image"
        assert blocks[0]["source"]["type"] == "base64"
        assert blocks[0]["source"]["media_type"] == "image/png"
        assert isinstance(blocks[0]["source"]["data"], str)
        assert blocks[1]["type"] == "text"

    async def test_text_message_returns_empty_dict_not_image(self):
        """AC1: message_type='text' retorna {} (no-op)."""
        state = _make_state(message_type="text")
        result = await process_media(state)
        assert result == {}

    @patch(
        "workflows.whatsapp.nodes.process_media.transcribe_audio",
        new_callable=AsyncMock,
    )
    @patch(
        "workflows.whatsapp.nodes.process_media.download_media",
        new_callable=AsyncMock,
    )
    async def test_audio_message_not_handled_as_image(self, mock_download, mock_transcribe):
        """AC1: message_type='audio' não entra no branch de imagem."""
        mock_download.return_value = (b"audio-bytes", "audio/ogg")
        mock_transcribe.return_value = "transcrição"

        state = _make_state(
            message_type="audio",
            media_id="media-check",
            mime_type="audio/ogg",
        )
        result = await process_media(state)
        assert "image_message" not in result
        assert "transcribed_text" in result

    @patch(
        "workflows.whatsapp.nodes.process_media.download_media",
        new_callable=AsyncMock,
    )
    async def test_image_with_caption_combines_text(self, mock_download):
        """AC4: Imagem com caption combina texto + imagem."""
        fake_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 50
        mock_download.return_value = (fake_bytes, "image/jpeg")

        state = _make_state(
            message_type="image",
            media_id="img-caption",
            mime_type="image/jpeg",
            user_message="O que é essa lesão?",
        )
        result = await process_media(state)

        blocks = result["image_message"]
        assert blocks[1]["text"] == "O que é essa lesão?"

    @patch(
        "workflows.whatsapp.nodes.process_media.download_media",
        new_callable=AsyncMock,
    )
    async def test_image_without_caption_uses_default_prompt(self, mock_download):
        """AC4: Imagem sem caption usa prompt padrão."""
        fake_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 50
        mock_download.return_value = (fake_bytes, "image/jpeg")

        state = _make_state(
            message_type="image",
            media_id="img-no-caption",
            mime_type="image/jpeg",
            user_message="",
        )
        result = await process_media(state)

        blocks = result["image_message"]
        assert blocks[1]["text"] == IMAGE_DEFAULT_PROMPT

    @patch(
        "workflows.whatsapp.nodes.process_media.download_media",
        new_callable=AsyncMock,
    )
    async def test_image_download_failure_returns_fallback(self, mock_download):
        """AC5: Download falha retorna mensagem de fallback."""
        mock_download.side_effect = ExternalServiceError(
            service="whatsapp",
            message="HTTP 404",
        )

        state = _make_state(
            message_type="image",
            media_id="img-fail",
            mime_type="image/jpeg",
        )
        result = await process_media(state)

        assert "image_message" not in result
        assert result["user_message"] == IMAGE_FAILURE_MESSAGE

    @patch(
        "workflows.whatsapp.nodes.process_media.download_media",
        new_callable=AsyncMock,
    )
    async def test_image_too_large_returns_limit_message(self, mock_download):
        """AC6: Imagem > 5MB retorna mensagem de limite."""
        large_bytes = b"\x00" * (IMAGE_MAX_BYTES + 1)
        mock_download.return_value = (large_bytes, "image/jpeg")

        state = _make_state(
            message_type="image",
            media_id="img-large",
            mime_type="image/jpeg",
        )
        result = await process_media(state)

        assert "image_message" not in result
        assert result["user_message"] == IMAGE_TOO_LARGE_MESSAGE

    async def test_image_unsupported_mime_type_returns_message(self):
        """AC5: MIME type inválido rejeita com mensagem."""
        state = _make_state(
            message_type="image",
            media_id="img-bmp",
            mime_type="image/bmp",
        )
        result = await process_media(state)

        assert "image_message" not in result
        assert result["user_message"] == IMAGE_UNSUPPORTED_TYPE_MESSAGE

    @patch(
        "workflows.whatsapp.nodes.process_media.download_media",
        new_callable=AsyncMock,
    )
    async def test_image_unexpected_exception_returns_fallback(self, mock_download):
        """AC5: Exceção inesperada (não-ExternalServiceError) retorna fallback gracioso."""
        mock_download.side_effect = RuntimeError("Connection reset by peer")

        state = _make_state(
            message_type="image",
            media_id="img-unexpected",
            mime_type="image/jpeg",
        )
        result = await process_media(state)

        assert "image_message" not in result
        assert result["user_message"] == IMAGE_FAILURE_MESSAGE


class TestProcessMediaAudioMessage:
    """Tests for audio message handling (AC #1, #2)."""

    @patch(
        "workflows.whatsapp.nodes.process_media.transcribe_audio",
        new_callable=AsyncMock,
    )
    @patch(
        "workflows.whatsapp.nodes.process_media.download_media",
        new_callable=AsyncMock,
    )
    async def test_audio_happy_path(self, mock_download, mock_transcribe):
        """AC1: Áudio é baixado, transcrito e retornado como user_message."""
        mock_download.return_value = (b"audio-bytes", "audio/ogg")
        mock_transcribe.return_value = "Qual a dose de amoxicilina?"

        state = _make_state(
            message_type="audio",
            media_id="media-123",
            mime_type="audio/ogg; codecs=opus",
        )
        result = await process_media(state)

        assert result["transcribed_text"] == "Qual a dose de amoxicilina?"
        assert result["user_message"] == "Qual a dose de amoxicilina?"
        mock_download.assert_awaited_once_with("media-123", "audio/ogg; codecs=opus")
        mock_transcribe.assert_awaited_once_with(b"audio-bytes", "audio/ogg; codecs=opus")

    @patch(
        "workflows.whatsapp.nodes.process_media.transcribe_audio",
        new_callable=AsyncMock,
    )
    @patch(
        "workflows.whatsapp.nodes.process_media.download_media",
        new_callable=AsyncMock,
    )
    async def test_audio_with_existing_body_concatenates(
        self,
        mock_download,
        mock_transcribe,
    ):
        """AC1: Áudio com body existente (debounce) concatena texto."""
        mock_download.return_value = (b"audio-bytes", "audio/ogg")
        mock_transcribe.return_value = "dose de dipirona"

        state = _make_state(
            message_type="audio",
            media_id="media-456",
            mime_type="audio/ogg; codecs=opus",
            user_message="Olá doutor",
        )
        result = await process_media(state)

        assert result["transcribed_text"] == "dose de dipirona"
        assert result["user_message"] == "Olá doutor\n\n[Transcrição do áudio]: dose de dipirona"

    @patch(
        "workflows.whatsapp.nodes.process_media.send_text_message",
        new_callable=AsyncMock,
    )
    @patch(
        "workflows.whatsapp.nodes.process_media.transcribe_audio",
        new_callable=AsyncMock,
    )
    @patch(
        "workflows.whatsapp.nodes.process_media.download_media",
        new_callable=AsyncMock,
    )
    async def test_audio_whisper_failure_sends_message_and_raises(
        self,
        mock_download,
        mock_transcribe,
        mock_send,
    ):
        """AC2: Falha do Whisper envia mensagem amigável e raises GraphNodeError."""
        mock_download.return_value = (b"audio-bytes", "audio/ogg")
        mock_transcribe.side_effect = ExternalServiceError(
            service="whisper",
            message="HTTP 500: Internal Server Error",
        )
        mock_send.return_value = {"messages": [{"id": "wamid.err"}]}

        state = _make_state(
            message_type="audio",
            media_id="media-fail",
            mime_type="audio/ogg; codecs=opus",
        )

        with pytest.raises(GraphNodeError) as exc_info:
            await process_media(state)

        assert "process_media" in str(exc_info.value)
        mock_send.assert_awaited_once()
        sent_msg = mock_send.call_args[0][1]
        assert "Não consegui processar seu áudio" in sent_msg

    @patch(
        "workflows.whatsapp.nodes.process_media.send_text_message",
        new_callable=AsyncMock,
    )
    @patch(
        "workflows.whatsapp.nodes.process_media.download_media",
        new_callable=AsyncMock,
    )
    async def test_audio_download_failure_sends_message_and_raises(
        self,
        mock_download,
        mock_send,
    ):
        """AC2: Falha no download envia mensagem amigável e raises GraphNodeError."""
        mock_download.side_effect = ExternalServiceError(
            service="whatsapp",
            message="Timeout downloading media",
        )
        mock_send.return_value = {"messages": [{"id": "wamid.err"}]}

        state = _make_state(
            message_type="audio",
            media_id="media-timeout",
            mime_type="audio/ogg; codecs=opus",
        )

        with pytest.raises(GraphNodeError):
            await process_media(state)

        mock_send.assert_awaited_once()

    @patch(
        "workflows.whatsapp.nodes.process_media.send_text_message",
        new_callable=AsyncMock,
    )
    @patch(
        "workflows.whatsapp.nodes.process_media.transcribe_audio",
        new_callable=AsyncMock,
    )
    @patch(
        "workflows.whatsapp.nodes.process_media.download_media",
        new_callable=AsyncMock,
    )
    async def test_audio_failure_still_raises_even_if_send_fails(
        self,
        mock_download,
        mock_transcribe,
        mock_send,
    ):
        """AC2: Se envio da mensagem de erro também falha, ainda raises GraphNodeError."""
        mock_download.return_value = (b"audio-bytes", "audio/ogg")
        mock_transcribe.side_effect = ExternalServiceError(
            service="whisper",
            message="Timeout",
        )
        mock_send.side_effect = Exception("WhatsApp send failed")

        state = _make_state(
            message_type="audio",
            media_id="media-double-fail",
            mime_type="audio/ogg; codecs=opus",
        )

        with pytest.raises(GraphNodeError):
            await process_media(state)

    @patch(
        "workflows.whatsapp.nodes.process_media.transcribe_audio",
        new_callable=AsyncMock,
    )
    @patch(
        "workflows.whatsapp.nodes.process_media.download_media",
        new_callable=AsyncMock,
    )
    async def test_audio_empty_body_uses_transcription_only(
        self,
        mock_download,
        mock_transcribe,
    ):
        """AC1: Áudio sem body existente usa transcrição diretamente como user_message."""
        mock_download.return_value = (b"audio-bytes", "audio/ogg")
        mock_transcribe.return_value = "Pergunta do áudio"

        state = _make_state(
            message_type="audio",
            media_id="media-789",
            mime_type="audio/ogg; codecs=opus",
            user_message="",
        )
        result = await process_media(state)

        assert result["user_message"] == "Pergunta do áudio"
        assert "[Transcrição do áudio]" not in result["user_message"]
