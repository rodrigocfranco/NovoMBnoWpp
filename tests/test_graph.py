"""Tests for WhatsApp LangGraph StateGraph."""

import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from django.test import AsyncClient
from langchain_core.messages import AIMessage

from workflows.services.rate_limiter import RateLimitResult
from workflows.whatsapp.graph import build_whatsapp_graph, get_graph

WEBHOOK_SECRET = "test-webhook-secret"


def _make_initial_state(**overrides) -> dict:
    """Create a complete initial state dict for graph invocation."""
    from tests.test_whatsapp.conftest import make_whatsapp_state

    defaults = {
        "user_id": "",
        "subscription_tier": "",
        "cost_usd": 0.0,
    }
    defaults.update(overrides)
    return make_whatsapp_state(**defaults)


def _setup_mocks(
    mock_id_cache,
    mock_ctx_cache,
    mock_tracker_cls,
    mock_get_model,
    llm_content="Resposta do LLM",
):
    """Configure common mocks for graph execution tests."""
    mock_id_cache.get_session = AsyncMock(return_value=None)
    mock_id_cache.cache_session = AsyncMock()
    mock_ctx_cache.get_session = AsyncMock(return_value=None)
    mock_ctx_cache.cache_session = AsyncMock()

    mock_tracker = MagicMock()
    mock_tracker.get_cost_summary.return_value = {
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
        "cost_usd": 0.001,
    }
    mock_tracker_cls.return_value = mock_tracker
    mock_response = AIMessage(content=llm_content)
    mock_model = AsyncMock()
    mock_model.ainvoke.return_value = mock_response
    mock_model.bind_tools = MagicMock(return_value=mock_model)
    mock_get_model.return_value = mock_model


class TestBuildWhatsAppGraph:
    """Tests for graph construction."""

    def test_graph_builds_successfully(self):
        """Graph compila sem erros."""
        graph = build_whatsapp_graph()
        assert graph is not None

    def test_graph_builds_with_checkpointer(self):
        """Graph compila com checkpointer."""
        from langgraph.checkpoint.memory import InMemorySaver

        graph = build_whatsapp_graph(checkpointer=InMemorySaver())
        assert graph is not None

    def test_graph_contains_tool_nodes(self):
        """Story 2.2: Graph contém nós tools e collect_sources."""
        graph = build_whatsapp_graph()
        node_names = set(graph.get_graph().nodes.keys())
        assert "tools" in node_names
        assert "collect_sources" in node_names
        assert "orchestrate_llm" in node_names

    def test_retry_policy_on_tools_node(self):
        """Story 5.1 AC#2: ToolNode has RetryPolicy(max_attempts=3, backoff_factor=2.0)."""
        graph = build_whatsapp_graph()
        spec = graph.builder.nodes["tools"]
        assert spec.retry_policy is not None
        assert spec.retry_policy.max_attempts == 3
        assert spec.retry_policy.backoff_factor == 2.0

    def test_no_retry_policy_on_persist_node(self):
        """persist NÃO tem RetryPolicy (catches DatabaseError)."""
        graph = build_whatsapp_graph()
        spec = graph.builder.nodes["persist"]
        assert spec.retry_policy is None

    def test_no_retry_policy_on_identify_user(self):
        """Story 5.1: identify_user NÃO tem RetryPolicy (fallback graceful, side effects)."""
        graph = build_whatsapp_graph()
        spec = graph.builder.nodes["identify_user"]
        assert spec.retry_policy is None

    def test_no_retry_policy_on_load_context(self):
        """Story 5.1: load_context NÃO tem RetryPolicy (fallback graceful)."""
        graph = build_whatsapp_graph()
        spec = graph.builder.nodes["load_context"]
        assert spec.retry_policy is None

    def test_no_retry_policy_on_rate_limit(self):
        """Story 5.1: rate_limit NÃO tem RetryPolicy (fail-open)."""
        graph = build_whatsapp_graph()
        spec = graph.builder.nodes["rate_limit"]
        assert spec.retry_policy is None

    @patch("workflows.providers.checkpointer.get_checkpointer", new_callable=AsyncMock)
    async def test_get_graph_returns_singleton(self, mock_get_cp):
        """get_graph() retorna a mesma instância (singleton)."""
        import workflows.whatsapp.graph as graph_module

        mock_get_cp.return_value = None

        original = graph_module._compiled_graph
        try:
            graph_module._compiled_graph = None
            g1 = await get_graph()
            g2 = await get_graph()
            assert g1 is g2
        finally:
            graph_module._compiled_graph = original


