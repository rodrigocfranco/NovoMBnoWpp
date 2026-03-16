"""Tests for orchestrate_llm node (AC3, AC4)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from workflows.utils.errors import GraphNodeError


def _make_state(**overrides):
    """Thin wrapper over shared make_whatsapp_state with orchestrate_llm defaults."""
    from tests.test_whatsapp.conftest import make_whatsapp_state

    defaults = {
        "user_message": "O que é insuficiência cardíaca?",
        "user_id": "user-123",
        "subscription_tier": "premium",
        "cost_usd": 0.0,
    }
    defaults.update(overrides)
    return make_whatsapp_state(**defaults)


class TestOrchestrateLlm:
    """Tests for orchestrate_llm node."""

    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message")
    async def test_invokes_model_with_system_prompt_and_history(
        self, mock_build_sys, mock_tracker_cls, mock_get_model
    ):
        """AC3: Nó invoca modelo com system prompt + histórico."""
        mock_sys_msg = MagicMock()
        mock_build_sys.return_value = mock_sys_msg

        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": 0.001,
        }
        mock_tracker_cls.return_value = mock_tracker

        mock_response = AIMessage(content="Resposta do LLM")
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = mock_response
        mock_model.bind_tools = MagicMock(return_value=mock_model)
        mock_get_model.return_value = mock_model

        history = [HumanMessage(content="Oi"), AIMessage(content="Olá!")]
        state = _make_state(messages=history)

        from workflows.whatsapp.nodes.orchestrate_llm import orchestrate_llm

        await orchestrate_llm(state)

        # Verify ainvoke was called with correct message sequence
        call_args = mock_model.ainvoke.call_args
        messages = call_args[0][0]
        assert messages[0] is mock_sys_msg  # system prompt
        assert messages[1] is history[0]  # history[0]
        assert messages[2] is history[1]  # history[1]
        assert isinstance(messages[3], HumanMessage)  # user message
        assert messages[3].content == "O que é insuficiência cardíaca?"

    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message")
    async def test_response_added_to_messages(
        self, mock_build_sys, mock_tracker_cls, mock_get_model
    ):
        """AC3: Resposta do LLM é adicionada ao estado como messages."""
        mock_build_sys.return_value = MagicMock()

        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": 0.001,
        }
        mock_tracker_cls.return_value = mock_tracker

        mock_response = AIMessage(content="Insuficiência cardíaca é...")
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = mock_response
        mock_model.bind_tools = MagicMock(return_value=mock_model)
        mock_get_model.return_value = mock_model

        state = _make_state()

        from workflows.whatsapp.nodes.orchestrate_llm import orchestrate_llm

        result = await orchestrate_llm(state)

        assert "messages" in result
        assert len(result["messages"]) == 2
        # First message: user's HumanMessage (persisted for checkpointer history)
        assert isinstance(result["messages"][0], HumanMessage)
        assert result["messages"][0].content == "O que é insuficiência cardíaca?"
        # Second message: LLM response
        assert result["messages"][1] is mock_response
        assert result["messages"][1].content == "Insuficiência cardíaca é..."

    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message")
    async def test_cost_usd_returned_in_state(
        self, mock_build_sys, mock_tracker_cls, mock_get_model
    ):
        """AC3: cost_usd é calculado e retornado no estado."""
        mock_build_sys.return_value = MagicMock()

        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 1500,
            "output_tokens": 350,
            "cache_read_tokens": 1000,
            "cache_creation_tokens": 200,
            "cost_usd": 0.0072,
        }
        mock_tracker_cls.return_value = mock_tracker

        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = AIMessage(content="test")
        mock_model.bind_tools = MagicMock(return_value=mock_model)
        mock_get_model.return_value = mock_model

        state = _make_state()

        from workflows.whatsapp.nodes.orchestrate_llm import orchestrate_llm

        result = await orchestrate_llm(state)

        assert result["cost_usd"] == 0.0072

    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message")
    async def test_cost_tracker_receives_user_id(
        self, mock_build_sys, mock_tracker_cls, mock_get_model
    ):
        """AC3: CostTrackingCallback criado com user_id do estado."""
        mock_build_sys.return_value = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": 0.0,
        }
        mock_tracker_cls.return_value = mock_tracker
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = AIMessage(content="test")
        mock_model.bind_tools = MagicMock(return_value=mock_model)
        mock_get_model.return_value = mock_model

        state = _make_state(user_id="user-456")

        from workflows.whatsapp.nodes.orchestrate_llm import orchestrate_llm

        await orchestrate_llm(state)

        mock_tracker_cls.assert_called_once_with(user_id="user-456", model_name="")

    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message")
    async def test_raises_graph_node_error_on_failure(self, mock_build_sys, mock_get_model):
        """AC3: Erro no LLM levanta GraphNodeError."""
        mock_build_sys.return_value = MagicMock()
        mock_model = AsyncMock()
        mock_model.ainvoke.side_effect = RuntimeError("LLM unavailable")
        mock_model.bind_tools = MagicMock(return_value=mock_model)
        mock_get_model.return_value = mock_model

        state = _make_state()

        from workflows.whatsapp.nodes.orchestrate_llm import orchestrate_llm

        with pytest.raises(GraphNodeError, match="orchestrate_llm"):
            await orchestrate_llm(state)


class TestProviderUsedTracking:
    """Tests for provider_used tracking (Story 5.1, AC#1)."""

    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message")
    async def test_provider_used_vertex_ai_on_success(
        self, mock_build_sys, mock_tracker_cls, mock_get_model
    ):
        """AC#1: Primary provider (Vertex AI) reportado quando sucesso."""
        mock_build_sys.return_value = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": 0.001,
        }
        mock_tracker_cls.return_value = mock_tracker

        mock_response = AIMessage(
            content="Resposta",
            response_metadata={"model_name": "claude-sonnet-4@20250514"},
        )
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = mock_response
        mock_model.bind_tools = MagicMock(return_value=mock_model)
        mock_get_model.return_value = mock_model

        state = _make_state()

        from workflows.whatsapp.nodes.orchestrate_llm import orchestrate_llm

        result = await orchestrate_llm(state)

        assert result["provider_used"] == "vertex_ai"

    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message")
    async def test_provider_used_anthropic_direct_on_fallback(
        self, mock_build_sys, mock_tracker_cls, mock_get_model
    ):
        """AC#1: Fallback provider (Anthropic Direct) reportado quando fallback ativa."""
        mock_build_sys.return_value = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": 0.001,
        }
        mock_tracker_cls.return_value = mock_tracker

        # Anthropic Direct returns model name without "@"
        mock_response = AIMessage(
            content="Resposta via fallback",
            response_metadata={"model_name": "claude-sonnet-4-20250514"},
        )
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = mock_response
        mock_model.bind_tools = MagicMock(return_value=mock_model)
        mock_get_model.return_value = mock_model

        state = _make_state()

        from workflows.whatsapp.nodes.orchestrate_llm import orchestrate_llm

        result = await orchestrate_llm(state)

        assert result["provider_used"] == "anthropic_direct"

    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message")
    async def test_provider_used_logged_in_llm_response_event(
        self, mock_build_sys, mock_tracker_cls, mock_get_model
    ):
        """AC#1: provider_used é logado no evento llm_response_generated."""
        mock_build_sys.return_value = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": 0.001,
        }
        mock_tracker_cls.return_value = mock_tracker

        mock_response = AIMessage(
            content="test",
            response_metadata={"model_name": "claude-sonnet-4@20250514"},
        )
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = mock_response
        mock_model.bind_tools = MagicMock(return_value=mock_model)
        mock_get_model.return_value = mock_model

        state = _make_state()

        with patch("workflows.whatsapp.nodes.orchestrate_llm.logger") as mock_logger:
            from workflows.whatsapp.nodes.orchestrate_llm import orchestrate_llm

            await orchestrate_llm(state)

            # Verify provider_used is in the log call
            mock_logger.info.assert_called_once()
            call_kwargs = mock_logger.info.call_args[1]
            assert call_kwargs["provider_used"] == "vertex_ai"

    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message")
    async def test_provider_used_unknown_when_no_metadata(
        self, mock_build_sys, mock_tracker_cls, mock_get_model
    ):
        """AC#1: provider_used é 'unknown' quando response_metadata ausente."""
        mock_build_sys.return_value = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": 0.001,
        }
        mock_tracker_cls.return_value = mock_tracker

        # No response_metadata
        mock_response = AIMessage(content="test")
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = mock_response
        mock_model.bind_tools = MagicMock(return_value=mock_model)
        mock_get_model.return_value = mock_model

        state = _make_state()

        from workflows.whatsapp.nodes.orchestrate_llm import orchestrate_llm

        result = await orchestrate_llm(state)

        assert result["provider_used"] == "unknown"


