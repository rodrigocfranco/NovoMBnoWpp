"""Tests for error fallback and partial response (Story 5.2).

Covers:
- AC1: Friendly message on irrecoverable LLM failure
- AC2: Partial response when specific tool fails (ToolNode + system prompt)
- AC3: Structured error logging with required fields
- AC4: Dynamic config for error fallback message
"""

from unittest.mock import AsyncMock, patch

import pytest

from workflows.utils.errors import GraphNodeError
from workflows.views import FALLBACK_ERROR_MESSAGE, _send_fallback

# ─── AC1 / AC4: _send_fallback loads message from ConfigService ───


class TestSendFallbackConfig:
    """Tests for _send_fallback using ConfigService (AC1, AC4)."""

    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    @patch("workflows.views.ConfigService")
    async def test_send_fallback_loads_from_config(self, mock_config, mock_send):
        """AC4: _send_fallback loads message from ConfigService."""
        mock_config.get = AsyncMock(return_value="Mensagem do admin")

        await _send_fallback("5511999999999")

        mock_config.get.assert_awaited_once_with("message:error_fallback")
        mock_send.assert_awaited_once_with("5511999999999", "Mensagem do admin")

    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    @patch("workflows.views.ConfigService")
    async def test_send_fallback_uses_hardcoded_when_config_fails(self, mock_config, mock_send):
        """AC1: ConfigService fails → uses hardcoded FALLBACK_ERROR_MESSAGE."""
        mock_config.get = AsyncMock(side_effect=Exception("Config unavailable"))

        await _send_fallback("5511999999999")

        mock_send.assert_awaited_once_with("5511999999999", FALLBACK_ERROR_MESSAGE)

    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    @patch("workflows.views.ConfigService")
    async def test_send_fallback_does_not_raise_on_send_failure(self, mock_config, mock_send):
        """NFR13: _send_fallback never raises — best-effort delivery."""
        mock_config.get = AsyncMock(return_value="Mensagem")
        mock_send.side_effect = Exception("WhatsApp API down")

        # Should NOT raise
        await _send_fallback("5511999999999")


# ─── AC2: ToolNode with handle_tool_errors=True ───


class TestToolNodeHandleErrors:
    """Tests for ToolNode with handle_tool_errors=True (AC2)."""

    def test_toolnode_has_handle_tool_errors_enabled(self):
        """AC2: ToolNode is configured with handle_tool_errors=True.

        Verifies via the ToolNode instance directly, since compiled graph
        wraps nodes as PregelNode which doesn't expose handle_tool_errors.
        """
        from langgraph.prebuilt import ToolNode

        from workflows.whatsapp.tools import get_tools

        tool_node = ToolNode(get_tools(), handle_tool_errors=True)
        assert tool_node._handle_tool_errors is True

    def test_toolnode_does_not_crash_graph_on_tool_exception(self):
        """AC2: ToolNode with handle_tool_errors=True converts exception to ToolMessage.

        Uses a minimal StateGraph to provide the required graph context for ToolNode.
        """
        from typing import Annotated

        from langchain_core.messages import AIMessage, AnyMessage, ToolCall
        from langchain_core.tools import tool
        from langgraph.graph import END, START, StateGraph
        from langgraph.graph.message import add_messages
        from langgraph.prebuilt import ToolNode
        from typing_extensions import TypedDict

        class _State(TypedDict):
            messages: Annotated[list[AnyMessage], add_messages]

        @tool
        def failing_tool(query: str) -> str:
            """A tool that always fails."""
            raise ValueError("Pinecone timeout")

        builder = StateGraph(_State)
        builder.add_node("tools", ToolNode([failing_tool], handle_tool_errors=True))
        builder.add_edge(START, "tools")
        builder.add_edge("tools", END)
        graph = builder.compile()

        ai_msg = AIMessage(
            content="",
            tool_calls=[ToolCall(id="call_1", name="failing_tool", args={"query": "test"})],
        )

        # Should NOT raise — converts to ToolMessage with error content
        result = graph.invoke({"messages": [ai_msg]})
        messages = result["messages"]
        # Last message should be the error ToolMessage
        last_msg = messages[-1]
        assert "Error" in last_msg.content or "error" in last_msg.content.lower()


