# Story 7.3: Métricas de Qualidade e Alertas

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a equipe Medway,
I want monitorar métricas de qualidade e receber alertas quando thresholds são ultrapassados,
So that reajo proativamente a problemas antes que impactem os alunos.

## Acceptance Criteria

1. **AC1 — Métricas via Django Admin** (FR30)
   **Given** o Django Admin com dados de CostLog, Feedback, Message, ToolExecution
   **When** a equipe acessa o admin
   **Then** pode consultar: custo agregado por dia/semana/mês, taxa de satisfação (positivo/total), latência média (via ToolExecution), taxa de erro por nó

2. **AC2 — Alerta de custo diário** (FR31, NFR9)
   **Given** o gasto diário excede threshold configurável (ex: $50/dia)
   **When** o sistema detecta via checagem periódica
   **Then** envia alerta (log CRITICAL + notificação configurável)

3. **AC3 — Alerta de taxa de erro** (FR31)
   **Given** a taxa de erro excede threshold (ex: > 5%)
   **When** o sistema detecta
   **Then** emite alerta com: nó com mais falhas, tipo de erro mais frequente, últimos 5 trace_ids para investigação

## Tasks / Subtasks

- [x] Task 1: Criar modelo ErrorLog para rastreamento queryable de erros (AC: #1, #3)
  - [x] 1.1 Adicionar `ErrorLog` ao `workflows/models.py` com campos: user (FK nullable), node (CharField 100), error_type (CharField 100), error_message (TextField), trace_id (CharField 36), created_at — indexes em [node], [-created_at]
  - [x] 1.2 Criar migration `workflows/migrations/0018_add_errorlog.py` (nota: 0018 pois 0015-0017 já existiam)
  - [x] 1.3 Registrar `ErrorLogAdmin` em `admin.py` com list_display, list_filter, date_hierarchy, readonly_fields
  - [x] 1.4 Testes: model creation, __str__, indexes, admin registration (15 testes)

- [x] Task 2: Integrar ErrorLog nos error handlers existentes (AC: #3)
  - [x] 2.1 Em `views.py`: no catch de `GraphNodeError`, criar `ErrorLog` (node=exc.node, error_type, trace_id)
  - [x] 2.2 Em `views.py`: no catch de `Exception` genérica, criar `ErrorLog` (node="unknown", error_type, trace_id)
  - [x] 2.3 Manter padrão best-effort: `ErrorLog.objects.acreate()` dentro de `try/except` — NUNCA bloquear fallback ao usuário
  - [x] 2.4 Testes: error log criado em graph_node_error, error log criado em graph_execution_error, fallback não bloqueado por falha DB (5 testes)

- [x] Task 3: Criar MetricsService com queries de agregação (AC: #1)
  - [x] 3.1 Criar `workflows/services/metrics.py` com classe `MetricsService`
  - [x] 3.2 `get_daily_cost(date=None)` → `CostLog.objects.filter(created_at__date=date).aaggregate(Sum("cost_usd"))`
  - [x] 3.3 `get_period_cost(days)` → custo agregado nos últimos N dias
  - [x] 3.4 `get_satisfaction_rate(days=7)` → `Feedback.objects.filter(rating__in=["positive","negative"])` → positive / total
  - [x] 3.5 `get_average_latency(days=7)` → `ToolExecution.objects.aaggregate(Avg("latency_ms"))`
  - [x] 3.6 `get_error_rate(hours=24)` → `ErrorLog.objects.filter().acount()` / `Message.objects.filter(role="user").acount()`
  - [x] 3.7 `get_error_breakdown(hours=24)` → agregação por node com Count, top error_types, últimos 5 trace_ids
  - [x] 3.8 `get_metrics_summary()` → dict combinando todas as métricas
  - [x] 3.9 Testes unitários: cada método com dados conhecidos (`@pytest.mark.django_db` com BD real) (20 testes)

- [x] Task 4: Criar AlertingService com checagem de thresholds (AC: #2, #3)
  - [x] 4.1 Criar `workflows/services/alerting.py` com classe `AlertingService`
  - [x] 4.2 `check_cost_threshold()` → compara custo diário (MetricsService) com threshold do ConfigService → log CRITICAL se excedido
  - [x] 4.3 `check_error_rate_threshold()` → compara taxa de erro com threshold → log CRITICAL com breakdown (nó, tipo, trace_ids)
  - [x] 4.4 `run_all_checks()` → executa todos os checks, retorna lista de alertas disparados
  - [x] 4.5 Testes: threshold não excedido (sem alerta), threshold excedido (CRITICAL logado), ConfigService fallback (threshold default) (11 testes)

- [x] Task 5: Criar Config entries para thresholds (AC: #2, #3)
  - [x] 5.1 Data migration `0019_add_alert_configs.py` com entries:
    - `alert:cost_daily_threshold` = `50.0`
    - `alert:error_rate_threshold` = `5.0`
  - [x] 5.2 Testes: migration verificada via script, configs criadas corretamente

- [x] Task 6: Criar management command check_alerts (AC: #2, #3)
  - [x] 6.1 Criar `workflows/management/__init__.py` e `workflows/management/commands/__init__.py`
  - [x] 6.2 Criar `workflows/management/commands/check_alerts.py` com `BaseCommand`
  - [x] 6.3 Comando chama `AlertingService.run_all_checks()` usando `async_to_sync`
  - [x] 6.4 Exit code 1 se alertas disparados, 0 se OK
  - [x] 6.5 Opção `--dry-run` para exibir métricas sem disparar alertas
  - [x] 6.6 Testes: comando roda sem erros, retorna exit code correto (5 testes)

- [x] Task 7: Testes end-to-end + lint (AC: #1, #2, #3)
  - [x] 7.1 Teste integração: cenário completo com CostLog + ErrorLog → check_alerts dispara CRITICAL (via test_alerting.py::test_returns_both_alerts_when_both_exceeded)
  - [x] 7.2 Teste: métricas com dados vazios retornam defaults seguros (0, 0.0, None) (via test_metrics.py::test_returns_safe_defaults_with_empty_data)
  - [x] 7.3 Teste: MetricsService com dados reais no DB (django_db) — todos os 20 testes usam BD real
  - [x] 7.4 `uv run ruff check .` e `uv run ruff format --check .` passam (novos arquivos limpos)
  - [x] 7.5 `uv run pytest tests/ --ignore=tests/e2e --ignore=tests/integration` — 730 passed, 3 pre-existing failures

## Dev Notes

### O que já existe (NÃO reimplementar)

| Componente | Status Atual | O que falta (esta story) |
|------------|-------------|--------------------------|
| `CostLog` model | Implementado (Story 7.1) — user, provider, model, tokens_*, cost_usd, created_at | Manter (usado para agregações) |
| `ToolExecution` model | Implementado (Story 7.1) — tool_name, latency_ms, success, error | Manter (usado para latência e erro de tools) |
| `Feedback` model | Implementado (Story 6.1) — rating [positive/negative/comment], comment | Manter (usado para satisfação) |
| `Message` model | Implementado (Story 1.1) — role, content, created_at | Manter (usado para total de requests) |
| `CostLogAdmin` | Implementado — list_display, date_hierarchy, readonly_fields | Manter (já permite consulta por período) |
| `ToolExecutionAdmin` | Implementado — list_display, list_filter | Manter |
| `FeedbackAdmin` | Implementado — date_hierarchy, has_comment custom | Manter |
| `ConfigService.get(key)` | Implementado — async, raises ValidationError | Usar para thresholds |
| structlog JSON | Implementado — sanitize_pii, trace_id, JSON rendering | Usar para alertas CRITICAL |
| Langfuse tracing | Implementado (Story 7.2) — traces end-to-end, fire-and-forget | Complementa (alertas disparam CRITICAL log que aparece nos traces) |
| Error handlers em views.py | Implementados — `GraphNodeError` + `Exception` genérica | **ADICIONAR** ErrorLog.acreate() nos catch blocks |
| `ErrorLog` model | **NÃO existe** | **CRIAR** |
| `MetricsService` | **NÃO existe** | **CRIAR** |
| `AlertingService` | **NÃO existe** | **CRIAR** |
| Management command | **NÃO existe** | **CRIAR** |
| Config thresholds | **NÃO existem** | **CRIAR** via data migration |

### ErrorLog model — Schema exato

```python
class ErrorLog(models.Model):
    """Registro de erros do pipeline para métricas queryable via Django Admin."""

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="error_logs"
    )
    node = models.CharField(max_length=100)  # e.g. "orchestrate_llm", "send_whatsapp", "unknown"
    error_type = models.CharField(max_length=100)  # e.g. "GraphNodeError", "TimeoutError"
    error_message = models.TextField()
    trace_id = models.CharField(max_length=36, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "error_logs"
        indexes = [
            models.Index(fields=["node"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self) -> str:
        return f"ErrorLog({self.node}, {self.error_type})"
```

**Notas:**
- `user` é `SET_NULL` + `null=True` porque erros podem ocorrer antes da identificação do usuário (ex: erro no nó identify_user)
- `trace_id` permite correlação com Langfuse e structlog
- Indexes em `node` (para agregação por nó) e `-created_at` (para queries recentes)

### ErrorLogAdmin — Configuração exata

```python
@admin.register(ErrorLog)
class ErrorLogAdmin(admin.ModelAdmin):
    list_display = ("node", "error_type", "user", "trace_id", "created_at")
    list_filter = ("node", "error_type", "created_at")
    date_hierarchy = "created_at"
    search_fields = ("trace_id", "error_message")
    raw_id_fields = ("user",)
    readonly_fields = ("user", "node", "error_type", "error_message", "trace_id", "created_at")
```

### Integração ErrorLog em views.py — Padrão exato

Adicionar APÓS o `logger.critical()` e ANTES do `await _send_fallback(phone)` em cada catch block:

```python
# views.py — dentro do except GraphNodeError
try:
    user_obj = await User.objects.filter(phone=phone).afirst()
    await ErrorLog.objects.acreate(
        user=user_obj,
        node=exc.node,
        error_type=type(exc).__name__,
        error_message=str(exc)[:1000],
        trace_id=trace_id,
    )
except Exception:
    logger.warning("error_log_persist_failed", phone=phone)
```

**CRÍTICO:**
- ErrorLog.acreate() DEVE estar dentro de try/except — NUNCA bloquear o fallback ao usuário
- Truncar error_message em 1000 chars para evitar excesso no banco
- `trace_id` vem da variável local capturada no início de `_process_message()`
- User pode ser None (filtro retorna None se phone não existe)

### MetricsService — Implementação exata

```python
# workflows/services/metrics.py
"""Service para agregação de métricas de qualidade."""

from datetime import timedelta
from decimal import Decimal

import structlog
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from workflows.models import CostLog, ErrorLog, Feedback, Message, ToolExecution

logger = structlog.get_logger(__name__)


class MetricsService:
    @staticmethod
    async def get_daily_cost(date=None) -> Decimal:
        """Custo total de um dia específico (default: hoje)."""
        if date is None:
            date = timezone.now().date()
        result = await CostLog.objects.filter(
            created_at__date=date
        ).aaggregate(total=Sum("cost_usd"))
        return result["total"] or Decimal("0")

    @staticmethod
    async def get_period_cost(days: int) -> Decimal:
        """Custo total nos últimos N dias."""
        since = timezone.now() - timedelta(days=days)
        result = await CostLog.objects.filter(
            created_at__gte=since
        ).aaggregate(total=Sum("cost_usd"))
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
        request_count = await Message.objects.filter(
            created_at__gte=since, role="user"
        ).acount()
        if request_count == 0:
            return 0.0
        return round(error_count / request_count * 100, 2)

    @staticmethod
    async def get_error_breakdown(hours: int = 24) -> list[dict]:
        """Breakdown de erros por nó: count, top error_type, últimos 5 trace_ids."""
        since = timezone.now() - timedelta(hours=hours)
        qs = ErrorLog.objects.filter(created_at__gte=since)

        # Agregação por node usando async for em values().annotate()
        breakdown = []
        node_counts = {}
        async for entry in qs.values("node").annotate(count=Count("id")).order_by("-count"):
            node_counts[entry["node"]] = entry["count"]

        for node, count in node_counts.items():
            node_qs = qs.filter(node=node)
            # Top error_type
            top_type = None
            async for t in node_qs.values("error_type").annotate(
                c=Count("id")
            ).order_by("-c")[:1]:
                top_type = t["error_type"]
            # Últimos 5 trace_ids
            trace_ids = []
            async for err in node_qs.order_by("-created_at").values_list(
                "trace_id", flat=True
            )[:5]:
                if err:
                    trace_ids.append(err)
            breakdown.append({
                "node": node,
                "count": count,
                "top_error_type": top_type,
                "trace_ids": trace_ids,
            })
        return breakdown

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
```

**CRÍTICO:**
- Usar `aaggregate()` (async aggregate) — disponível Django 5.1+
- Usar `acount()` (async count) — disponível Django 4.1+
- `async for` com `values().annotate()` — pattern async do Django ORM
- `get_satisfaction_rate` ignora rating="comment" (não é positivo nem negativo)
- `get_error_rate` usa Message(role="user") como denominador (total de requests)
- Retornar `None` quando não há dados (não 0.0 — são semanticamente diferentes)

### AlertingService — Implementação exata

```python
# workflows/services/alerting.py
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
        cost_alert = await AlertingService.check_cost_threshold()
        if cost_alert:
            alerts.append(cost_alert)
        error_alert = await AlertingService.check_error_rate_threshold()
        if error_alert:
            alerts.append(error_alert)
        return alerts
```

**Notas:**
- `_get_threshold()` usa ConfigService com fallback — NUNCA falha
- `logger.critical()` para alertas — padrão definido nos ACs e na arquitetura
- `run_all_checks()` retorna lista (pode ter 0, 1 ou 2 alertas)
- Breakdown inclui nó com mais falhas, tipo de erro, trace_ids (exatamente como pedido no AC3)

### Management Command — Implementação exata

```python
# workflows/management/commands/check_alerts.py
"""Management command para checagem periódica de thresholds (Cloud Scheduler)."""

import sys

import structlog
from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand

from workflows.services.alerting import AlertingService
from workflows.services.metrics import MetricsService

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = "Check quality metrics against configured thresholds and emit alerts"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show metrics summary without triggering alerts",
        )

    def handle(self, *args, **options):
        if options["dry_run"]:
            summary = async_to_sync(MetricsService.get_metrics_summary)()
            self.stdout.write(self.style.SUCCESS("=== Metrics Summary ==="))
            for key, value in summary.items():
                self.stdout.write(f"  {key}: {value}")
            return

        alerts = async_to_sync(AlertingService.run_all_checks)()

        if alerts:
            for alert in alerts:
                self.stdout.write(self.style.ERROR(f"ALERT: {alert['type']}"))
                for key, value in alert.items():
                    if key != "type":
                        self.stdout.write(f"  {key}: {value}")
            logger.info("check_alerts_completed", alerts_triggered=len(alerts))
            sys.exit(1)
        else:
            self.stdout.write(self.style.SUCCESS("All metrics within thresholds."))
            logger.info("check_alerts_completed", alerts_triggered=0)
```

**Notas:**
- `async_to_sync` do asgiref (já instalado como dep do Django) para chamar funções async
- `--dry-run` mostra métricas sem disparar alertas (útil para debugging)
- Exit code 1 se alertas disparados — Cloud Scheduler pode reagir ao exit code
- NÃO usar `import asyncio` + `asyncio.run()` — `async_to_sync` é o padrão Django

### Data Migration — Config entries

```python
# workflows/migrations/0019_add_alert_configs.py
from django.db import migrations


def create_alert_configs(apps, schema_editor):
    Config = apps.get_model("workflows", "Config")
    configs = [
        {"key": "alert:cost_daily_threshold", "value": 50.0, "updated_by": "migration"},
        {"key": "alert:error_rate_threshold", "value": 5.0, "updated_by": "migration"},
    ]
    for cfg in configs:
        Config.objects.get_or_create(key=cfg["key"], defaults=cfg)


def remove_alert_configs(apps, schema_editor):
    Config = apps.get_model("workflows", "Config")
    Config.objects.filter(key__startswith="alert:").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("workflows", "0018_add_errorlog"),
    ]

    operations = [
        migrations.RunPython(create_alert_configs, remove_alert_configs),
    ]
```

### Django Admin — Métricas agregadas (AC1)

O Django Admin JÁ permite consultar métricas via:
- **CostLogAdmin**: `date_hierarchy` para filtrar por dia/semana/mês, ver custo por período
- **FeedbackAdmin**: `date_hierarchy` + filtro por rating para ver taxa de satisfação
- **ToolExecutionAdmin**: filtro por tool_name + success para ver taxa de erro de tools

Para complementar (não obrigatório, mas recomendado):
- Adicionar método `changelist_view` override no CostLogAdmin para exibir totais no topo da lista
- OU usar a flag `--dry-run` do management command como dashboard CLI

**Approach mínimo (opcional — substituído por `check_alerts --dry-run`):**
```python
# No CostLogAdmin, adicionar:
def changelist_view(self, request, extra_context=None):
    # Inject aggregated metrics into the changelist template
    from django.db.models import Sum
    qs = self.get_queryset(request)
    extra_context = extra_context or {}
    result = qs.aggregate(total_cost=Sum("cost_usd"))
    extra_context["total_cost"] = result["total_cost"] or 0
    return super().changelist_view(request, extra_context=extra_context)
```

### Sobre Django async ORM aggregations

Django 5.1+ suporta `aaggregate()` (async aggregate). Documentação: [Django Aggregation](https://docs.djangoproject.com/en/6.0/topics/db/aggregation/). Se `aaggregate()` não estiver disponível na versão instalada, usar `sync_to_async(qs.aggregate)(...)` como fallback.

Verificar versão: o projeto usa Django 5.1+ (confirmado em ADR-002 e pyproject.toml).

### Cloud Scheduler para checagem periódica

O management command `check_alerts` é executado via Cloud Scheduler no Cloud Run:

```bash
# Local (manual)
uv run python manage.py check_alerts
uv run python manage.py check_alerts --dry-run

# Cloud Scheduler → Cloud Run Job (produção)
# Configurar job no GCP que executa:
# python manage.py check_alerts
# Cron: */15 * * * * (a cada 15 minutos)
```

**NÃO** é necessário Celery, django-celery-beat, ou qualquer dependência extra. O management command + Cloud Scheduler é suficiente para M1.

### Retro Watch Items — Exigidos em code review

1. **Over-mocking** — Pelo menos 1 teste de integração real por service. MetricsService DEVE ser testado com `@pytest.mark.django_db` e dados reais no banco (NÃO mock). AlertingService pode usar mock para ConfigService, mas MetricsService interno deve ser real.
2. **Silent error handlers** — Zero `except Exception` sem log. Todo novo `except` DEVE ter `logger.warning()` ou `logger.exception()`. ErrorLog creation em views.py DEVE logar falha.
3. **ErrorLog best-effort** — ErrorLog.acreate() NUNCA deve bloquear o fallback ao usuário. Se a criação falhar (DatabaseError), apenas logar e continuar.
4. **aaggregate() vs aggregate()** — Verificar se Django 5.1+ suporta `aaggregate()`. Se não, usar `sync_to_async`.

### Decisões de design relevantes

- **ADR-012:** NUNCA chamar `.bind_tools()` no retorno de `get_model()` — N/A para esta story (sem LLM)
- **ADR-013:** Modelo é Haiku 4.5 — N/A diretamente, mas pricing referência para custos
- **M1 scope:** Django Admin + CRITICAL logs para alertas. Sem Slack, sem email, sem dashboard custom.
- **Fase 2/3** (futuro): Slack webhooks, dashboards visuais, GCP Cloud Monitoring
- **structlog obrigatório** — NUNCA `print()`, sempre `structlog.get_logger(__name__)`
- **Naming convention:** snake_case para eventos: `alert_cost_threshold_exceeded`, `alert_error_rate_exceeded`
- **Config pattern:** `alert:cost_daily_threshold`, `alert:error_rate_threshold` — mesmo pattern de namespace usado em rate_limit:free, message:welcome, etc.

### Project Structure Notes

- Novo arquivo: `workflows/services/metrics.py` (MetricsService)
- Novo arquivo: `workflows/services/alerting.py` (AlertingService)
- Novo arquivo: `workflows/management/__init__.py`
- Novo arquivo: `workflows/management/commands/__init__.py`
- Novo arquivo: `workflows/management/commands/check_alerts.py`
- Modificações: `workflows/models.py` (ErrorLog), `workflows/admin.py` (ErrorLogAdmin + CostLogAdmin changelist), `workflows/views.py` (ErrorLog.acreate nos catch blocks)
- Migrations: `workflows/migrations/0018_add_errorlog.py`, `workflows/migrations/0019_add_alert_configs.py`
- Testes novos: `tests/test_services/test_metrics.py`, `tests/test_services/test_alerting.py`, `tests/test_models/test_error_log.py`, `tests/test_management/test_check_alerts.py`, `tests/test_management/__init__.py`
- Testes modificados: `tests/test_views/` (ErrorLog creation em error handlers)

### Previous Story Intelligence (7.1 + 7.2)

**Story 7.1 learnings:**
- Migration numbering conflicts: verificar última migration antes de criar (atualmente 0014)
- `response_metadata` e `usage_metadata` podem ser None — usar `or {}` pattern
- `asyncio.TimeoutError` → `TimeoutError` (UP041 lint fix — Ruff)
- Review encontrou 9 issues (2 HIGH, 4 MEDIUM, 3 LOW) — todos corrigidos
- `model_name` deve ser setado ANTES de `get_cost_summary()` (bug H1 da review)

**Story 7.2 learnings:**
- `trace_id` agora é capturado corretamente de `structlog.contextvars.get_contextvars()` (antes era `""`)
- Langfuse handler é condicional via `LANGFUSE_ENABLED` setting
- `propagate_attributes()` é context manager do SDK v4 do Langfuse
- Pre-existing test failures existem (orchestrate_llm model mismatch, bulas_med timeout) — não introduzidos nesta story

**Story 7.1 code review findings relevantes:**
- `if cost_usd and cost_usd > 0` → mudado para `if cost_usd is not None` (M1) — aplicar mesmo pattern para métricas
- `int(state["user_id"])` pode causar ValueError → mover dentro de try (M2) — ErrorLog deve tratar user_id inválido
- readonly_fields obrigatório para admin de models de analytics (L1)

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 7, Story 7.3]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-011: Admin Panel 3 fases (Django Admin Fase 1)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Observability cross-cutting concern]
- [Source: _bmad-output/planning-artifacts/architecture.md — NFR9: Alertas de gasto, M1.5]
- [Source: _bmad-output/planning-artifacts/architecture.md — structlog patterns, log levels]
- [Source: _bmad-output/planning-artifacts/architecture.md — Future enhancements: alertas customizados]
- [Source: _bmad-output/planning-artifacts/adr-013-haiku-tool-calling-optimization.md — Haiku 4.5 pricing reference]
- [Source: _bmad-output/implementation-artifacts/7-1-cost-tracking-callback-costlog.md — CostLog model, ToolExecution, persist patterns]
- [Source: _bmad-output/implementation-artifacts/7-2-traces-end-to-end-langfuse-structlog.md — Langfuse integration, trace_id fix]
- [Source: _bmad-output/implementation-artifacts/epic-3-5-retro-2026-03-12.md — Over-mocking, error handler concerns]
- [Source: workflows/models.py — Current models: CostLog, ToolExecution, Feedback, Message]
- [Source: workflows/admin.py — Current admin registrations]
- [Source: workflows/services/config_service.py — ConfigService.get() pattern]
- [Source: workflows/views.py — _process_message error handlers (GraphNodeError, Exception)]
- [Source: workflows/whatsapp/nodes/persist.py — Best-effort persist pattern]
- [Source: workflows/whatsapp/graph.py — Graph nodes and edges]
- [Source: Django docs — Aggregation: https://docs.djangoproject.com/en/6.0/topics/db/aggregation/]
- [Source: Langfuse docs — Spend Alerts: https://langfuse.com/docs/administration/spend-alerts]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Migration numbering: 0018 (ErrorLog) e 0019 (alert configs) — story previa 0015/0016 mas 0015-0017 já existiam
- Teste `error_log.user == user` falhou por SynchronousOnlyOperation em async context — corrigido para `error_log.user_id == user.pk`
- Testes views ErrorLog precisaram `transaction=True` para visibilidade cross-connection

### Completion Notes List

- AC1 (Métricas via Django Admin): MetricsService com 7 métodos async de agregação + ErrorLogAdmin queryable + CostLogAdmin existente com date_hierarchy
- AC2 (Alerta de custo diário): AlertingService.check_cost_threshold() + CRITICAL log + management command check_alerts com exit code 1
- AC3 (Alerta de taxa de erro): AlertingService.check_error_rate_threshold() + breakdown por nó, top error_type, últimos 5 trace_ids
- Retro watch items: zero over-mocking (MetricsService 100% com BD real), zero silent error handlers, ErrorLog best-effort verificado, aaggregate() confirmado Django 5.1+
- 56 novos testes, 730/733 do suite total passam (3 pre-existing failures de stories 7.1/7.2)

### File List

**Novos arquivos:**
- workflows/services/metrics.py — MetricsService com agregações async
- workflows/services/alerting.py — AlertingService com checagem de thresholds
- workflows/management/__init__.py — package init
- workflows/management/commands/__init__.py — package init
- workflows/management/commands/check_alerts.py — management command
- workflows/migrations/0018_add_errorlog.py — migration ErrorLog model
- workflows/migrations/0019_add_alert_configs.py — data migration configs
- tests/test_models/test_error_log.py — 15 testes ErrorLog model + admin
- tests/test_views/test_error_log_integration.py — 5 testes ErrorLog em views.py
- tests/test_services/test_metrics.py — 20 testes MetricsService (BD real)
- tests/test_services/test_alerting.py — 11 testes AlertingService
- tests/test_management/__init__.py — package init
- tests/test_management/test_check_alerts.py — 5 testes management command

**Arquivos modificados:**
- workflows/models.py — adicionado ErrorLog model
- workflows/admin.py — adicionado ErrorLogAdmin
- workflows/views.py — adicionado ErrorLog.acreate() nos catch blocks de _process_message

## Change Log

- 2026-03-15: Story 7.3 implementada — ErrorLog model, MetricsService, AlertingService, management command check_alerts, data migration com thresholds configuráveis, 56 novos testes
- 2026-03-15: Code Review (AI) — 9 issues encontradas (1H, 4M, 4L), todas corrigidas:
  - H1: run_all_checks() com isolamento de falhas entre checks (try/except por check)
  - M1: get_error_breakdown otimizado de N+1 queries para single query + agregação Python
  - M2: _sanitize_error_msg() adicionado em views.py para strip URLs de error_message
  - M3: test_alerting mock side_effect trocado de lista para função por key
  - M4: Dev Notes corrigidos (migrations 0018/0019, changelist_view marcado opcional)
  - L1: logger não utilizado removido de metrics.py
  - L3: test renomeado para refletir comportamento real
  - L4: edge case test adicionado (errors sem user messages)
  - 57 testes Story 7.3 passando, 733/736 suite total (3 pre-existing failures)
