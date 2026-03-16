"""Service para agregação de métricas de qualidade."""

from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Sum
from django.utils import timezone

from workflows.models import CostLog, ErrorLog, Feedback, Message, ToolExecution


class MetricsService:
    @staticmethod
    async def get_daily_cost(date=None) -> Decimal:
        """Custo total de um dia específico (default: hoje)."""
        if date is None:
            date = timezone.now().date()
        result = await CostLog.objects.filter(created_at__date=date).aaggregate(
            total=Sum("cost_usd")
        )
        return result["total"] or Decimal("0")

    @staticmethod
    async def get_period_cost(days: int) -> Decimal:
        """Custo total nos últimos N dias."""
        since = timezone.now() - timedelta(days=days)
        result = await CostLog.objects.filter(created_at__gte=since).aaggregate(
            total=Sum("cost_usd")
        )
        return result["total"] or Decimal("0")

    @staticmethod
    async def get_satisfaction_rate(days: int = 7) -> float | None:
        """Taxa de satisfação: positive / (positive + negative). Ignora 'comment'."""
        since = timezone.now() - timedelta(days=days)
        qs = Feedback.objects.filter(
            created_at__gte=since,
            rating__in=["positive", "negative"],
        )
        total = await qs.acount()
        if total == 0:
            return None
        positive = await qs.filter(rating="positive").acount()
        return round(positive / total * 100, 1)

    @staticmethod
    async def get_average_latency(days: int = 7) -> float | None:
        """Latência média de tool executions em ms."""
        since = timezone.now() - timedelta(days=days)
        result = await ToolExecution.objects.filter(
            created_at__gte=since,
            latency_ms__isnull=False,
        ).aaggregate(avg=Avg("latency_ms"))
        return round(result["avg"], 1) if result["avg"] is not None else None

    @staticmethod
    async def get_error_rate(hours: int = 24) -> float:
        """Taxa de erro: errors / total_requests * 100."""
        since = timezone.now() - timedelta(hours=hours)
        error_count = await ErrorLog.objects.filter(created_at__gte=since).acount()
        request_count = await Message.objects.filter(created_at__gte=since, role="user").acount()
        if request_count == 0:
            return 0.0
        return round(error_count / request_count * 100, 2)

    @staticmethod
    async def get_error_breakdown(hours: int = 24) -> list[dict]:
        """Breakdown de erros por nó: count, top error_type, últimos 5 trace_ids."""
        since = timezone.now() - timedelta(hours=hours)

        # Single query — avoids N+1 pattern (1 query instead of 1+2N)
        errors: list[dict] = []
        async for err in (
            ErrorLog.objects.filter(created_at__gte=since)
            .order_by("-created_at")
            .values("node", "error_type", "trace_id")
        ):
            errors.append(err)

        if not errors:
            return []

        # Aggregate in Python — O(N) single pass
        node_counts: Counter[str] = Counter()
        node_error_types: defaultdict[str, Counter[str]] = defaultdict(Counter)
        node_trace_ids: defaultdict[str, list[str]] = defaultdict(list)

        for err in errors:
            node = err["node"]
            node_counts[node] += 1
            node_error_types[node][err["error_type"]] += 1
            if err["trace_id"] and len(node_trace_ids[node]) < 5:
                node_trace_ids[node].append(err["trace_id"])

        return [
            {
                "node": node,
                "count": count,
                "top_error_type": node_error_types[node].most_common(1)[0][0],
                "trace_ids": node_trace_ids[node],
            }
            for node, count in node_counts.most_common()
        ]

    @staticmethod
    async def get_metrics_summary() -> dict:
        """Resumo completo de métricas para dashboard/alerting."""
        today = timezone.now().date()
        return {
            "cost_today_usd": float(await MetricsService.get_daily_cost(today)),
            "cost_7d_usd": float(await MetricsService.get_period_cost(7)),
            "cost_30d_usd": float(await MetricsService.get_period_cost(30)),
            "satisfaction_rate_7d": await MetricsService.get_satisfaction_rate(7),
            "avg_latency_ms_7d": await MetricsService.get_average_latency(7),
            "error_rate_24h": await MetricsService.get_error_rate(24),
            "error_breakdown_24h": await MetricsService.get_error_breakdown(24),
        }
