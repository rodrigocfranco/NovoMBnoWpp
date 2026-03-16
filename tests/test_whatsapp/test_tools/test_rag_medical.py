"""Tests for rag_medical_search tool (AC1, AC2, AC5 — Story 2.1)."""

from unittest.mock import AsyncMock, MagicMock, patch


class TestRagMedicalSearch:
    """Tests for rag_medical_search LangChain tool."""

    @patch("workflows.whatsapp.tools.rag_medical.get_pinecone")
    async def test_returns_formatted_results_with_markers(self, mock_get_pinecone):
        """AC1: Retorna resultados formatados com [N] e metadata."""
        mock_provider = MagicMock()
        mock_provider.query_similar = AsyncMock(
            return_value=[
                {
                    "title": "Harrison's Internal Medicine",
                    "text": "Carvedilol reduz mortalidade em IC...",
                    "source": "Harrison 21ª ed., p. 1764-1768",
                    "section": "Cap. 252 — Insuficiência Cardíaca",
                    "score": 0.95,
                },
                {
                    "title": "Diretriz SBC 2023",
                    "text": "Betabloqueadores com evidência em IC...",
                    "source": "Arq Bras Cardiol. 2023; 121(1):1-212",
                    "section": "Tratamento Farmacológico",
                    "score": 0.88,
                },
            ]
        )
        mock_get_pinecone.return_value = mock_provider

        from workflows.whatsapp.tools.rag_medical import rag_medical_search

        result = await rag_medical_search.ainvoke({"query": "Quando usar carvedilol na IC?"})

        assert "[1]" in result
        assert "[2]" in result
        assert "Harrison" in result
        assert "Diretriz SBC" in result
        assert "Carvedilol reduz mortalidade" in result

    @patch("workflows.whatsapp.tools.rag_medical.get_pinecone")
    async def test_zero_coverage_returns_no_content_message(self, mock_get_pinecone):
        """AC5: Cobertura zero retorna mensagem indicando sem conteúdo curado."""
        mock_provider = MagicMock()
        mock_provider.query_similar = AsyncMock(return_value=[])
        mock_get_pinecone.return_value = mock_provider

        from workflows.whatsapp.tools.rag_medical import rag_medical_search

        result = await rag_medical_search.ainvoke({"query": "Algo sem conteúdo curado"})

        assert "não encontrei" in result.lower() or "não há" in result.lower()

    @patch("workflows.whatsapp.tools.rag_medical.get_pinecone")
    async def test_pinecone_error_returns_error_message(self, mock_get_pinecone):
        """AC1: Erro Pinecone retorna mensagem de erro amigável."""
        mock_provider = MagicMock()
        mock_provider.query_similar = AsyncMock(side_effect=Exception("Connection timeout"))
        mock_get_pinecone.return_value = mock_provider

        from workflows.whatsapp.tools.rag_medical import rag_medical_search

        result = await rag_medical_search.ainvoke({"query": "Qualquer pergunta"})

        assert "erro" in result.lower() or "indisponível" in result.lower()

    def test_tool_has_docstring(self):
        """AC1: Tool tem docstring (LLM usa para decisão de uso)."""
        from workflows.whatsapp.tools.rag_medical import rag_medical_search

        assert rag_medical_search.description
        assert len(rag_medical_search.description) > 20

    @patch("workflows.whatsapp.tools.rag_medical.get_pinecone")
    async def test_calls_query_similar_with_query_and_top_k(self, mock_get_pinecone):
        """AC1: Chama query_similar com query e top_k=5."""
        mock_provider = MagicMock()
        mock_provider.query_similar = AsyncMock(return_value=[])
        mock_get_pinecone.return_value = mock_provider

        from workflows.whatsapp.tools.rag_medical import rag_medical_search

        await rag_medical_search.ainvoke({"query": "Tratamento IC"})

        mock_provider.query_similar.assert_called_once_with(query="Tratamento IC", top_k=5)
