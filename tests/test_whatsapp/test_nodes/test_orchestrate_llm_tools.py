"""Tests for orchestrate_llm with tools (AC6 — Story 2.1)."""

from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from tests.test_whatsapp.conftest import make_whatsapp_state
from workflows.whatsapp.nodes.orchestrate_llm import orchestrate_llm


def _make_state(**overrides) -> dict:
    """Wrapper over shared make_whatsapp_state with tool-test defaults."""
    defaults = {"user_message": "Quando usar carvedilol na IC?", "cost_usd": 0.0}
    defaults.update(overrides)
    return make_whatsapp_state(**defaults)


class TestOrchestreLlmTools:
    """Tests for orchestrate_llm with tools binding (AC6)."""

    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_tools")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    async def test_model_receives_tools_bound(
        self, mock_tracker_cls, mock_get_model, mock_get_tools, mock_build_sys
    ):
        """AC6: Model recebe tools via get_model(tools=...)."""
        mock_build_sys.return_value = MagicMock()
        mock_tools = [MagicMock(name="rag_medical_search")]
        mock_get_tools.return_value = mock_tools

        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = AIMessage(content="Resposta")
        mock_get_model.return_value = mock_model

        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": 0.001,
        }
        mock_tracker_cls.return_value = mock_tracker

        state = _make_state()
        await orchestrate_llm(state)

        mock_get_model.assert_called_once_with(
            tools=mock_tools, parallel_tool_calls=False, max_tokens=1024
        )

    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_tools")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    async def test_returns_tool_calls_in_response(
        self, mock_tracker_cls, mock_get_model, mock_get_tools, mock_build_sys
    ):
        """AC6: Quando LLM retorna tool_calls, nó retorna normalmente."""
        mock_build_sys.return_value = MagicMock()
        mock_get_tools.return_value = [MagicMock()]

        tool_call_response = AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "call_123",
                    "name": "rag_medical_search",
                    "args": {"query": "carvedilol IC"},
                }
            ],
        )

        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = tool_call_response
        mock_get_model.return_value = mock_model

        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": 0.001,
        }
        mock_tracker_cls.return_value = mock_tracker

        state = _make_state()
        result = await orchestrate_llm(state)

        # The node returns normally, letting tools_condition handle routing
        assert "messages" in result
        assert any(
            hasattr(m, "tool_calls") and m.tool_calls
            for m in result["messages"]
            if isinstance(m, AIMessage)
        )

    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_tools")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    async def test_cost_tracking_on_all_invocations(
        self, mock_tracker_cls, mock_get_model, mock_get_tools, mock_build_sys
    ):
        """AC6: CostTrackingCallback registra tokens de todas as invocações."""
        mock_build_sys.return_value = MagicMock()
        mock_get_tools.return_value = [MagicMock()]

        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = AIMessage(content="Resposta final")
        mock_get_model.return_value = mock_model

        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 200,
            "output_tokens": 100,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": 0.002,
        }
        mock_tracker_cls.return_value = mock_tracker

        state = _make_state()
        result = await orchestrate_llm(state)

        # Cost tracker was passed as callback via config
        call_kwargs = mock_model.ainvoke.call_args
        config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config", {})
        if isinstance(config, dict):
            assert mock_tracker in config["callbacks"]
        assert result["cost_usd"] == 0.002

    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_tools")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    async def test_reentry_after_tools_skips_duplicate_human_message(
        self, mock_tracker_cls, mock_get_model, mock_get_tools, mock_build_sys
    ):
        """CR: Re-entry após tools loop não duplica HumanMessage."""
        mock_build_sys.return_value = MagicMock()
        mock_get_tools.return_value = [MagicMock()]

        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = AIMessage(content="Resposta final")
        mock_get_model.return_value = mock_model

        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 150,
            "output_tokens": 80,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": 0.001,
        }
        mock_tracker_cls.return_value = mock_tracker

        # Simulate re-entry: state has user msg + AI tool_call + ToolMessage
        state = _make_state(
            messages=[
                HumanMessage(content="Quando usar carvedilol na IC?"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "call_1",
                            "name": "rag_medical_search",
                            "args": {"query": "carvedilol"},
                        }
                    ],
                ),
                ToolMessage(content="[1] Harrison...", tool_call_id="call_1"),
            ],
            cost_usd=0.001,
        )
        result = await orchestrate_llm(state)

        # Should only contain the AI response (no duplicate HumanMessage)
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)
        # Cost should accumulate
        assert result["cost_usd"] == 0.002
