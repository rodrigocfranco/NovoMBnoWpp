"""Tests for Embeddings provider (AC1 — Story 2.1)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from workflows.utils.errors import ExternalServiceError


class TestEmbeddingsProvider:
    """Tests for get_embeddings() and embed_query()."""

    def setup_method(self):
        """Reset singleton between tests."""
        import workflows.providers.embeddings as mod

        mod._embeddings_instance = None

    def teardown_method(self):
        """Reset singleton after tests."""
        import workflows.providers.embeddings as mod

        mod._embeddings_instance = None

    @patch("workflows.providers.embeddings.VertexAIEmbeddings")
    def test_get_embeddings_returns_vertex_ai_instance(self, mock_cls):
        """AC1: get_embeddings retorna VertexAIEmbeddings com text-embedding-004."""
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance

        from workflows.providers.embeddings import get_embeddings

        result = get_embeddings()
        assert result is mock_instance

        mock_cls.assert_called_once()
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["model_name"] == "text-embedding-004"

    @patch("workflows.providers.embeddings.VertexAIEmbeddings")
    def test_get_embeddings_singleton(self, mock_cls):
        """Singleton: segunda chamada retorna mesma instância."""
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance

        from workflows.providers.embeddings import get_embeddings

        result1 = get_embeddings()
        result2 = get_embeddings()
        assert result1 is result2
        mock_cls.assert_called_once()

    @patch("workflows.providers.embeddings.VertexAIEmbeddings")
    async def test_embed_query_returns_vector(self, mock_cls):
        """AC1: embed_query retorna list[float] via aembed_query."""
        mock_instance = MagicMock()
        expected_vector = [0.1] * 768
        mock_instance.aembed_query = AsyncMock(return_value=expected_vector)
        mock_cls.return_value = mock_instance

        from workflows.providers.embeddings import embed_query

        result = await embed_query("Quando usar carvedilol na IC?")

        assert result == expected_vector
        mock_instance.aembed_query.assert_called_once_with("Quando usar carvedilol na IC?")

    @patch("workflows.providers.embeddings.VertexAIEmbeddings")
    async def test_embed_query_raises_external_service_error(self, mock_cls):
        """CR: Erros do VertexAI são convertidos em ExternalServiceError."""
        mock_instance = MagicMock()
        mock_instance.aembed_query = AsyncMock(side_effect=Exception("Quota exceeded"))
        mock_cls.return_value = mock_instance

        from workflows.providers.embeddings import embed_query

        with pytest.raises(ExternalServiceError) as exc_info:
            await embed_query("Qualquer texto")

        assert "vertexai" in exc_info.value.service.lower()
