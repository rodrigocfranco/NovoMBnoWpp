"""Tests for graph integration with ToolNode (AC6 — Story 2.1 + Story 2.6)."""

from langchain_core.messages import AIMessage, HumanMessage, ToolCall, ToolMessage

from tests.test_whatsapp.conftest import make_whatsapp_state as _make_state
from workflows.whatsapp.graph import build_whatsapp_graph
from workflows.whatsapp.nodes.collect_sources import collect_sources
from workflows.whatsapp.nodes.format_response import format_response


class TestGraphToolsIntegration:
    """Tests for ToolNode integration in the graph (AC6)."""

    def test_graph_has_tools_node(self):
        """AC6: Graph compilado contém nó 'tools'."""
        graph = build_whatsapp_graph()
        node_names = set(graph.get_graph().nodes.keys())
        assert "tools" in node_names

    def test_graph_has_collect_sources_node(self):
        """AC6: Graph compilado contém nó 'collect_sources'."""
        graph = build_whatsapp_graph()
        node_names = set(graph.get_graph().nodes.keys())
        assert "collect_sources" in node_names

    def test_graph_has_orchestrate_llm_node(self):
        """AC6: Graph compilado contém nó 'orchestrate_llm'."""
        graph = build_whatsapp_graph()
        node_names = set(graph.get_graph().nodes.keys())
        assert "orchestrate_llm" in node_names

    def test_rag_medical_search_in_tools(self):
        """AC6: rag_medical_search está registrada na lista de tools."""
        from workflows.whatsapp.tools import get_tools

        tools = get_tools()
        tool_names = [t.name for t in tools]
        assert "rag_medical_search" in tool_names

    def test_graph_compiles_successfully(self):
        """AC6: Graph compila sem erros com todos os nós incluindo tools."""
        graph = build_whatsapp_graph()
        assert graph is not None
        node_names = set(graph.get_graph().nodes.keys())
        # All expected nodes present
        expected = {
            "identify_user",
            "rate_limit",
            "load_context",
            "orchestrate_llm",
            "format_response",
            "send_whatsapp",
            "persist",
            "tools",
            "collect_sources",
        }
        assert expected.issubset(node_names)


class TestGraphToolsE2EFlow:
    """Story 2.6 AC#1, AC#2: End-to-end flow with parallel tools."""

    def test_all_tools_registered_in_graph(self):
        """AC#4: Graph has all 6 tools registered."""
        from workflows.whatsapp.tools import get_tools

        tools = get_tools()
        tool_names = {t.name for t in tools}
        assert tool_names == {
            "rag_medical_search",
            "web_search",
            "verify_medical_paper",
            "drug_lookup",
            "medical_calculator",
            "quiz_generate",
        }

    async def test_e2e_collect_sources_after_parallel_tools(self):
        """AC#1: Full flow: orchestrate_llm → tools (parallel) → collect_sources."""
        rag_content = (
            "[1] Harrison's, Cap. 252 — IC\n"
            '   "Carvedilol reduz mortalidade em IC"\n'
            "   Fonte: Harrison 21ª ed.\n"
        )
        web_content = (
            "[W-1] ESC Guidelines 2020\n"
            "URL: https://escardio.org/AF\n"
            "Anticoagulation in AF management"
        )
        calc_content = "CHA₂DS₂-VASc: 3/9\nInterpretação: Alto risco"

        state = _make_state(
            messages=[
                HumanMessage(content="CHA2DS2-VASc de 72a, HAS, DM + conduta anticoagulação"),
                AIMessage(
                    content="",
                    tool_calls=[
                        ToolCall(
                            id="call_rag",
                            name="rag_medical_search",
                            args={"query": "anticoagulação FA"},
                        ),
                        ToolCall(
                            id="call_web",
                            name="web_search",
                            args={"query": "ESC AF guidelines 2020"},
                        ),
                        ToolCall(
                            id="call_calc",
                            name="medical_calculator",
                            args={},
                        ),
                    ],
                ),
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
                    content=calc_content,
                    name="medical_calculator",
                    tool_call_id="call_calc",
                ),
                AIMessage(
                    content=("O CHA₂DS₂-VASc do paciente é 3 [1]. Segundo as diretrizes [W-1]..."),
                ),
            ]
        )

        # Run collect_sources
        sources = await collect_sources(state)

        # Verify retrieved_sources + web_sources unified
        assert len(sources["retrieved_sources"]) == 1
        assert sources["retrieved_sources"][0]["title"] == "Harrison's, Cap. 252 — IC"
        assert sources["retrieved_sources"][0]["type"] == "rag"
        assert len(sources["web_sources"]) == 1
        assert sources["web_sources"][0]["title"] == "ESC Guidelines 2020"
        assert sources["web_sources"][0]["url"] == "https://escardio.org/AF"

    async def test_e2e_format_response_with_mixed_sources(self):
        """AC#1: format_response generates footer with sources from multiple tools."""
        rag_sources = [{"index": 1, "title": "Harrison's, Cap. 252", "type": "rag"}]
        web_sources = [
            {
                "index": 1,
                "title": "ESC Guidelines 2020",
                "url": "https://escardio.org/AF",
                "type": "web",
            },
        ]

        state = _make_state(
            messages=[
                HumanMessage(content="test"),
                AIMessage(
                    content=(
                        "O CHA₂DS₂-VASc do paciente é 3 [1]."
                        " Segundo as diretrizes [W-1],"
                        " anticoagulação é recomendada."
                    ),
                ),
            ],
            retrieved_sources=rag_sources,
            web_sources=web_sources,
        )

        result = await format_response(state)

        # Footer should contain both RAG and web sources
        response = result["formatted_response"]
        assert "Harrison" in response
        assert "ESC Guidelines" in response
        assert "escardio.org" in response
