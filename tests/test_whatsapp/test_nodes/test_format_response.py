"""Tests for format_response node (AC1, AC2, AC7)."""

from langchain_core.messages import AIMessage, HumanMessage

from workflows.whatsapp.nodes.format_response import (
    _build_source_footer,
    format_response,
    strip_competitor_citations,
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


class TestValidateCitations:
    """Tests for validate_citations function."""

    def test_removes_all_markers_when_no_sources(self):
        """AC1: Remove [N] quando retrieved_sources vazio."""
        text = "Conteúdo [1] com citações [2] inválidas."
        result = validate_citations(text, [])
        assert "[1]" not in result
        assert "[2]" not in result

    def test_removes_web_markers_when_no_sources(self):
        """AC1: Remove [W-N] quando sem fontes."""
        text = "Conteúdo [W-1] com citação web."
        result = validate_citations(text, [])
        assert "[W-1]" not in result

    def test_noop_when_no_markers(self):
        """AC1: No-op quando texto não tem marcadores."""
        text = "Conteúdo sem citações."
        result = validate_citations(text, [])
        assert result == text

    def test_keeps_valid_rag_citations(self):
        """AC1: Mantém citações RAG válidas."""
        sources = [{"type": "rag", "index": 1, "title": "Source 1"}]
        text = "Conteúdo [1] válido."
        result = validate_citations(text, sources)
        assert "[1]" in result

    def test_removes_invalid_rag_citations(self):
        """AC1: Remove citações RAG inválidas (índice não presente nas fontes)."""
        sources = [{"type": "rag", "index": 1, "title": "Source 1"}]
        text = "Conteúdo [1] válido [5] inválido."
        result = validate_citations(text, sources)
        assert "[1]" in result
        assert "[5]" not in result

    def test_keeps_valid_web_citations(self):
        """AC1: Mantém citações web válidas."""
        sources = [{"type": "web", "index": 1, "url": "https://example.com"}]
        text = "Conteúdo [W-1] válido."
        result = validate_citations(text, sources)
        assert "[W-1]" in result

    def test_validates_by_actual_index_not_count(self):
        """Review fix #7: Valida por índice real, não por contagem."""
        sources = [
            {"type": "rag", "index": 1, "title": "S1"},
            {"type": "rag", "index": 3, "title": "S3"},
        ]
        text = "Citação [1] ok, [2] inválida, [3] ok."
        result = validate_citations(text, sources)
        assert "[1]" in result
        assert "[2]" not in result
        assert "[3]" in result


class TestStripCompetitorCitations:
    """Tests for strip_competitor_citations function."""

    def test_removes_competitor_mention(self):
        """AC1: Remove menções a concorrentes."""
        text = "Segundo o Medcurso, a resposta é..."
        result = strip_competitor_citations(text)
        assert "medcurso" not in result.lower()
        assert "[fonte removida]" in result

    def test_noop_when_no_competitors(self):
        """AC1: No-op quando sem menções a concorrentes."""
        text = "Resposta normal sem menções."
        result = strip_competitor_citations(text)
        assert result == text

    def test_removes_multiple_competitors(self):
        """AC1: Remove múltiplos concorrentes."""
        text = "Medcurso e Sanar concordam que..."
        result = strip_competitor_citations(text)
        assert "medcurso" not in result.lower()
        assert "sanar" not in result.lower()


class TestFormatResponseNode:
    """Tests for format_response graph node."""

    async def test_extracts_last_aimessage(self):
        """AC1: Extrai texto do último AIMessage."""
        state = _make_state(
            messages=[
                HumanMessage(content="Pergunta"),
                AIMessage(content="**Resposta** formatada."),
            ]
        )
        result = await format_response(state)
        assert "formatted_response" in result
        assert "*Resposta*" in result["formatted_response"]

    async def test_applies_markdown_to_whatsapp(self):
        """AC1: Aplica conversão markdown → WhatsApp."""
        state = _make_state(
            messages=[
                HumanMessage(content="Q"),
                AIMessage(content="## Título\n\n**Bold** e _italic_"),
            ]
        )
        result = await format_response(state)
        assert "*Título*" in result["formatted_response"]
        assert "_italic_" in result["formatted_response"]

    async def test_validate_citations_noop_when_empty(self):
        """AC1: validate_citations é no-op quando retrieved_sources vazio."""
        state = _make_state(
            messages=[
                HumanMessage(content="Q"),
                AIMessage(content="Resposta simples sem citações."),
            ],
            retrieved_sources=[],
        )
        result = await format_response(state)
        assert "Resposta simples sem citações" in result["formatted_response"]

    async def test_strips_invalid_citations(self):
        """AC1: Remove citações [N] quando sem fontes."""
        state = _make_state(
            messages=[
                HumanMessage(content="Q"),
                AIMessage(content="Conteúdo [1] com citação [2]."),
            ],
            retrieved_sources=[],
        )
        result = await format_response(state)
        assert "[1]" not in result["formatted_response"]
        assert "[2]" not in result["formatted_response"]

    async def test_adds_disclaimer_for_medical_content(self):
        """AC7: Disclaimer adicionado em conteúdo médico."""
        state = _make_state(
            messages=[
                HumanMessage(content="Q"),
                AIMessage(content="O diagnóstico diferencial inclui pneumonia."),
            ]
        )
        result = await format_response(state)
        assert "⚕️" in result["formatted_response"]

    async def test_no_disclaimer_for_greeting(self):
        """AC7: Sem disclaimer para saudação."""
        state = _make_state(
            messages=[
                HumanMessage(content="Oi"),
                AIMessage(content="Olá! Como posso ajudar?"),
            ]
        )
        result = await format_response(state)
        assert "⚕️" not in result["formatted_response"]

    async def test_splits_long_response(self):
        """AC2: Resposta longa é dividida."""
        long_text = "Explicação médica detalhada. " * 200  # ~5800 chars
        state = _make_state(
            messages=[
                HumanMessage(content="Q"),
                AIMessage(content=long_text),
            ]
        )
        result = await format_response(state)
        assert len(result["formatted_response"]) <= 4096
        assert len(result["additional_responses"]) >= 1

    async def test_short_response_no_additional(self):
        """AC2: Resposta curta não gera additional_responses."""
        state = _make_state(
            messages=[
                HumanMessage(content="Q"),
                AIMessage(content="Resposta curta."),
            ]
        )
        result = await format_response(state)
        assert result["additional_responses"] == []

    async def test_returns_partial_dict(self):
        """AC1: Retorna dict parcial com formatted_response e additional_responses."""
        state = _make_state()
        result = await format_response(state)
        assert "formatted_response" in result
        assert "additional_responses" in result

    async def test_appends_rate_limit_warning(self):
        """AC2 (Story 4.1): format_response append warning quando rate_limit_warning preenchido."""
        state = _make_state(
            messages=[
                HumanMessage(content="Q"),
                AIMessage(content="Resposta normal."),
            ],
            rate_limit_warning="⚠️ Você ainda tem 2 perguntas disponível(is) hoje.",
        )
        result = await format_response(state)
        assert "⚠️" in result["formatted_response"]
        assert "2 perguntas" in result["formatted_response"]

    async def test_no_warning_when_empty(self):
        """AC2 (Story 4.1): Sem warning quando rate_limit_warning vazio."""
        state = _make_state(
            messages=[
                HumanMessage(content="Q"),
                AIMessage(content="Resposta normal."),
            ],
            rate_limit_warning="",
        )
        result = await format_response(state)
        assert "⚠️" not in result["formatted_response"]

    async def test_web_source_footer_appended(self):
        """AC#1 (Story 2.2): Rodapé de fontes web incluído na resposta."""
        state = _make_state(
            messages=[
                HumanMessage(content="Q"),
                AIMessage(content="Resposta com citação [W-1]."),
            ],
            web_sources=[
                {
                    "index": 1,
                    "title": "PubMed Article",
                    "url": "https://pubmed.ncbi.nlm.nih.gov/123",
                    "type": "web",
                },
            ],
        )
        result = await format_response(state)
        assert "[W-1]" in result["formatted_response"]
        assert "Web:" in result["formatted_response"]
        assert "PubMed Article" in result["formatted_response"]

    async def test_no_footer_when_no_sources(self):
        """AC#1 (Story 2.2): Sem rodapé quando não há fontes."""
        state = _make_state(
            messages=[
                HumanMessage(content="Q"),
                AIMessage(content="Resposta simples."),
            ],
        )
        result = await format_response(state)
        assert "Web:" not in result["formatted_response"]
        assert "Fontes:" not in result["formatted_response"]


class TestBuildSourceFooter:
    """Tests for _build_source_footer helper (Story 2.2)."""

    def test_web_sources_formatted(self):
        """AC#1: Formata fontes web com [W-N] título — URL."""
        web = [
            {"index": 1, "title": "Article A", "url": "https://a.com", "type": "web"},
            {"index": 2, "title": "Article B", "url": "https://b.com", "type": "web"},
        ]
        result = _build_source_footer([], web)
        assert "[W-1] Article A" in result
        assert "[W-2] Article B" in result
        assert "https://a.com" in result
        assert "\U0001f310" in result  # 🌐

    def test_rag_sources_formatted(self):
        """AC#1: Formata fontes RAG com [N] título."""
        rag = [{"index": 1, "title": "Medway Source", "type": "rag"}]
        result = _build_source_footer(rag, [])
        assert "[1] Medway Source" in result
        assert "\U0001f4da" in result  # 📚

    def test_mixed_sources(self):
        """AC#1: Footer com fontes RAG e web."""
        rag = [{"index": 1, "title": "RAG Source", "type": "rag"}]
        web = [{"index": 1, "title": "Web Source", "url": "https://web.com", "type": "web"}]
        result = _build_source_footer(rag, web)
        assert "Fontes:" in result
        assert "Web:" in result

    def test_empty_sources(self):
        """AC#1: Sem rodapé quando ambas listas vazias."""
        result = _build_source_footer([], [])
        assert result == ""
