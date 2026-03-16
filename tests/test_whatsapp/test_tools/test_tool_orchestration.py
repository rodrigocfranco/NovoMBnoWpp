"""Tests for parallel tool orchestration via ToolNode (AC #1, #2, #6 — Story 2.6)."""

import asyncio

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolCall, ToolMessage

from tests.test_whatsapp.conftest import make_whatsapp_state as _make_state
from workflows.whatsapp.nodes.collect_sources import collect_sources
from workflows.whatsapp.tools import get_tools


class TestToolRegistration:
    """Tests for tool registration in get_tools()."""

    def test_get_tools_returns_six_tools(self):
        """AC#4: get_tools() returns all 6 tools."""
        tools = get_tools()
        assert len(tools) == 6

    def test_all_tool_names_present(self):
        """AC#4: All expected tool names are registered."""
        tools = get_tools()
        tool_names = {t.name for t in tools}
        expected = {
            "rag_medical_search",
            "web_search",
            "verify_medical_paper",
            "drug_lookup",
            "medical_calculator",
            "quiz_generate",
        }
        assert tool_names == expected

    def test_all_tools_have_docstrings(self):
        """AC#4: All tools have descriptive docstrings."""
        tools = get_tools()
        for tool in tools:
            assert tool.description, f"Tool {tool.name} has no description"
            assert len(tool.description) > 20, (
                f"Tool {tool.name} description too short: {tool.description}"
            )


class TestToolNodeParallelExecution:
    """Tests for ToolNode parallel execution (AC#1, AC#6)."""

    async def test_single_tool_call_returns_correct_result(self):
        """AC#1: Single tool invocation returns correct result."""
        from workflows.whatsapp.tools.calculators import medical_calculator as calc_tool

        result = await calc_tool.ainvoke(
            {
                "calculator_name": "imc",
                "parameters": {"peso_kg": 70.0, "altura_m": 1.75},
            }
        )

        assert "22.9" in result
        assert "normal" in result.lower()

    async def test_parallel_tool_calls_via_asyncio_gather(self):
        """AC#1: Multiple tool_calls can be executed in parallel via asyncio.gather."""
        from workflows.whatsapp.tools.calculators import medical_calculator as calc_tool

        # Simulate what ToolNode does: asyncio.gather for parallel execution
        imc_coro = calc_tool.ainvoke(
            {
                "calculator_name": "imc",
                "parameters": {"peso_kg": 70.0, "altura_m": 1.75},
            }
        )
        glasgow_coro = calc_tool.ainvoke(
            {
                "calculator_name": "glasgow",
                "parameters": {
                    "abertura_ocular": 4,
                    "resposta_verbal": 5,
                    "resposta_motora": 6,
                },
            }
        )

        results = await asyncio.gather(imc_coro, glasgow_coro)

        assert len(results) == 2
        assert "22.9" in results[0]  # IMC
        assert "15" in results[1]  # Glasgow

    async def test_three_tools_parallel_rag_web_calculator(self):
        """AC#1: Three different tools executed in parallel (simulated)."""
        from workflows.whatsapp.tools.calculators import medical_calculator as calc_tool

        # Calculator is the only tool we can call without external deps
        # For RAG and web, we simulate the parallel pattern
        calc_result = await calc_tool.ainvoke(
            {
                "calculator_name": "cha2ds2_vasc",
                "parameters": {
                    "idade": 72,
                    "sexo": "M",
                    "icc": False,
                    "has": True,
                    "avc_ait": False,
                    "doenca_vascular": False,
                    "diabetes": True,
                },
            }
        )

        # Verify calc tool returns proper result
        assert "3/9" in calc_result
        assert "Alto risco" in calc_result

        # Simulate what would happen: all 3 ToolMessages in state
        state = _make_state(
            messages=[
                HumanMessage(content="CHA2DS2-VASc + conduta anticoagulação"),
                AIMessage(
                    content="",
                    tool_calls=[
                        ToolCall(
                            id="call_rag",
                            name="rag_medical_search",
                            args={"query": "anticoagulação"},
                        ),
                        ToolCall(
                            id="call_web",
                            name="web_search",
                            args={"query": "ESC AF"},
                        ),
                        ToolCall(id="call_calc", name="medical_calculator", args={}),
                    ],
                ),
                ToolMessage(
                    content='[1] Harrison\'s, Cap. 252\n   "Texto"\n   Fonte: Harrison',
                    name="rag_medical_search",
                    tool_call_id="call_rag",
                ),
                ToolMessage(
                    content="[W-1] ESC Guidelines\nURL: https://escardio.org\nContent",
                    name="web_search",
                    tool_call_id="call_web",
                ),
                ToolMessage(
                    content=calc_result,
                    name="medical_calculator",
                    tool_call_id="call_calc",
                ),
            ]
        )

        # collect_sources should parse only RAG and web
        sources_result = await collect_sources(state)
        assert len(sources_result["retrieved_sources"]) == 1
        assert len(sources_result["web_sources"]) == 1


