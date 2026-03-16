"""Service para checagem de thresholds e emissão de alertas."""

import structlog

from workflows.services.config_service import ConfigService
from workflows.services.metrics import MetricsService

logger = structlog.get_logger(__name__)

# Defaults caso Config não tenha as chaves
DEFAULT_COST_THRESHOLD = 50.0  # USD/dia
DEFAULT_ERROR_RATE_THRESHOLD = 5.0  # percent


class AlertingService:
    @staticmethod
    async def _get_threshold(key: str, default: float) -> float:
        """Load threshold from ConfigService with fallback to default."""
        try:
            value = await ConfigService.get(key)
            return float(value)
        except Exception:
            logger.warning("alert_threshold_config_fallback", key=key, default=default)
            return default

    @staticmethod
    async def check_cost_threshold() -> dict | None:
        """Verifica se custo diário excede threshold. Retorna alerta dict ou None."""
        threshold = await AlertingService._get_threshold(
            "alert:cost_daily_threshold", DEFAULT_COST_THRESHOLD
        )
        daily_cost = float(await MetricsService.get_daily_cost())

        if daily_cost > threshold:
            alert = {
                "type": "cost_threshold_exceeded",
                "daily_cost_usd": daily_cost,
                "threshold_usd": threshold,
            }
            logger.critical(
                "alert_cost_threshold_exceeded",
                daily_cost_usd=daily_cost,
                threshold_usd=threshold,
            )
            return alert
        return None

    @staticmethod
    async def check_error_rate_threshold() -> dict | None:
        """Verifica se taxa de erro excede threshold. Retorna alerta dict com breakdown ou None."""
        threshold = await AlertingService._get_threshold(
            "alert:error_rate_threshold", DEFAULT_ERROR_RATE_THRESHOLD
        )
        error_rate = await MetricsService.get_error_rate(hours=24)

        if error_rate > threshold:
            breakdown = await MetricsService.get_error_breakdown(hours=24)
            alert = {
                "type": "error_rate_threshold_exceeded",
                "error_rate_percent": error_rate,
                "threshold_percent": threshold,
                "breakdown": breakdown,
            }
            logger.critical(
                "alert_error_rate_exceeded",
                error_rate_percent=error_rate,
                threshold_percent=threshold,
                top_node=breakdown[0]["node"] if breakdown else "unknown",
                top_error_type=breakdown[0]["top_error_type"] if breakdown else "unknown",
                trace_ids=breakdown[0]["trace_ids"][:5] if breakdown else [],
            )
            return alert
        return None

    @staticmethod
    async def run_all_checks() -> list[dict]:
        """Executa todos os checks de threshold. Retorna lista de alertas disparados."""
        alerts = []
        checks = [
            AlertingService.check_cost_threshold,
            AlertingService.check_error_rate_threshold,
        ]
        for check in checks:
            try:
                result = await check()
                if result:
                    alerts.append(result)
            except Exception:
                logger.exception("alert_check_failed", check=check.__name__)
        return alerts