@pytest.mark.django_db(transaction=True)
class TestGraphExecution:
    """Tests for graph execution flow."""

    @patch("workflows.whatsapp.nodes.rate_limit.RateLimiter")
    @patch("workflows.whatsapp.nodes.rate_limit.ConfigService")
    @patch("workflows.whatsapp.nodes.send_whatsapp.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.mark_as_read", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.load_context.CacheManager")
    @patch("workflows.whatsapp.nodes.identify_user.CacheManager")
    async def test_graph_executes_full_flow(
        self,
        mock_id_cache,
        mock_ctx_cache,
        mock_build_sys,
        mock_tracker_cls,
        mock_get_model,
        mock_mark,
        mock_send,
        mock_rl_config,
        mock_rl_limiter,
    ):
        """Story 4.1: Grafo executa flow completo com 7 nós."""
        from workflows.models import Message, User

        user = await User.objects.acreate(phone="5511999999999", subscription_tier="premium")

        _setup_mocks(mock_id_cache, mock_ctx_cache, mock_tracker_cls, mock_get_model)
        mock_build_sys.return_value = MagicMock()
        mock_mark.return_value = True
        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}
        mock_rl_limiter.check = AsyncMock(
            return_value=RateLimitResult(
                allowed=True,
                remaining_daily=999,
                daily_limit=1000,
                reason="",
            )
        )
        mock_rl_config.get = AsyncMock(return_value=2)

        graph = build_whatsapp_graph()
        result = await graph.ainvoke(_make_initial_state())

        # identify_user
        assert result["user_id"] == str(user.id)
        assert result["subscription_tier"] == "premium"
        # rate_limit — allowed
        assert result["rate_limit_exceeded"] is False
        # orchestrate_llm
        assert isinstance(result["messages"], list)
        assert result["cost_usd"] == 0.001
        assert any(
            isinstance(m, AIMessage) and m.content == "Resposta do LLM" for m in result["messages"]
        )
        # format_response
        assert result["formatted_response"]
        assert isinstance(result["additional_responses"], list)
        # send_whatsapp
        assert result["response_sent"] is True
        mock_send.assert_called()
        # persist — messages saved to DB
        msg_count = 0
        async for _ in Message.objects.filter(user=user):
            msg_count += 1
        assert msg_count == 2  # user + assistant

    @patch("workflows.whatsapp.nodes.rate_limit.RateLimiter")
    @patch("workflows.whatsapp.nodes.rate_limit.ConfigService")
    @patch("workflows.whatsapp.nodes.send_whatsapp.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.mark_as_read", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.load_context.CacheManager")
    @patch("workflows.whatsapp.nodes.identify_user.CacheManager")
    async def test_graph_with_checkpointer_accepts_thread_id(
        self,
        mock_id_cache,
        mock_ctx_cache,
        mock_build_sys,
        mock_tracker_cls,
        mock_get_model,
        mock_mark,
        mock_send,
        mock_rl_config,
        mock_rl_limiter,
    ):
        """Grafo compilado com checkpointer aceita thread_id."""
        from workflows.models import User

        await User.objects.acreate(phone="5511888888888", subscription_tier="free")

        mock_build_sys.return_value = MagicMock()
        _setup_mocks(
            mock_id_cache,
            mock_ctx_cache,
            mock_tracker_cls,
            mock_get_model,
            llm_content="test",
        )
        mock_mark.return_value = True
        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}
        mock_rl_limiter.check = AsyncMock(
            return_value=RateLimitResult(allowed=True, remaining_daily=9, daily_limit=10, reason="")
        )
        mock_rl_config.get = AsyncMock(return_value=2)

        from langgraph.checkpoint.memory import InMemorySaver

        graph = build_whatsapp_graph(checkpointer=InMemorySaver())
        initial_state = _make_initial_state(
            phone_number="5511888888888",
            user_message="Test",
            wamid="wamid.cp_test",
            trace_id="trace-cp",
        )

        result = await graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": "5511888888888"}},
        )
        assert result["user_id"]
        assert result["response_sent"] is True

    @patch("workflows.whatsapp.nodes.rate_limit.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.rate_limit.RateLimiter")
    @patch("workflows.whatsapp.nodes.rate_limit.ConfigService")
    @patch("workflows.whatsapp.nodes.identify_user.CacheManager")
    async def test_graph_ends_at_rate_limit_when_exceeded(
        self, mock_id_cache, mock_rl_config, mock_rl_limiter, mock_rl_send
    ):
        """Story 4.1: Grafo encerra quando rate_limit exceeded."""
        from workflows.models import User

        await User.objects.acreate(phone="5511999999999", subscription_tier="free")

        mock_id_cache.get_session = AsyncMock(return_value=None)
        mock_id_cache.cache_session = AsyncMock()
        mock_rl_limiter.check = AsyncMock(
            return_value=RateLimitResult(
                allowed=False,
                remaining_daily=0,
                daily_limit=10,
                reason="daily_exceeded",
            )
        )
        mock_rl_config.get = AsyncMock(
            return_value="Você atingiu seu limite de {limit} interações por hoje. Até lá!"
        )
        mock_rl_send.return_value = {"messages": [{"id": "wamid.rl"}]}

        graph = build_whatsapp_graph()
        result = await graph.ainvoke(_make_initial_state())

        # rate_limit blocked → pipeline ended
        assert result["rate_limit_exceeded"] is True
        assert result["remaining_daily"] == 0
        # send_whatsapp was NOT called (pipeline ended at rate_limit → END)
        assert result["response_sent"] is False
        # rate_limit node sent the message directly
        mock_rl_send.assert_awaited_once()


