"""Tests for persist node (AC2, AC5)."""

from decimal import Decimal

import pytest

from workflows.whatsapp.nodes.persist import persist


def _make_state(**overrides) -> dict:
    """Create a minimal WhatsAppState-like dict for testing."""
    state = {
        "phone_number": "5511999999999",
        "user_message": "Pergunta do usuário",
        "message_type": "text",
        "media_url": None,
        "wamid": "wamid.test",
        "user_id": "1",
        "subscription_tier": "free",
        "messages": [],
        "formatted_response": "Resposta formatada.",
        "additional_responses": [],
        "response_sent": True,
        "trace_id": "trace-test",
        "cost_usd": 0.001,
        "retrieved_sources": [],
        "cited_source_indices": [],
        "web_sources": [],
        "transcribed_text": "",
        "provider_used": "vertex_ai",
        # Cost tracking fields (Story 7.1)
        "tokens_input": 500,
        "tokens_output": 200,
        "tokens_cache_read": 300,
        "tokens_cache_creation": 100,
        "model_used": "claude-haiku-4-5@20251001",
        "tool_executions": [],
    }
    state.update(overrides)
    return state


@pytest.mark.django_db(transaction=True)
class TestPersistNode:
    """Tests for persist graph node."""

    async def test_creates_user_and_assistant_messages(self):
        """AC5: persist cria 2 Messages (user + assistant) via Django ORM."""
        from workflows.models import Message, User

        user = await User.objects.acreate(phone="5511999999999", subscription_tier="free")
        state = _make_state(user_id=str(user.id))

        await persist(state)

        messages = []
        async for msg in Message.objects.filter(user=user).order_by("created_at"):
            messages.append(msg)

        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "Pergunta do usuário"
        assert messages[0].message_type == "text"
        assert messages[1].role == "assistant"
        assert messages[1].content == "Resposta formatada."
        assert messages[1].message_type == "text"

    async def test_saves_cost_usd(self):
        """AC5: persist salva cost_usd na mensagem do assistente."""
        from workflows.models import Message, User

        user = await User.objects.acreate(phone="5511888888888", subscription_tier="premium")
        state = _make_state(user_id=str(user.id), cost_usd=0.0023)

        await persist(state)

        assistant_msg = await Message.objects.aget(user=user, role="assistant")
        assert assistant_msg.cost_usd == Decimal("0.0023").quantize(Decimal("0.000001"))

    async def test_returns_empty_dict(self):
        """AC5: persist retorna dict parcial vazio."""
        from workflows.models import User

        user = await User.objects.acreate(phone="5511666666666", subscription_tier="free")
        state = _make_state(user_id=str(user.id))

        result = await persist(state)
        assert result == {}


@pytest.mark.django_db(transaction=True)
class TestPersistCostLog:
    """Tests for CostLog creation in persist (Story 7.1, AC#2)."""

    async def test_creates_costlog_with_token_breakdown(self):
        """AC#2: persist cria CostLog com token breakdown correto."""
        from workflows.models import CostLog, User

        user = await User.objects.acreate(phone="5511990000001", subscription_tier="free")
        state = _make_state(
            user_id=str(user.id),
            cost_usd=0.0024,
            provider_used="vertex_ai",
            model_used="claude-haiku-4-5@20251001",
            tokens_input=500,
            tokens_output=200,
            tokens_cache_read=300,
            tokens_cache_creation=100,
        )

        await persist(state)

        log = await CostLog.objects.aget(user=user)
        assert log.provider == "vertex_ai"
        assert log.model == "claude-haiku-4-5@20251001"
        assert log.tokens_input == 500
        assert log.tokens_output == 200
        assert log.tokens_cache_read == 300
        assert log.tokens_cache_creation == 100
        assert log.cost_usd == Decimal("0.0024")

    async def test_costlog_created_when_zero_cost(self):
        """Review Fix M1: persist cria CostLog mesmo com cost_usd == 0 para tracking completo."""
        from workflows.models import CostLog, User

        user = await User.objects.acreate(phone="5511990000002", subscription_tier="free")
        state = _make_state(user_id=str(user.id), cost_usd=0.0)

        await persist(state)

        count = await CostLog.objects.filter(user=user).acount()
        assert count == 1
        log = await CostLog.objects.aget(user=user)
        assert log.cost_usd == Decimal("0")

    async def test_no_costlog_when_none_cost(self):
        """AC#2: persist NÃO cria CostLog quando cost_usd é None."""
        from workflows.models import CostLog, User

        user = await User.objects.acreate(phone="5511990000003", subscription_tier="free")
        state = _make_state(user_id=str(user.id), cost_usd=None)

        await persist(state)

        count = await CostLog.objects.filter(user=user).acount()
        assert count == 0


@pytest.mark.django_db(transaction=True)
class TestPersistToolExecution:
    """Tests for ToolExecution creation in persist (Story 7.1, AC#2)."""

    async def test_creates_tool_executions(self):
        """AC#2: persist cria ToolExecution para cada tool chamada."""
        from workflows.models import ToolExecution, User

        user = await User.objects.acreate(phone="5511990000004", subscription_tier="free")
        state = _make_state(
            user_id=str(user.id),
            tool_executions=[
                {"tool_name": "drug_lookup", "latency_ms": 150, "success": True, "error": None},
                {"tool_name": "rag_search", "latency_ms": 200, "success": True, "error": None},
            ],
        )

        await persist(state)

        executions = []
        async for te in ToolExecution.objects.filter(user=user).order_by("created_at"):
            executions.append(te)

        assert len(executions) == 2
        assert executions[0].tool_name == "drug_lookup"
        assert executions[0].latency_ms == 150
        assert executions[0].success is True
        assert executions[1].tool_name == "rag_search"

    async def test_creates_tool_execution_with_error(self):
        """AC#2: persist cria ToolExecution com error quando tool falha."""
        from workflows.models import ToolExecution, User

        user = await User.objects.acreate(phone="5511990000005", subscription_tier="free")
        state = _make_state(
            user_id=str(user.id),
            tool_executions=[
                {
                    "tool_name": "web_search",
                    "latency_ms": 5000,
                    "success": False,
                    "error": "Timeout",
                },
            ],
        )

        await persist(state)

        te = await ToolExecution.objects.aget(user=user)
        assert te.tool_name == "web_search"
        assert te.success is False
        assert te.error == "Timeout"

    async def test_no_tool_executions_when_empty(self):
        """AC#2: persist NÃO cria ToolExecution quando lista vazia."""
        from workflows.models import ToolExecution, User

        user = await User.objects.acreate(phone="5511990000006", subscription_tier="free")
        state = _make_state(user_id=str(user.id), tool_executions=[])

        await persist(state)

        count = await ToolExecution.objects.filter(user=user).acount()
        assert count == 0

    async def test_costlog_and_tool_executions_together(self):
        """AC#2: persist cria CostLog + ToolExecution na mesma chamada."""
        from workflows.models import CostLog, ToolExecution, User

        user = await User.objects.acreate(phone="5511990000007", subscription_tier="free")
        state = _make_state(
            user_id=str(user.id),
            cost_usd=0.002,
            tool_executions=[
                {"tool_name": "drug_lookup", "latency_ms": 100, "success": True, "error": None},
            ],
        )

        await persist(state)

        cost_count = await CostLog.objects.filter(user=user).acount()
        tool_count = await ToolExecution.objects.filter(user=user).acount()
        assert cost_count == 1
        assert tool_count == 1
