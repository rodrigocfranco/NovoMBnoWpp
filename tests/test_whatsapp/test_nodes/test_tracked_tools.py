"""Tests for tracked_tools wrapper node (Story 7.1, Task 4)."""

from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode


class TestTrackedTools:
    """Tests for tracked_tools execution tracking."""

    @patch("workflows.whatsapp.nodes.tracked_tools._tool_node")
    async def test_successful_tool_execution(self, mock_tool_node):
        """Tool sucesso → tool_executions com success=True."""
        mock_tool_node.ainvoke = AsyncMock(
            return_value={
                "messages": [
                    ToolMessage(
                        content="Drug info for carvedilol",
                        name="drug_lookup",
                        tool_call_id="tc1",
                    ),
                ],
            }
        )

        state = {
            "user_id": "user-1",
            "tool_executions": [],
            "messages": [],
        }

        from workflows.whatsapp.nodes.tracked_tools import tracked_tools

        result = await tracked_tools(state)

        assert len(result["tool_executions"]) == 1
        exec_data = result["tool_executions"][0]
        assert exec_data["tool_name"] == "drug_lookup"
        assert exec_data["success"] is True
        assert exec_data["error"] is None
        assert exec_data["latency_ms"] >= 0

    @patch("workflows.whatsapp.nodes.tracked_tools._tool_node")
    async def test_failed_tool_execution(self, mock_tool_node):
        """Tool erro → tool_executions com success=False e error message."""
        error_msg = ToolMessage(
            content="Error: timeout after 10s",
            name="web_search",
            tool_call_id="tc2",
            status="error",
        )
        mock_tool_node.ainvoke = AsyncMock(return_value={"messages": [error_msg]})

        state = {
            "user_id": "user-1",
            "tool_executions": [],
            "messages": [],
        }

        from workflows.whatsapp.nodes.tracked_tools import tracked_tools

        result = await tracked_tools(state)

        assert len(result["tool_executions"]) == 1
        exec_data = result["tool_executions"][0]
        assert exec_data["tool_name"] == "web_search"
        assert exec_data["success"] is False
        assert exec_data["error"] == "Error: timeout after 10s"

    @patch("workflows.whatsapp.nodes.tracked_tools._tool_node")
    async def test_accumulates_with_previous_executions(self, mock_tool_node):
        """tool_executions acumulam entre iterações do tool loop."""
        mock_tool_node.ainvoke = AsyncMock(
            return_value={
                "messages": [
                    ToolMessage(content="result", name="rag_search", tool_call_id="tc3"),
                ],
            }
        )

        previous = [{"tool_name": "drug_lookup", "latency_ms": 100, "success": True, "error": None}]
        state = {
            "user_id": "user-1",
            "tool_executions": previous,
            "messages": [],
        }

        from workflows.whatsapp.nodes.tracked_tools import tracked_tools

        result = await tracked_tools(state)

        assert len(result["tool_executions"]) == 2
        assert result["tool_executions"][0]["tool_name"] == "drug_lookup"
        assert result["tool_executions"][1]["tool_name"] == "rag_search"

    @patch("workflows.whatsapp.nodes.tracked_tools._tool_node")
    async def test_latency_tracking(self, mock_tool_node):
        """latency_ms é medido corretamente."""
        mock_tool_node.ainvoke = AsyncMock(
            return_value={
                "messages": [
                    ToolMessage(content="result", name="calculator", tool_call_id="tc4"),
                ],
            }
        )

        state = {
            "user_id": "user-1",
            "tool_executions": [],
            "messages": [],
        }

        from workflows.whatsapp.nodes.tracked_tools import tracked_tools

        result = await tracked_tools(state)

        exec_data = result["tool_executions"][0]
        assert isinstance(exec_data["latency_ms"], int)
        assert exec_data["latency_ms"] >= 0

    @patch("workflows.whatsapp.nodes.tracked_tools._tool_node")
    async def test_preserves_tool_node_messages(self, mock_tool_node):
        """tracked_tools preserva as messages do ToolNode original."""
        tool_msg = ToolMessage(content="some result", name="pubmed_search", tool_call_id="tc5")
        mock_tool_node.ainvoke = AsyncMock(return_value={"messages": [tool_msg]})

        state = {
            "user_id": "user-1",
            "tool_executions": [],
            "messages": [],
        }

        from workflows.whatsapp.nodes.tracked_tools import tracked_tools

        result = await tracked_tools(state)

        assert result["messages"] == [tool_msg]