class TestOrchestrateLlmImageMessage:
    """Tests for image_message multimodal support (Story 3.2, AC #3, #4)."""

    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message")
    async def test_image_message_sends_multimodal_human_message(
        self, mock_build_sys, mock_tracker_cls, mock_get_model
    ):
        """AC3: image_message presente → LLM recebe HumanMessage multimodal."""
        mock_sys_msg = MagicMock()
        mock_build_sys.return_value = mock_sys_msg

        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 1600,
            "output_tokens": 200,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": 0.01,
        }
        mock_tracker_cls.return_value = mock_tracker

        mock_response = AIMessage(content="Esta é uma questão sobre anatomia...")
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = mock_response
        mock_model.bind_tools = MagicMock(return_value=mock_model)
        mock_get_model.return_value = mock_model

        image_blocks = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": "abc123base64data",
                },
            },
            {"type": "text", "text": "O que é essa imagem?"},
        ]
        state = _make_state(image_message=image_blocks)

        from workflows.whatsapp.nodes.orchestrate_llm import orchestrate_llm

        await orchestrate_llm(state)

        call_args = mock_model.ainvoke.call_args
        messages = call_args[0][0]
        # messages = [sys_msg, user_msg] (no history, response not in input)
        user_msg = messages[-1]
        assert isinstance(user_msg, HumanMessage)
        assert user_msg.content == image_blocks  # multimodal content blocks

    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message")
    async def test_no_image_message_sends_text_human_message(
        self, mock_build_sys, mock_tracker_cls, mock_get_model
    ):
        """AC3: image_message None → comportamento original (texto)."""
        mock_build_sys.return_value = MagicMock()

        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": 0.001,
        }
        mock_tracker_cls.return_value = mock_tracker

        mock_response = AIMessage(content="Resposta texto")
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = mock_response
        mock_model.bind_tools = MagicMock(return_value=mock_model)
        mock_get_model.return_value = mock_model

        state = _make_state(image_message=None)

        from workflows.whatsapp.nodes.orchestrate_llm import orchestrate_llm

        await orchestrate_llm(state)

        call_args = mock_model.ainvoke.call_args
        messages = call_args[0][0]
        # messages = [sys_msg, user_msg] (no history, response not in input)
        user_msg = messages[-1]
        assert isinstance(user_msg, HumanMessage)
        assert user_msg.content == "O que é insuficiência cardíaca?"  # plain text

    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message")
    async def test_image_with_tool_reentry_works(
        self, mock_build_sys, mock_tracker_cls, mock_get_model
    ):
        """AC3: imagem + tool reentry → tools loop funciona após Vision."""
        from langchain_core.messages import ToolMessage

        mock_build_sys.return_value = MagicMock()

        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 200,
            "output_tokens": 100,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": 0.002,
        }
        mock_tracker_cls.return_value = mock_tracker

        mock_response = AIMessage(content="Resultado da busca sobre anatomia")
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = mock_response
        mock_model.bind_tools = MagicMock(return_value=mock_model)
        mock_get_model.return_value = mock_model

        # Simulate tool reentry: messages end with a ToolMessage
        image_blocks = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "x"}},
            {"type": "text", "text": "Analise"},
        ]
        existing_messages = [
            HumanMessage(content=image_blocks),
            AIMessage(content="", additional_kwargs={"tool_calls": [{"id": "tc1"}]}),
            ToolMessage(content="tool result", tool_call_id="tc1"),
        ]
        state = _make_state(
            image_message=image_blocks,
            messages=existing_messages,
            cost_usd=0.01,
        )

        from workflows.whatsapp.nodes.orchestrate_llm import orchestrate_llm

        result = await orchestrate_llm(state)

        # On re-entry, only response is returned (no new user_msg)
        assert len(result["messages"]) == 1
        assert result["messages"][0] is mock_response
        # Cost accumulated
        assert result["cost_usd"] == 0.012


