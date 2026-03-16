"""Tests for check_alerts management command (Story 7.3, AC #2, #3)."""

from decimal import Decimal
from io import StringIO
from unittest.mock import AsyncMock, patch

import pytest
from django.core.management import call_command

from workflows.models import CostLog, ErrorLog, Message, User


@pytest.mark.django_db(transaction=True)
class TestCheckAlertsCommand:
    @pytest.fixture
    def user(self):
        return User.objects.create(phone="5511999990300")

    def test_no_alerts_exit_zero(self):
        """Sem alertas: exit code 0 e mensagem de sucesso."""
        out = StringIO()
        call_command("check_alerts", stdout=out)
        assert "All metrics within thresholds" in out.getvalue()

    @patch(
        "workflows.services.alerting.ConfigService.get",
        new_callable=AsyncMock,
    )
    def test_cost_alert_exit_one(self, mock_config, user):
        """AC2: Custo excedido → exit code 1."""
        mock_config.return_value = 50.0
        CostLog.objects.create(
            user=user,
            provider="vertex",
            model="haiku",
            tokens_input=100,
            tokens_output=50,
            cost_usd=Decimal("60.0"),
        )
        out = StringIO()
        with pytest.raises(SystemExit) as exc_info:
            call_command("check_alerts", stdout=out)
        assert exc_info.value.code == 1
        assert "cost_threshold_exceeded" in out.getvalue()

    @patch(
        "workflows.services.alerting.ConfigService.get",
        new_callable=AsyncMock,
    )
    def test_error_rate_alert_exit_one(self, mock_config, user):
        """AC3: Taxa de erro excedida → exit code 1."""
        mock_config.return_value = 5.0
        Message.objects.create(user=user, content="q1", role="user")
        ErrorLog.objects.create(
            node="orchestrate_llm",
            error_type="GraphNodeError",
            error_message="err",
            trace_id="t1",
        )
        out = StringIO()
        with pytest.raises(SystemExit) as exc_info:
            call_command("check_alerts", stdout=out)
        assert exc_info.value.code == 1
        assert "error_rate_threshold_exceeded" in out.getvalue()

    def test_dry_run_shows_metrics(self):
        """--dry-run mostra métricas sem disparar alertas."""
        out = StringIO()
        call_command("check_alerts", "--dry-run", stdout=out)
        output = out.getvalue()
        assert "Metrics Summary" in output
        assert "cost_today_usd" in output
        assert "error_rate_24h" in output

    def test_dry_run_no_exit_one(self, user):
        """--dry-run NUNCA retorna exit code 1, mesmo com dados excedendo thresholds."""
        CostLog.objects.create(
            user=user,
            provider="vertex",
            model="haiku",
            tokens_input=100,
            tokens_output=50,
            cost_usd=Decimal("999.0"),
        )
        out = StringIO()
        # Should NOT raise SystemExit
        call_command("check_alerts", "--dry-run", stdout=out)
        assert "Metrics Summary" in out.getvalue()
