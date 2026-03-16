"""Tests for MetricsService (Story 7.3, AC #1).

Retro watch item: NO over-mocking. All tests use real DB with @pytest.mark.django_db.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from workflows.models import CostLog, ErrorLog, Feedback, Message, ToolExecution, User
from workflows.services.metrics import MetricsService


@pytest.mark.django_db(transaction=True)
class TestGetDailyCost:
    @pytest.fixture
    def user(self):
        return User.objects.create(phone="5511999990100")

    async def test_returns_sum_for_today(self, user):
        await CostLog.objects.acreate(
            user=user,
            provider="vertex",
            model="haiku",
            tokens_input=100,
            tokens_output=50,
            cost_usd=Decimal("0.001"),
        )
        await CostLog.objects.acreate(
            user=user,
            provider="vertex",
            model="haiku",
            tokens_input=200,
            tokens_output=100,
            cost_usd=Decimal("0.002"),
        )
        result = await MetricsService.get_daily_cost()
        assert result == Decimal("0.003")

    async def test_returns_zero_when_no_data(self):
        result = await MetricsService.get_daily_cost()
        assert result == Decimal("0")

    async def test_filters_by_specific_date(self, user):
        await CostLog.objects.acreate(
            user=user,
            provider="vertex",
            model="haiku",
            tokens_input=100,
            tokens_output=50,
            cost_usd=Decimal("0.005"),
        )
        yesterday = (timezone.now() - timedelta(days=1)).date()
        result = await MetricsService.get_daily_cost(yesterday)
        assert result == Decimal("0")


@pytest.mark.django_db(transaction=True)
class TestGetPeriodCost:
    @pytest.fixture
    def user(self):
        return User.objects.create(phone="5511999990101")

    async def test_returns_sum_for_period(self, user):
        await CostLog.objects.acreate(
            user=user,
            provider="vertex",
            model="haiku",
            tokens_input=100,
            tokens_output=50,
            cost_usd=Decimal("0.010"),
        )
        result = await MetricsService.get_period_cost(7)
        assert result == Decimal("0.010")

    async def test_returns_zero_when_no_data(self):
        result = await MetricsService.get_period_cost(30)
        assert result == Decimal("0")


@pytest.mark.django_db(transaction=True)
class TestGetSatisfactionRate:
    @pytest.fixture
    def user(self):
        return User.objects.create(phone="5511999990102")

    @pytest.fixture
    def msg(self, user):
        return Message.objects.create(user=user, content="test", role="assistant")

    async def test_returns_rate(self, user, msg):
        await Feedback.objects.acreate(user=user, message=msg, rating="positive")
        # Need a second message for second feedback (unique constraint)
        msg2 = await Message.objects.acreate(user=user, content="test2", role="assistant")
        await Feedback.objects.acreate(user=user, message=msg2, rating="negative")
        result = await MetricsService.get_satisfaction_rate(7)
        assert result == 50.0

    async def test_returns_none_when_no_data(self):
        result = await MetricsService.get_satisfaction_rate(7)
        assert result is None

    async def test_ignores_comment_rating(self, user, msg):
        await Feedback.objects.acreate(user=user, message=msg, rating="comment")
        result = await MetricsService.get_satisfaction_rate(7)
        assert result is None

    async def test_all_positive(self, user, msg):
        await Feedback.objects.acreate(user=user, message=msg, rating="positive")
        result = await MetricsService.get_satisfaction_rate(7)
        assert result == 100.0


@pytest.mark.django_db(transaction=True)
class TestGetAverageLatency:
    @pytest.fixture
    def user(self):
        return User.objects.create(phone="5511999990103")

    async def test_returns_average(self, user):
        await ToolExecution.objects.acreate(
            user=user,
            tool_name="rag",
            latency_ms=100,
            success=True,
        )
        await ToolExecution.objects.acreate(
            user=user,
            tool_name="web_search",
            latency_ms=200,
            success=True,
        )
        result = await MetricsService.get_average_latency(7)
        assert result == 150.0

    async def test_returns_none_when_no_data(self):
        result = await MetricsService.get_average_latency(7)
        assert result is None

    async def test_ignores_null_latency(self, user):
        await ToolExecution.objects.acreate(
            user=user,
            tool_name="rag",
            latency_ms=None,
            success=True,
        )
        result = await MetricsService.get_average_latency(7)
        assert result is None


@pytest.mark.django_db(transaction=True)
class TestGetErrorRate:
    @pytest.fixture
    def user(self):
        return User.objects.create(phone="5511999990104")

    async def test_returns_rate(self, user):
        await Message.objects.acreate(user=user, content="q1", role="user")
        await Message.objects.acreate(user=user, content="q2", role="user")
        await ErrorLog.objects.acreate(
            node="orchestrate_llm",
            error_type="GraphNodeError",
            error_message="err",
        )
        result = await MetricsService.get_error_rate(24)
        assert result == 50.0

    async def test_returns_zero_when_no_errors(self, user):
        await Message.objects.acreate(user=user, content="q1", role="user")
        result = await MetricsService.get_error_rate(24)
        assert result == 0.0

    async def test_returns_zero_when_no_requests(self):
        result = await MetricsService.get_error_rate(24)
        assert result == 0.0

    async def test_returns_zero_when_errors_exist_but_no_user_messages(self):
        """Edge case: ErrorLogs existem mas zero Messages(role='user') → retorna 0.0."""
        await ErrorLog.objects.acreate(
            node="orchestrate_llm",
            error_type="GraphNodeError",
            error_message="err",
        )
        result = await MetricsService.get_error_rate(24)
        assert result == 0.0


@pytest.mark.django_db(transaction=True)
class TestGetErrorBreakdown:
    async def test_returns_breakdown_by_node(self):
        await ErrorLog.objects.acreate(
            node="orchestrate_llm",
            error_type="GraphNodeError",
            error_message="err1",
            trace_id="t1",
        )
        await ErrorLog.objects.acreate(
            node="orchestrate_llm",
            error_type="GraphNodeError",
            error_message="err2",
            trace_id="t2",
        )
        await ErrorLog.objects.acreate(
            node="send_whatsapp",
            error_type="TimeoutError",
            error_message="err3",
            trace_id="t3",
        )
        result = await MetricsService.get_error_breakdown(24)
        assert len(result) == 2
        # orchestrate_llm has more errors → first
        assert result[0]["node"] == "orchestrate_llm"
        assert result[0]["count"] == 2
        assert result[0]["top_error_type"] == "GraphNodeError"
        assert "t1" in result[0]["trace_ids"] or "t2" in result[0]["trace_ids"]

    async def test_returns_empty_when_no_errors(self):
        result = await MetricsService.get_error_breakdown(24)
        assert result == []

    async def test_excludes_empty_trace_ids(self):
        await ErrorLog.objects.acreate(
            node="test",
            error_type="Error",
            error_message="err",
            trace_id="",
        )
        result = await MetricsService.get_error_breakdown(24)
        assert len(result) == 1
        assert result[0]["trace_ids"] == []


@pytest.mark.django_db(transaction=True)
class TestGetMetricsSummary:
    async def test_returns_all_keys(self):
        result = await MetricsService.get_metrics_summary()
        assert "cost_today_usd" in result
        assert "cost_7d_usd" in result
        assert "cost_30d_usd" in result
        assert "satisfaction_rate_7d" in result
        assert "avg_latency_ms_7d" in result
        assert "error_rate_24h" in result
        assert "error_breakdown_24h" in result

    async def test_returns_safe_defaults_with_empty_data(self):
        result = await MetricsService.get_metrics_summary()
        assert result["cost_today_usd"] == 0.0
        assert result["cost_7d_usd"] == 0.0
        assert result["cost_30d_usd"] == 0.0
        assert result["satisfaction_rate_7d"] is None
        assert result["avg_latency_ms_7d"] is None
        assert result["error_rate_24h"] == 0.0
        assert result["error_breakdown_24h"] == []