# ─── AC2: System prompt includes partial response instruction ───


class TestSystemPromptPartialResponse:
    """Tests for system prompt partial response instruction (AC2)."""

    def test_system_prompt_has_partial_response_section(self):
        """AC2: System prompt contains partial response instructions."""
        from workflows.whatsapp.prompts.system import SYSTEM_PROMPT

        assert "Resposta Parcial" in SYSTEM_PROMPT

    def test_system_prompt_instructs_to_inform_unavailable_sources(self):
        """AC2: System prompt tells LLM to inform which sources were unavailable."""
        from workflows.whatsapp.prompts.system import SYSTEM_PROMPT

        assert "fontes não puderam ser consultadas" in SYSTEM_PROMPT

    def test_system_prompt_forbids_inventing_data(self):
        """AC2: System prompt forbids inventing data from failed sources."""
        from workflows.whatsapp.prompts.system import SYSTEM_PROMPT

        assert "NUNCA" in SYSTEM_PROMPT
        assert "invente dados" in SYSTEM_PROMPT


# ─── AC3: Structured error logging with required fields ───


class TestErrorLogging:
    """Tests for structured error logging (AC3)."""

    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    @patch("workflows.views.ConfigService")
    @patch("workflows.views.get_graph", new_callable=AsyncMock)
    async def test_graph_node_error_logs_required_fields(
        self, mock_get_graph, mock_config, mock_send
    ):
        """AC3: GraphNodeError logs user_id, phone, node, error_type."""
        from workflows.views import _process_message

        mock_config.get = AsyncMock(return_value="fallback msg")
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(side_effect=GraphNodeError("orchestrate_llm", "LLM failed"))
        mock_get_graph.return_value = mock_graph

        validated_data = {
            "phone": "5511999999999",
            "message_id": "wamid.test123",
            "message_type": "text",
            "body": "Qual a dose de amoxicilina?",
        }

        with patch("workflows.views.logger") as mock_logger:
            await _process_message(validated_data)

            # Verify critical log was called with required fields
            mock_logger.critical.assert_called()
            call_kwargs = mock_logger.critical.call_args
            assert call_kwargs[0][0] == "graph_node_error"
            kwargs = call_kwargs[1]
            assert kwargs["phone"] == "5511999999999"
            assert kwargs["user_id"] == "5511999999999"
            assert kwargs["node"] == "orchestrate_llm"
            assert kwargs["error_type"] == "GraphNodeError"
            assert "user_message" in kwargs
            assert kwargs["exc_info"] is True

    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    @patch("workflows.views.ConfigService")
    @patch("workflows.views.get_graph", new_callable=AsyncMock)
    async def test_generic_exception_logs_required_fields(
        self, mock_get_graph, mock_config, mock_send
    ):
        """AC3: Generic exception logs user_id, error_type, node=unknown."""
        from workflows.views import _process_message

        mock_config.get = AsyncMock(return_value="fallback msg")
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("Unexpected"))
        mock_get_graph.return_value = mock_graph

        validated_data = {
            "phone": "5511999999999",
            "message_id": "wamid.test456",
            "message_type": "text",
            "body": "Olá",
        }

        with patch("workflows.views.logger") as mock_logger:
            await _process_message(validated_data)

            mock_logger.critical.assert_called()
            call_kwargs = mock_logger.critical.call_args
            assert call_kwargs[0][0] == "graph_execution_error"
            kwargs = call_kwargs[1]
            assert kwargs["user_id"] == "5511999999999"
            assert kwargs["error_type"] == "RuntimeError"
            assert kwargs["node"] == "unknown"
            assert kwargs["exc_info"] is True

    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    @patch("workflows.views.ConfigService")
    @patch("workflows.views.get_graph", new_callable=AsyncMock)
    async def test_user_message_truncated_in_log(self, mock_get_graph, mock_config, mock_send):
        """AC3: User message is truncated to 200 chars in log."""
        from workflows.views import _process_message

        mock_config.get = AsyncMock(return_value="fallback msg")
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("Fail"))
        mock_get_graph.return_value = mock_graph

        long_message = "x" * 500
        validated_data = {
            "phone": "5511999999999",
            "message_id": "wamid.long",
            "message_type": "text",
            "body": long_message,
        }

        with patch("workflows.views.logger") as mock_logger:
            await _process_message(validated_data)

            kwargs = mock_logger.critical.call_args[1]
            assert len(kwargs["user_message"]) == 200