class TestSemaphoreConcurrency:
    """Tests for concurrency semaphore (NFR4)."""

    def test_semaphore_limit_is_50(self):
        """Semaphore limita concorrência a 50."""
        from workflows.views import _concurrency_semaphore

        assert _concurrency_semaphore._value == 50


@pytest.mark.django_db(transaction=True)
class TestGraphWebhookIntegration:
    """Grafo integrado com webhook processa mensagem corretamente."""

    @patch("workflows.views.get_pending_comment", new_callable=AsyncMock, return_value=None)
    @patch("workflows.views.is_feature_enabled", new_callable=AsyncMock, return_value=True)
    @patch("workflows.whatsapp.nodes.rate_limit.RateLimiter")
    @patch("workflows.whatsapp.nodes.rate_limit.ConfigService")
    @patch("workflows.whatsapp.nodes.send_whatsapp.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.mark_as_read", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.load_context.CacheManager")
    @patch("workflows.whatsapp.nodes.identify_user.CacheManager")
    @patch("workflows.views.is_duplicate_message", new_callable=AsyncMock, return_value=False)
    @patch("workflows.views.schedule_processing")
    @patch("workflows.views.get_graph")
    async def test_webhook_dispatches_graph_execution(
        self,
        mock_get_graph,
        mock_schedule,
        mock_dedup,
        mock_id_cache,
        mock_ctx_cache,
        mock_build_sys,
        mock_tracker_cls,
        mock_get_model,
        mock_mark,
        mock_send,
        mock_rl_config,
        mock_rl_limiter,
        mock_ff,
        mock_pending,
    ):
        """POST webhook → fire-and-forget → graph runs full flow."""

        mock_build_sys.return_value = MagicMock()
        _setup_mocks(
            mock_id_cache,
            mock_ctx_cache,
            mock_tracker_cls,
            mock_get_model,
            llm_content="ok",
        )
        mock_mark.return_value = True
        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}
        mock_rl_limiter.check = AsyncMock(
            return_value=RateLimitResult(allowed=True, remaining_daily=9, daily_limit=10, reason="")
        )
        mock_rl_config.get = AsyncMock(return_value=2)

        graph = build_whatsapp_graph()
        mock_get_graph.return_value = graph

        # Bypass debounce: schedule_processing calls _process_message directly
        async def bypass_debounce(phone, data, callback):
            await callback(data)

        mock_schedule.side_effect = bypass_debounce

        ts = str(int(time.time()))
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "BIZ_ID",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "15551234567",
                                    "phone_number_id": "PHONE_ID",
                                },
                                "messages": [
                                    {
                                        "from": "5511999999999",
                                        "id": "wamid.graph_test",
                                        "timestamp": ts,
                                        "type": "text",
                                        "text": {"body": "Teste integração"},
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }

        body = json.dumps(payload).encode()
        signature = "sha256=" + hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()

        client = AsyncClient()
        response = await client.post(
            "/webhook/whatsapp/",
            data=body,
            content_type="application/json",
            headers={"X-Hub-Signature-256": signature},
        )

        assert response.status_code == 200

        import asyncio

        from workflows.models import User

        # Poll for user creation (fire-and-forget task) with timeout
        user = None
        for _ in range(50):  # 5s max
            try:
                user = await User.objects.aget(phone="5511999999999")
                break
            except User.DoesNotExist:
                await asyncio.sleep(0.1)

        assert user is not None, "Fire-and-forget task did not complete within 5s"
        assert user.subscription_tier == "free"