class TestTokenBreakdown:
    """Tests for token breakdown fields (Story 7.1, AC#1)."""

    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message")
    async def test_returns_token_breakdown(
        self, mock_build_sys, mock_tracker_cls, mock_get_model
    ):
        """AC#1: orchestrate_llm retorna token breakdown no state."""
        mock_build_sys.return_value = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 500,
            "output_tokens": 200,
            "cache_read_tokens": 300,
            "cache_creation_tokens": 100,
            "cost_usd": 0.002,
        }
        mock_tracker_cls.return_value = mock_tracker

        mock_response = AIMessage(content="test")
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = mock_response
        mock_get_model.return_value = mock_model

        state = _make_state()

        from workflows.whatsapp.nodes.orchestrate_llm import orchestrate_llm

        result = await orchestrate_llm(state)

        assert result["tokens_input"] == 500
        assert result["tokens_output"] == 200
        assert result["tokens_cache_read"] == 300
        assert result["tokens_cache_creation"] == 100

    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message")
    async def test_tokens_accumulate_across_tool_loops(
        self, mock_build_sys, mock_tracker_cls, mock_get_model
    ):
        """AC#1: Tokens acumulam entre iterações do tool loop."""
        mock_build_sys.return_value = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 200,
            "output_tokens": 80,
            "cache_read_tokens": 50,
            "cache_creation_tokens": 0,
            "cost_usd": 0.001,
        }
        mock_tracker_cls.return_value = mock_tracker

        mock_response = AIMessage(content="Resultado")
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = mock_response
        mock_get_model.return_value = mock_model

        # State with pre-existing token counts (from previous tool loop iteration)
        state = _make_state(
            tokens_input=300,
            tokens_output=100,
            tokens_cache_read=150,
            tokens_cache_creation=50,
        )

        from workflows.whatsapp.nodes.orchestrate_llm import orchestrate_llm

        result = await orchestrate_llm(state)

        assert result["tokens_input"] == 500  # 300 + 200
        assert result["tokens_output"] == 180  # 100 + 80
        assert result["tokens_cache_read"] == 200  # 150 + 50
        assert result["tokens_cache_creation"] == 50  # 50 + 0

    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message")
    async def test_model_used_from_response_metadata(
        self, mock_build_sys, mock_tracker_cls, mock_get_model
    ):
        """AC#1: model_used capturado de response_metadata."""
        mock_build_sys.return_value = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": 0.001,
        }
        mock_tracker_cls.return_value = mock_tracker

        mock_response = AIMessage(
            content="test",
            response_metadata={"model_name": "claude-haiku-4-5@20251001"},
        )
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = mock_response
        mock_get_model.return_value = mock_model

        state = _make_state()

        from workflows.whatsapp.nodes.orchestrate_llm import orchestrate_llm

        result = await orchestrate_llm(state)

        assert result["model_used"] == "claude-haiku-4-5@20251001"