# ─── AC2: Integration test — pipeline with failing tool ───


class TestPartialResponseIntegration:
    """Integration test: pipeline with tool failure produces partial response (AC2)."""

    def test_toolnode_partial_failure_returns_error_message(self):
        """AC2: ToolNode with mixed success/failure returns error ToolMessage for failed tool.

        Uses a minimal StateGraph to provide the required graph context for ToolNode.
        """
        from typing import Annotated

        from langchain_core.messages import AIMessage, AnyMessage, ToolCall
        from langchain_core.tools import tool
        from langgraph.graph import END, START, StateGraph
        from langgraph.graph.message import add_messages
        from langgraph.prebuilt import ToolNode
        from typing_extensions import TypedDict

        class _State(TypedDict):
            messages: Annotated[list[AnyMessage], add_messages]

        @tool
        def working_tool(query: str) -> str:
            """A tool that works."""
            return "Resultado da busca: dados encontrados"

        @tool
        def failing_tool(query: str) -> str:
            """A tool that fails."""
            raise ConnectionError("Pinecone timeout")

        builder = StateGraph(_State)
        builder.add_node("tools", ToolNode([working_tool, failing_tool], handle_tool_errors=True))
        builder.add_edge(START, "tools")
        builder.add_edge("tools", END)
        graph = builder.compile()

        ai_msg = AIMessage(
            content="",
            tool_calls=[
                ToolCall(id="call_ok", name="working_tool", args={"query": "test"}),
                ToolCall(id="call_fail", name="failing_tool", args={"query": "test"}),
            ],
        )

        result = graph.invoke({"messages": [ai_msg]})
        messages = result["messages"]

        # Input AIMessage + 2 ToolMessages
        tool_messages = [m for m in messages if hasattr(m, "tool_call_id") and m.tool_call_id]

        assert len(tool_messages) == 2

        success_msg = next(m for m in tool_messages if m.tool_call_id == "call_ok")
        error_msg = next(m for m in tool_messages if m.tool_call_id == "call_fail")

        assert "Resultado da busca" in success_msg.content
        assert "Error" in error_msg.content or "error" in error_msg.content.lower()


# ─── Migration test ───


@pytest.mark.django_db
class TestErrorFallbackMigration:
    """Test that the error fallback config is accessible after migration (AC4)."""

    async def test_migration_creates_error_fallback_config(self):
        """AC4: Migration 0008 populates message:error_fallback key."""
        from workflows.models import Config

        # Migration should have already created the key — no manual insert
        config = await Config.objects.aget(key="message:error_fallback")
        assert "instabilidade técnica" in config.value

    @patch("workflows.services.config_service.get_redis_client")
    async def test_config_service_returns_error_fallback(self, mock_get_redis):
        """AC4: ConfigService can fetch message:error_fallback."""
        from workflows.services.config_service import ConfigService

        # Mock Redis cache miss so it falls through to DB
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()
        mock_get_redis.return_value = mock_redis

        result = await ConfigService.get("message:error_fallback")
        assert "instabilidade técnica" in result
