"""Tests for format_response citation handling (AC3, AC4 — Story 2.1)."""

from langchain_core.messages import AIMessage, HumanMessage

from workflows.whatsapp.nodes.format_response import (
    _build_source_footer,
    format_response,
    validate_citations,
)


def _make_state(**overrides) -> dict:
    """Create a minimal WhatsAppState-like dict for testing."""
    state = {
        "phone_number": "5511999999999",
        "user_message": "Olá",
        "message_type": "text",
        "media_url": None,
        "wamid": "wamid.test",
        "user_id": "1",
        "subscription_tier": "free",
        "is_new_user": False,
        "messages": [
            HumanMessage(content="Olá"),
            AIMessage(content="Resposta do LLM."),
        ],
        "formatted_response": "",
        "additional_responses": [],
        "response_sent": False,
        "trace_id": "trace-test",
        "cost_usd": 0.001,
        "retrieved_sources": [],
        "cited_source_indices": [],
        "web_sources": [],
        "transcribed_text": "",
        "rate_limit_exceeded": False,
        "remaining_daily": 0,
        "rate_limit_warning": "",
    }
    state.update(overrides)
    return state


class TestBuildSourceFooter:
    """Tests for _build_source_footer function (AC3)."""

    def test_rag_footer_format(self):
        """AC3: Rodapé RAG no formato 📚 *Fontes:* [1] Título."""
        rag_sources = [
            {"index": 1, "title": "Harrison, Cap. 252 — IC", "type": "rag"},
            {"index": 2, "title": "Diretriz SBC 2023", "type": "rag"},
        ]
        footer = _build_source_footer(rag_sources, [])

        assert "📚" in footer
        assert "*Fontes:*" in footer
        assert "[1] Harrison, Cap. 252 — IC" in footer
        assert "[2] Diretriz SBC 2023" in footer

    def test_no_footer_when_no_sources(self):
        """AC3: Sem rodapé quando sem fontes."""
        footer = _build_source_footer([], [])
        assert footer == ""

    def test_combined_rag_and_web_footer(self):
        """AC3: Rodapé combinado RAG + web."""
        rag_sources = [{"index": 1, "title": "Harrison", "type": "rag"}]
        web_sources = [
            {
                "index": 1,
                "title": "PubMed",
                "url": "https://pubmed.ncbi.nlm.nih.gov/123",
                "type": "web",
            }
        ]
        footer = _build_source_footer(rag_sources, web_sources)

        assert "📚" in footer
        assert "🌐" in footer
        assert "[1] Harrison" in footer
        assert "[W-1] PubMed" in footer


class TestValidateCitationsWithRag:
    """Tests for validate_citations with RAG sources (AC4)."""

    def test_keeps_valid_rag_citations(self):
        """AC4: Mantém citações [N] válidas quando fontes RAG existem."""
        sources = [
            {"type": "rag", "index": 1, "title": "Source 1"},
            {"type": "rag", "index": 2, "title": "Source 2"},
        ]
        text = "Conteúdo [1] e [2] com citações válidas."
        result = validate_citations(text, sources)
        assert "[1]" in result
        assert "[2]" in result

    def test_removes_phantom_rag_citations(self):
        """AC4: Remove citações [N] cujo índice não existe nas fontes RAG."""
        sources = [{"type": "rag", "index": 1, "title": "Source 1"}]
        text = "Conteúdo [1] válido [3] inválido [5] inválido."
        result = validate_citations(text, sources)
        assert "[1]" in result
        assert "[3]" not in result
        assert "[5]" not in result


class TestFormatResponseWithCitations:
    """Tests for format_response with RAG citation footer (AC3)."""

    async def test_adds_rag_source_footer(self):
        """AC3: format_response inclui rodapé com fontes RAG."""
        state = _make_state(
            messages=[
                HumanMessage(content="Quando usar carvedilol?"),
                AIMessage(content="Carvedilol reduz mortalidade em IC [1]."),
            ],
            retrieved_sources=[
                {"index": 1, "title": "Harrison, Cap. 252", "type": "rag"},
            ],
        )
        result = await format_response(state)

        assert "📚" in result["formatted_response"]
        assert "Harrison" in result["formatted_response"]

    async def test_no_footer_without_rag_sources(self):
        """AC3: Sem rodapé quando retrieved_sources vazio."""
        state = _make_state(
            messages=[
                HumanMessage(content="Oi"),
                AIMessage(content="Olá! Como posso ajudar?"),
            ],
            retrieved_sources=[],
        )
        result = await format_response(state)

        assert "📚" not in result["formatted_response"]

    async def test_strips_phantom_citations_from_response(self):
        """AC4: Citações [N] sem fonte real são removidas."""
        state = _make_state(
            messages=[
                HumanMessage(content="Q"),
                AIMessage(content="Info [1] e [5] e [10]."),
            ],
            retrieved_sources=[
                {"index": 1, "title": "Fonte real", "type": "rag"},
            ],
        )
        result = await format_response(state)

        assert "[1]" in result["formatted_response"]
        assert "[5]" not in result["formatted_response"]
        assert "[10]" not in result["formatted_response"]

    async def test_populates_cited_source_indices(self):
        """CR: format_response retorna cited_source_indices com índices válidos."""
        state = _make_state(
            messages=[
                HumanMessage(content="Q"),
                AIMessage(content="Info [1] e [2] são relevantes."),
            ],
            retrieved_sources=[
                {"index": 1, "title": "Fonte 1", "type": "rag"},
                {"index": 2, "title": "Fonte 2", "type": "rag"},
            ],
        )
        result = await format_response(state)

        assert "cited_source_indices" in result
        assert 1 in result["cited_source_indices"]
        assert 2 in result["cited_source_indices"]
