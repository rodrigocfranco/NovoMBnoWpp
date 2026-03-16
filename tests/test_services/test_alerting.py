"""Tests for AlertingService (Story 7.3, AC #2, #3)."""

import logging
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from workflows.models import CostLog, ErrorLog, Message, User
from workflows.services.alerting import (
    DEFAULT_COST_THRESHOLD,
    DEFAULT_ERROR_RATE_THRESHOLD,
    AlertingService,
)


@pytest.mark.django_db(transaction=True)
class TestCheckCostThreshold:
    @pytest.fixture
    def user(self):
        return User.objects.create(phone="5511999990200")

    @patch("workflows.services.alerting.ConfigService.get", new_callable=AsyncMock)
    async def test_no_alert_when_below_threshold(self, mock_config, user):
        """Custo abaixo do threshold não gera alerta."""
        mock_config.return_value = 50.0
        await CostLog.objects.acreate(
            user=user,
            provider="vertex",
            model="haiku",
            tokens_input=100,
            tokens_output=50,
            cost_usd=Decimal("10.0"),
        )
        result = await AlertingService.check_cost_threshold()
        assert result is None

    @patch("workflows.services.alerting.ConfigService.get", new_callable=AsyncMock)
    async def test_alert_when_above_threshold(self, mock_config, user):
        """AC2: Custo acima do threshold gera alerta CRITICAL."""
        mock_config.return_value = 50.0
        await CostLog.objects.acreate(
            user=user,
            provider="vertex",
            model="haiku",
            tokens_input=100,
            tokens_output=50,
            cost_usd=Decimal("60.0"),
        )
        result = await AlertingService.check_cost_threshold()
        assert result is not None
        assert result["type"] == "cost_threshold_exceeded"
        assert result["daily_cost_usd"] == 60.0
        assert result["threshold_usd"] == 50.0

    @patch("workflows.services.alerting.ConfigService.get", new_callable=AsyncMock)
    async def test_alert_logs_critical(self, mock_config, user, caplog):
        """AC2: Alerta emite log CRITICAL."""
        mock_config.return_value = 50.0
        await CostLog.objects.acreate(
            user=user,
            provider="vertex",
            model="haiku",
            tokens_input=100,
            tokens_output=50,
            cost_usd=Decimal("60.0"),
        )
        with caplog.at_level(logging.CRITICAL):
            await AlertingService.check_cost_threshold()
        assert any("alert_cost_threshold_exceeded" in r.message for r in caplog.records)

    async def test_no_alert_when_cost_zero_with_config_fallback(self):
        """ConfigService sem config no DB → fallback default → custo 0 < threshold."""
        result = await AlertingService.check_cost_threshold()
        assert result is None


@pytest.mark.django_db(transaction=True)
class TestCheckErrorRateThreshold:
    @pytest.fixture
    def user(self):
        return User.objects.create(phone="5511999990201")

    @patch("workflows.services.alerting.ConfigService.get", new_callable=AsyncMock)
    async def test_no_alert_when_below_threshold(self, mock_config, user):
        """Taxa de erro abaixo do threshold não gera alerta."""
        mock_config.return_value = 5.0
        await Message.objects.acreate(user=user, content="q1", role="user")
        # 0 errors / 1 request = 0% < 5%
        result = await AlertingService.check_error_rate_threshold()
        assert result is None

    @patch("workflows.services.alerting.ConfigService.get", new_callable=AsyncMock)
    async def test_alert_when_above_threshold(self, mock_config, user):
        """AC3: Taxa de erro acima do threshold gera alerta com breakdown."""
        mock_config.return_value = 5.0
        await Message.objects.acreate(user=user, content="q1", role="user")
        await ErrorLog.objects.acreate(
            node="orchestrate_llm",
            error_type="GraphNodeError",
            error_message="err",
            trace_id="t1",
        )
        # 1 error / 1 request = 100% > 5%
        result = await AlertingService.check_error_rate_threshold()
        assert result is not None
        assert result["type"] == "error_rate_threshold_exceeded"
        assert result["error_rate_percent"] == 100.0
        assert result["threshold_percent"] == 5.0
        assert len(result["breakdown"]) == 1
        assert result["breakdown"][0]["node"] == "orchestrate_llm"

    @patch("workflows.services.alerting.ConfigService.get", new_callable=AsyncMock)
    async def test_alert_logs_critical_with_breakdown(self, mock_config, user, caplog):
        """AC3: Alerta emite log CRITICAL com nó, tipo de erro, trace_ids."""
        mock_config.return_value = 5.0
        await Message.objects.acreate(user=user, content="q1", role="user")
        await ErrorLog.objects.acreate(
            node="orchestrate_llm",
            error_type="GraphNodeError",
            error_message="err",
            trace_id="trace-alert-001",
        )
        with caplog.at_level(logging.CRITICAL):
            await AlertingService.check_error_rate_threshold()
        assert any("alert_error_rate_exceeded" in r.message for r in caplog.records)


@pytest.mark.django_db(transaction=True)
class TestRunAllChecks:
    @pytest.fixture
    def user(self):
        return User.objects.create(phone="5511999990202")

    @patch("workflows.services.alerting.ConfigService.get", new_callable=AsyncMock)
    async def test_returns_empty_when_all_ok(self, mock_config, user):
        mock_config.return_value = 50.0
        result = await AlertingService.run_all_checks()
        assert result == []

    @patch("workflows.services.alerting.ConfigService.get", new_callable=AsyncMock)
    async def test_returns_both_alerts_when_both_exceeded(self, mock_config, user):
        def config_by_key(key):
            return 50.0 if key == "alert:cost_daily_threshold" else 5.0

        mock_config.side_effect = config_by_key
        await CostLog.objects.acreate(
            user=user,
            provider="vertex",
            model="haiku",
            tokens_input=100,
            tokens_output=50,
            cost_usd=Decimal("60.0"),
        )
        await Message.objects.acreate(user=user, content="q1", role="user")
        await ErrorLog.objects.acreate(
            node="orchestrate_llm",
            error_type="GraphNodeError",
            error_message="err",
            trace_id="t1",
        )
        result = await AlertingService.run_all_checks()
        assert len(result) == 2
        types = [a["type"] for a in result]
        assert "cost_threshold_exceeded" in types
        assert "error_rate_threshold_exceeded" in types


@pytest.mark.django_db(transaction=True)
class TestGetThresholdFallback:
    async def test_fallback_to_default_cost(self):
        """ConfigService não tem a chave → usa DEFAULT_COST_THRESHOLD."""
        threshold = await AlertingService._get_threshold(
            "alert:cost_daily_threshold", DEFAULT_COST_THRESHOLD
        )
        assert threshold == DEFAULT_COST_THRESHOLD

    async def test_fallback_to_default_error_rate(self):
        """ConfigService não tem a chave → usa DEFAULT_ERROR_RATE_THRESHOLD."""
        threshold = await AlertingService._get_threshold(
            "alert:error_rate_threshold", DEFAULT_ERROR_RATE_THRESHOLD
        )
        assert threshold == DEFAULT_ERROR_RATE_THRESHOLD