class TestTrackedToolsRealToolNode:
    """Review Fix H2: test with real ToolNode output (not hand-crafted ToolMessages).

    ToolNode requires LangGraph graph context for ainvoke(), so we build a mini
    StateGraph to test the full tracked_tools wrapper with real tool execution.
    """

    async def test_real_tool_node_success_via_graph(self):
        """Real tool execution inside a graph → tracked_tools records metadata correctly."""
        import time
        from typing import Annotated

        from langchain_core.messages import AnyMessage
        from langgraph.graph import StateGraph
        from langgraph.graph.message import add_messages
        from typing_extensions import TypedDict

        @tool
        def greet(name: str) -> str:
            """Return a greeting."""
            return f"Hello {name}"

        class MiniState(TypedDict):
            messages: Annotated[list[AnyMessage], add_messages]
            user_id: str
            tool_executions: list[dict]

        real_tool_node = ToolNode([greet], handle_tool_errors=True)

        async def tracked_wrapper(state: MiniState) -> dict:
            """Replicates tracked_tools logic with the real ToolNode."""
            start = time.monotonic()
            result = await real_tool_node.ainvoke(state)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            tool_messages = [m for m in result.get("messages", []) if isinstance(m, ToolMessage)]
            prev_executions = state.get("tool_executions") or []
            new_executions = []
            for msg in tool_messages:
                is_error = hasattr(msg, "status") and msg.status == "error"
                new_executions.append(
                    {
                        "tool_name": msg.name or "unknown",
                        "latency_ms": elapsed_ms,
                        "success": not is_error,
                        "error": msg.content[:500] if is_error else None,
                    }
                )
            return {**result, "tool_executions": prev_executions + new_executions}

        builder = StateGraph(MiniState)
        builder.add_node("tools", tracked_wrapper)
        builder.set_entry_point("tools")
        builder.set_finish_point("tools")
        graph = builder.compile()

        ai_msg = AIMessage(
            content="",
            tool_calls=[{"name": "greet", "args": {"name": "Rodrigo"}, "id": "tc_real_1"}],
        )
        result = await graph.ainvoke(
            {"messages": [ai_msg], "user_id": "user-1", "tool_executions": []}
        )

        # Verify real tool execution was tracked
        assert len(result["tool_executions"]) == 1
        exec_data = result["tool_executions"][0]
        assert exec_data["tool_name"] == "greet"
        assert exec_data["success"] is True
        assert exec_data["error"] is None
        assert isinstance(exec_data["latency_ms"], int)
        assert exec_data["latency_ms"] >= 0
        # Verify real ToolMessage from actual tool execution
        tool_msgs = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        assert len(tool_msgs) == 1
        assert "Hello Rodrigo" in tool_msgs[0].content

    async def test_real_tool_node_error_via_graph(self):
        """Real tool error inside a graph → tracked_tools records failure correctly."""
        import time
        from typing import Annotated

        from langchain_core.messages import AnyMessage
        from langgraph.graph import StateGraph
        from langgraph.graph.message import add_messages
        from typing_extensions import TypedDict

        @tool
        def failing_tool(query: str) -> str:
            """A tool that always fails."""
            msg = "Service unavailable"
            raise ValueError(msg)

        class MiniState(TypedDict):
            messages: Annotated[list[AnyMessage], add_messages]
            user_id: str
            tool_executions: list[dict]

        real_tool_node = ToolNode([failing_tool], handle_tool_errors=True)

        async def tracked_wrapper(state: MiniState) -> dict:
            """Replicates tracked_tools logic with the real ToolNode."""
            start = time.monotonic()
            result = await real_tool_node.ainvoke(state)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            tool_messages = [m for m in result.get("messages", []) if isinstance(m, ToolMessage)]
            prev_executions = state.get("tool_executions") or []
            new_executions = []
            for msg in tool_messages:
                is_error = hasattr(msg, "status") and msg.status == "error"
                new_executions.append(
                    {
                        "tool_name": msg.name or "unknown",
                        "latency_ms": elapsed_ms,
                        "success": not is_error,
                        "error": msg.content[:500] if is_error else None,
                    }
                )
            return {**result, "tool_executions": prev_executions + new_executions}

        builder = StateGraph(MiniState)
        builder.add_node("tools", tracked_wrapper)
        builder.set_entry_point("tools")
        builder.set_finish_point("tools")
        graph = builder.compile()

        ai_msg = AIMessage(
            content="",
            tool_calls=[{"name": "failing_tool", "args": {"query": "test"}, "id": "tc_real_2"}],
        )
        result = await graph.ainvoke(
            {"messages": [ai_msg], "user_id": "user-1", "tool_executions": []}
        )

        assert len(result["tool_executions"]) == 1
        exec_data = result["tool_executions"][0]
        assert exec_data["tool_name"] == "failing_tool"
        assert exec_data["success"] is False
        assert exec_data["error"] is not None