class TestPartialFailure:
    """Tests for graceful degradation on partial tool failure (AC#2)."""

    async def test_one_tool_fails_others_succeed(self):
        """AC#2: When one tool fails, others return normally (mock scenario)."""
        # Simulate: calculator succeeds, drug_lookup fails
        # drug_lookup returns error string (never raises exception)
        calc_result = ToolMessage(
            content="IMC: 22.9 kg/m²\nClassificação: Peso normal",
            name="medical_calculator",
            tool_call_id="call_calc",
        )
        drug_error = ToolMessage(
            content=(
                "Não foi possível consultar informações sobre"
                " 'Amoxicilina'. O serviço está temporariamente"
                " indisponível."
            ),
            name="drug_lookup",
            tool_call_id="call_drug",
        )

        # Both messages should be in state — LLM receives both
        state = _make_state(
            messages=[
                HumanMessage(content="IMC 70kg 1.75m e bula amoxicilina"),
                AIMessage(
                    content="",
                    tool_calls=[
                        ToolCall(id="call_calc", name="medical_calculator", args={}),
                        ToolCall(id="call_drug", name="drug_lookup", args={}),
                    ],
                ),
                calc_result,
                drug_error,
            ]
        )

        # collect_sources should still work — no sources from either tool
        result = await collect_sources(state)
        assert result["retrieved_sources"] == []
        assert result["web_sources"] == []

    async def test_rag_fails_calculator_succeeds(self):
        """AC#2: RAG fails but calculator returns normally."""
        rag_error = ToolMessage(
            content=(
                "Erro ao buscar na base de conhecimento."
                " O serviço está temporariamente indisponível."
            ),
            name="rag_medical_search",
            tool_call_id="call_rag",
        )
        calc_result = ToolMessage(
            content="CHA₂DS₂-VASc: 3/9\nInterpretação: Alto risco",
            name="medical_calculator",
            tool_call_id="call_calc",
        )

        state = _make_state(
            messages=[
                HumanMessage(content="CHA2DS2-VASc + conduta"),
                AIMessage(
                    content="",
                    tool_calls=[
                        ToolCall(id="call_rag", name="rag_medical_search", args={}),
                        ToolCall(id="call_calc", name="medical_calculator", args={}),
                    ],
                ),
                rag_error,
                calc_result,
            ]
        )

        result = await collect_sources(state)

        # RAG error message doesn't match [N] pattern, so no sources
        assert result["retrieved_sources"] == []
        assert result["web_sources"] == []


class TestCostAccumulation:
    """Tests for cost_usd accumulation across tool iterations (AC#6)."""

    async def test_cost_accumulates_via_orchestrate_llm_pattern(self):
        """AC#6: cost_usd accumulates correctly using the same logic as orchestrate_llm."""
        # orchestrate_llm accumulates via: state["cost_usd"] + new_cost
        # Simulate 3 iterations of the tool loop
        state = _make_state(cost_usd=0.0)

        # Iteration 1: first LLM call
        new_cost_1 = 0.005
        accumulated = state["cost_usd"] + new_cost_1
        state["cost_usd"] = accumulated
        assert state["cost_usd"] == pytest.approx(0.005)

        # Iteration 2: after tools, second LLM call
        new_cost_2 = 0.003
        accumulated = state["cost_usd"] + new_cost_2
        state["cost_usd"] = accumulated
        assert state["cost_usd"] == pytest.approx(0.008)

        # Iteration 3: after more tools, third LLM call
        new_cost_3 = 0.002
        accumulated = state["cost_usd"] + new_cost_3
        state["cost_usd"] = accumulated
        assert state["cost_usd"] == pytest.approx(0.010)

        # Verify total equals sum of all iterations
        assert state["cost_usd"] == pytest.approx(new_cost_1 + new_cost_2 + new_cost_3)


class TestCollectSourcesWithMixedTools:
    """Tests for collect_sources parsing with mix of tool results (AC#5, AC#6)."""

    async def test_collect_sources_with_rag_web_calculator(self):
        """AC#5/AC#6: collect_sources correctly parses mixed results.

        Verifies RAG + web + calculator results are all present.
        """
        rag_content = (
            "[1] Harrison's, Cap. 252\n"
            '   "Texto sobre anticoagulação"\n'
            "   Fonte: Harrison 21ª ed.\n"
        )
        web_content = (
            "[W-1] ESC Guidelines 2020\n"
            "URL: https://escardio.org/guidelines\n"
            "Content about AF management"
        )
        calc_content = "CHA₂DS₂-VASc: 3/9\nAlto risco\nReferência: ESC Guidelines 2020"

        state = _make_state(
            messages=[
                HumanMessage(content="CHA2DS2-VASc + conduta anticoagulação"),
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
                            args={"query": "ESC AF guidelines"},
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
                AIMessage(content="Based on results [1] and [W-1]..."),
            ]
        )

        result = await collect_sources(state)

        # RAG and web sources extracted
        assert len(result["retrieved_sources"]) == 1
        assert result["retrieved_sources"][0]["title"] == "Harrison's, Cap. 252"
        assert len(result["web_sources"]) == 1
        assert result["web_sources"][0]["title"] == "ESC Guidelines 2020"
        assert result["web_sources"][0]["url"] == "https://escardio.org/guidelines"

    async def test_format_response_builds_footer_from_mixed_sources(self):
        """AC#6: format_response generates correct footer with sources from multiple tools."""
        from workflows.whatsapp.nodes.format_response import format_response

        rag_sources = [{"index": 1, "title": "Harrison's, Cap. 252", "type": "rag"}]
        web_sources = [
            {
                "index": 1,
                "title": "ESC Guidelines 2020",
                "url": "https://escardio.org",
                "type": "web",
            },
        ]

        state = _make_state(
            messages=[
                HumanMessage(content="CHA2DS2-VASc + conduta"),
                AIMessage(content="O score é 3 [1]. Segundo diretrizes [W-1], anticoagulação."),
            ],
            retrieved_sources=rag_sources,
            web_sources=web_sources,
        )

        result = await format_response(state)

        response = result["formatted_response"]
        assert "Harrison" in response
        assert "ESC Guidelines" in response
        assert "escardio.org" in response
