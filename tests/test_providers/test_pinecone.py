"""Tests for Pinecone Assistant provider (Story 2.1)."""

from unittest.mock import MagicMock, patch

import pytest

from workflows.utils.errors import ExternalServiceError


class TestPineconeProvider:
    """Tests for PineconeProvider singleton and query_similar."""

    def setup_method(self):
        """Reset singleton between tests."""
        import workflows.providers.pinecone as mod

        mod._instance = None

    def teardown_method(self):
        """Reset singleton after tests."""
        import workflows.providers.pinecone as mod

        mod._instance = None

    @patch("workflows.providers.pinecone.Pinecone")
    async def test_get_pinecone_returns_singleton(self, mock_pc_cls):
        """Singleton: segunda chamada retorna mesma instância."""
        mock_pc = MagicMock()
        mock_assistant = MagicMock()
        mock_pc.assistant.Assistant.return_value = mock_assistant
        mock_pc_cls.return_value = mock_pc

        from workflows.providers.pinecone import get_pinecone

        provider1 = await get_pinecone()
        provider2 = await get_pinecone()
        assert provider1 is provider2

    @patch("workflows.providers.pinecone.Pinecone")
    async def test_query_similar_returns_formatted_results(self, mock_pc_cls):
        """query_similar retorna snippets formatados do Assistant."""
        mock_pc = MagicMock()
        mock_assistant = MagicMock()

        snippet1 = MagicMock()
        snippet1.score = 0.95
        snippet1.content = "Carvedilol reduz mortalidade..."
        snippet1.reference = MagicMock()
        snippet1.reference.file = MagicMock(name="Harrison's Internal Medicine.pdf")
        snippet1.reference.pages = [252, 253]

        snippet2 = MagicMock()
        snippet2.score = 0.88
        snippet2.content = "Betabloqueadores com evidência..."
        snippet2.reference = MagicMock()
        snippet2.reference.file = MagicMock(name="Diretriz SBC 2023.pdf")
        snippet2.reference.pages = [10, 11]

        ctx_response = MagicMock()
        ctx_response.snippets = [snippet1, snippet2]
        mock_assistant.context.return_value = ctx_response

        mock_pc.assistant.Assistant.return_value = mock_assistant
        mock_pc_cls.return_value = mock_pc

        from workflows.providers.pinecone import get_pinecone

        provider = await get_pinecone()
        results = await provider.query_similar(query="carvedilol IC", top_k=5)

        assert len(results) == 2
        assert results[0]["score"] == 0.95
        assert "Carvedilol" in results[0]["text"]

    @patch("workflows.providers.pinecone.Pinecone")
    async def test_query_similar_empty_results(self, mock_pc_cls):
        """Retorna lista vazia quando Assistant não tem snippets relevantes."""
        mock_pc = MagicMock()
        mock_assistant = MagicMock()
        ctx_response = MagicMock()
        ctx_response.snippets = []
        mock_assistant.context.return_value = ctx_response
        mock_pc.assistant.Assistant.return_value = mock_assistant
        mock_pc_cls.return_value = mock_pc

        from workflows.providers.pinecone import get_pinecone

        provider = await get_pinecone()
        results = await provider.query_similar(query="tema sem cobertura", top_k=5)

        assert results == []

    @patch("workflows.providers.pinecone.Pinecone")
    async def test_query_similar_raises_external_service_error(self, mock_pc_cls):
        """Exceções do Pinecone viram ExternalServiceError."""
        mock_pc = MagicMock()
        mock_assistant = MagicMock()
        mock_assistant.context.side_effect = Exception("Pinecone connection timeout")
        mock_pc.assistant.Assistant.return_value = mock_assistant
        mock_pc_cls.return_value = mock_pc

        from workflows.providers.pinecone import get_pinecone

        provider = await get_pinecone()

        with pytest.raises(ExternalServiceError) as exc_info:
            await provider.query_similar(query="test query", top_k=5)

        assert "pinecone" in exc_info.value.service.lower()

    @patch("workflows.providers.pinecone.Pinecone")
    async def test_query_similar_filters_low_score_results(self, mock_pc_cls):
        """Resultados com score abaixo do threshold são filtrados."""
        mock_pc = MagicMock()
        mock_assistant = MagicMock()

        high = MagicMock()
        high.score = 0.95
        high.content = "Relevante"
        high.reference = MagicMock()
        high.reference.file = MagicMock(name="Relevante.pdf")
        high.reference.pages = []

        low = MagicMock()
        low.score = 0.3
        low.content = "Irrelevante"
        low.reference = MagicMock()
        low.reference.file = MagicMock(name="Irrelevante.pdf")
        low.reference.pages = []

        ctx_response = MagicMock()
        ctx_response.snippets = [high, low]
        mock_assistant.context.return_value = ctx_response

        mock_pc.assistant.Assistant.return_value = mock_assistant
        mock_pc_cls.return_value = mock_pc

        from workflows.providers.pinecone import get_pinecone

        provider = await get_pinecone()
        results = await provider.query_similar(query="test", top_k=5, min_score=0.5)

        assert len(results) == 1
        assert "Relevante" in results[0]["text"]

    @patch("workflows.providers.pinecone.Pinecone")
    async def test_query_similar_respects_top_k(self, mock_pc_cls):
        """Retorna no máximo top_k resultados."""
        mock_pc = MagicMock()
        mock_assistant = MagicMock()

        snippets = []
        for i in range(10):
            s = MagicMock()
            s.score = 0.9 - i * 0.01
            s.content = f"Snippet {i}"
            s.reference = MagicMock()
            s.reference.file = MagicMock(name=f"File{i}.pdf")
            s.reference.pages = []
            snippets.append(s)

        ctx_response = MagicMock()
        ctx_response.snippets = snippets
        mock_assistant.context.return_value = ctx_response

        mock_pc.assistant.Assistant.return_value = mock_assistant
        mock_pc_cls.return_value = mock_pc

        from workflows.providers.pinecone import get_pinecone

        provider = await get_pinecone()
        results = await provider.query_similar(query="test", top_k=3)

        assert len(results) == 3
