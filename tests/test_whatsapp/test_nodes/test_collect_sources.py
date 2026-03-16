"""Tests for collect_sources node (Story 2.2, AC #1)."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from tests.test_whatsapp.conftest import make_whatsapp_state as _make_state
from workflows.whatsapp.nodes.collect_sources import collect_sources


class TestCollectSources:
    """Tests for collect_sources graph node."""

    async def test_extracts_web_sources_from_tool_message(self):
        """AC#1: Extract [W-N] sources from web_search ToolMessage."""
        tool_content = (
            "[W-1] PubMed Article\n"
            "URL: https://pubmed.ncbi.nlm.nih.gov/123\n"
            "Content about pneumonia\n\n"
            "[W-2] WHO Guidelines\n"
            "URL: https://who.int/guidelines\n"
            "Content about treatment"
        )
        state = _make_state(
            messages=[
                HumanMessage(content="test"),
                AIMessage(
                    content="",
                    tool_calls=[{"id": "call_1", "name": "web_search", "args": {"query": "test"}}],
                ),
                ToolMessage(content=tool_content, name="web_search", tool_call_id="call_1"),
                AIMessage(content="Based on the results..."),
            ]
        )

        result = await collect_sources(state)

        assert len(result["web_sources"]) == 2
        assert result["web_sources"][0]["index"] == 1
        assert result["web_sources"][0]["title"] == "PubMed Article"
        assert result["web_sources"][0]["url"] == "https://pubmed.ncbi.nlm.nih.gov/123"
        assert result["web_sources"][0]["type"] == "web"
        assert result["web_sources"][1]["index"] == 2

    async def test_no_tool_messages_returns_empty(self):
        """AC#1: No web_sources when no ToolMessages."""
        state = _make_state(
            messages=[
                HumanMessage(content="test"),
                AIMessage(content="Simple response"),
            ]
        )

        result = await collect_sources(state)

        assert result["web_sources"] == []

    async def test_ignores_non_web_search_tool_messages(self):
        """AC#1: Only parse web_search ToolMessages, not others."""
        state = _make_state(
            messages=[
                HumanMessage(content="test"),
                ToolMessage(
                    content="Some other tool result",
                    name="verify_medical_paper",
                    tool_call_id="call_1",
                ),
            ]
        )

        result = await collect_sources(state)

        assert result["web_sources"] == []

    async def test_handles_empty_tool_result(self):
        """AC#2: Graceful handling of empty tool results."""
        state = _make_state(
            messages=[
                HumanMessage(content="test"),
                ToolMessage(
                    content="Não foram encontradas fontes web confiáveis para esta consulta.",
                    name="web_search",
                    tool_call_id="call_1",
                ),
            ]
        )

        result = await collect_sources(state)

        assert result["web_sources"] == []

    async def test_extracts_rag_sources_from_tool_message(self):
        """Story 2.1 AC#1: Extract [N] sources from rag_medical_search ToolMessage."""
        tool_content = (
            "[1] Harrison's Internal Medicine, Cap. 252 — IC\n"
            '   "Carvedilol reduz mortalidade em IC..."\n'
            "   Fonte: Harrison 21ª ed., p. 1764-1768\n\n"
            "[2] Diretriz SBC 2023, Tratamento Farmacológico\n"
            '   "Betabloqueadores com evidência em IC..."\n'
            "   Fonte: Arq Bras Cardiol. 2023; 121(1):1-212"
        )
        state = _make_state(
            messages=[
                HumanMessage(content="Quando usar carvedilol na IC?"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "call_rag",
                            "name": "rag_medical_search",
                            "args": {"query": "carvedilol IC"},
                        }
                    ],
                ),
                ToolMessage(
                    content=tool_content,
                    name="rag_medical_search",
                    tool_call_id="call_rag",
                ),
                AIMessage(content="Carvedilol é usado em IC [1] conforme SBC [2]."),
            ]
        )

        result = await collect_sources(state)

        assert len(result["retrieved_sources"]) == 2
        assert result["retrieved_sources"][0]["index"] == 1
        assert (
            result["retrieved_sources"][0]["title"] == "Harrison's Internal Medicine, Cap. 252 — IC"
        )
        assert result["retrieved_sources"][0]["type"] == "rag"
        assert result["retrieved_sources"][1]["index"] == 2

    async def test_rag_zero_coverage_returns_empty(self):
        """Story 2.1 AC#5: Zero coverage returns empty retrieved_sources."""
        state = _make_state(
            messages=[
                HumanMessage(content="test"),
                ToolMessage(
                    content="Não encontrei conteúdo curado sobre este tema.",
                    name="rag_medical_search",
                    tool_call_id="call_rag",
                ),
            ]
        )

        result = await collect_sources(state)

        assert result["retrieved_sources"] == []

    async def test_combined_rag_and_web_sources(self):
        """Story 2.1+2.2: Both RAG and web sources collected together."""
        rag_content = '[1] Harrison\'s, Cap. 252\n   "Texto RAG"\n   Fonte: Harrison\n'
        web_content = "[W-1] PubMed Article\nURL: https://pubmed.ncbi.nlm.nih.gov/123\nContent"
        state = _make_state(
            messages=[
                HumanMessage(content="test"),
                ToolMessage(
                    content=rag_content,
                    name="rag_medical_search",
                    tool_call_id="call_rag",
                ),
                ToolMessage(
                    content=web_content,
                    name="web_search",
                    tool_call_id="call_web",
                ),
            ]
        )

        result = await collect_sources(state)

        assert len(result["retrieved_sources"]) == 1
        assert result["retrieved_sources"][0]["type"] == "rag"
        assert len(result["web_sources"]) == 1
        assert result["web_sources"][0]["type"] == "web"

    async def test_ignores_previous_turn_tool_messages(self):
        """Review fix #1: Only collect sources from current turn, not previous."""
        old_web_content = "[W-1] Old Article\nURL: https://old.com/article\nOld content"
        new_web_content = "[W-1] New Article\nURL: https://new.com/article\nNew content"
        state = _make_state(
            messages=[
                # --- Previous turn ---
                HumanMessage(content="primeira pergunta"),
                AIMessage(
                    content="",
                    tool_calls=[{"id": "call_old", "name": "web_search", "args": {"query": "old"}}],
                ),
                ToolMessage(content=old_web_content, name="web_search", tool_call_id="call_old"),
                AIMessage(content="Resposta anterior com [W-1]."),
                # --- Current turn ---
                HumanMessage(content="segunda pergunta"),
                AIMessage(
                    content="",
                    tool_calls=[{"id": "call_new", "name": "web_search", "args": {"query": "new"}}],
                ),
                ToolMessage(content=new_web_content, name="web_search", tool_call_id="call_new"),
                AIMessage(content="Resposta atual com [W-1]."),
            ]
        )

        result = await collect_sources(state)

        # Only current turn sources
        assert len(result["web_sources"]) == 1
        assert result["web_sources"][0]["title"] == "New Article"
        assert result["web_sources"][0]["url"] == "https://new.com/article"

    async def test_ignores_drug_lookup_tool_messages(self):
        """AC#5 Story 2.6: drug_lookup ToolMessages are not parsed as sources."""
        state = _make_state(
            messages=[
                HumanMessage(content="Qual a dose de amoxicilina?"),
                ToolMessage(
                    content="**Amoxicilina** (Amoxil)\nIndicações: Infecções...",
                    name="drug_lookup",
                    tool_call_id="call_drug",
                ),
            ]
        )

        result = await collect_sources(state)

        assert result["retrieved_sources"] == []
        assert result["web_sources"] == []

    async def test_ignores_medical_calculator_tool_messages(self):
        """AC#5 Story 2.6: medical_calculator ToolMessages are not parsed as sources."""
        state = _make_state(
            messages=[
                HumanMessage(content="CHA2DS2-VASc de paciente 72a, HAS, DM?"),
                ToolMessage(
                    content="CHA₂DS₂-VASc: 3/9\nInterpretação: Alto risco",
                    name="medical_calculator",
                    tool_call_id="call_calc",
                ),
            ]
        )

        result = await collect_sources(state)

        assert result["retrieved_sources"] == []
        assert result["web_sources"] == []

    async def test_mixed_tools_only_parses_rag_and_web(self):
        """AC#5 Story 2.6: Mix of all 5 tools — only RAG and web generate sources."""
        rag_content = '[1] Harrison\'s, Cap. 252\n   "Texto RAG"\n   Fonte: Harrison\n'
        web_content = "[W-1] PubMed Article\nURL: https://pubmed.ncbi.nlm.nih.gov/123\nContent"
        state = _make_state(
            messages=[
                HumanMessage(content="CHA2DS2-VASc + conduta anticoagulação"),
                ToolMessage(
                    content=rag_content,
                    name="rag_medical_search",
                    tool_call_id="call_rag",
                ),
                ToolMessage(
                    content=web_content,
                    name="web_search",
                    tool_call_id="call_web",
                ),
                ToolMessage(
                    content="CHA₂DS₂-VASc: 3/9\nAlto risco",
                    name="medical_calculator",
                    tool_call_id="call_calc",
                ),
                ToolMessage(
                    content="**Varfarina** — Anticoagulante oral",
                    name="drug_lookup",
                    tool_call_id="call_drug",
                ),
                ToolMessage(
                    content="✅ ARTIGO VERIFICADO no PubMed",
                    name="verify_medical_paper",
                    tool_call_id="call_verify",
                ),
            ]
        )

        result = await collect_sources(state)

        assert len(result["retrieved_sources"]) == 1
        assert result["retrieved_sources"][0]["type"] == "rag"
        assert len(result["web_sources"]) == 1
        assert result["web_sources"][0]["type"] == "web"
