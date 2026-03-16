# Story 7.1: CostTrackingCallback + CostLog

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a equipe Medway,
I want rastrear o custo de cada request com granularidade de tokens,
So that controlo o orçamento e identifico otimizações.

## Acceptance Criteria

1. **Given** o nó `orchestrate_llm` invoca o LLM
   **When** o `CostTrackingCallback` (AsyncCallbackHandler) processa a resposta
   **Then** registra tokens_input, tokens_output, tokens_cache_read, tokens_cache_creation
   **And** calcula `cost_usd` usando pricing por modelo (Haiku 4.5: input $1.00/MTok, cache_read $0.10/MTok, cache_creation $1.25/MTok, output $5.00/MTok — ver ADR-013)
   **And** registra qual provider foi usado (`primary` ou `fallback`)

2. **Given** o nó `persist` executa após o envio
   **When** salva os dados da interação
   **Then** cria registro `CostLog` via `CostLog.objects.acreate()` com: user FK, provider, model, tokens (input/output/cache_write/cache_read), cost_usd, created_at
   **And** cria registro `ToolExecution` para cada tool chamada: tool_name, latency_ms, success, created_at

3. **Given** o Django Admin
   **When** a equipe acessa `/admin/workflows/costlog/`
   **Then** `CostLogAdmin` mostra list_display com user, provider, model, cost_usd, created_at
   **And** list_filter por provider, model, created_at
   **And** date_hierarchy por created_at
   **And** precisão de custo ±5% sobre custo real da API (NFR8)

## Tasks / Subtasks

- [x] Task 1: Criar modelos Django CostLog e ToolExecution (AC: #2, #3)
  - [x] 1.1 Adicionar `CostLog` ao `workflows/models.py` com campos: user (FK), provider, model, tokens_input, tokens_output, tokens_cache_write, tokens_cache_read, cost_usd (Decimal 10,6), created_at — indexes em [user], [-created_at]
  - [x] 1.2 Adicionar `ToolExecution` ao `workflows/models.py` com campos: user (FK), tool_name, latency_ms (nullable), success, error (nullable), created_at — indexes em [tool_name], [-created_at]
  - [x] 1.3 Criar migration `workflows/migrations/0011_add_costlog_toolexecution.py` (renumerada por conflito com migration 0010 de Story 6.1)
  - [x] 1.4 Testes unitários para ambos os modelos (criação, __str__, indexes) — 11 testes em `tests/test_models/test_core_models.py`

- [x] Task 2: Atualizar pricing para suportar Haiku 4.5 + Sonnet 4 (AC: #1)
  - [x] 2.1 Substituir constantes fixas em `cost_tracker.py` por dict `MODEL_PRICING` com pricing por modelo
  - [x] 2.2 Adicionar `model_name` como parâmetro do `CostTrackingCallback.__init__()`
  - [x] 2.3 Ajustar `get_cost_summary()` para selecionar pricing baseado no modelo; fallback para Haiku 4.5 pricing se modelo desconhecido
  - [x] 2.4 Atualizar testes existentes em `tests/test_services/test_cost_tracker.py` para novo pricing e novos cenários (Haiku vs Sonnet) — 15 testes

- [x] Task 3: Adicionar campos de token breakdown ao WhatsAppState e orchestrate_llm (AC: #1, #2)
  - [x] 3.1 Adicionar ao `WhatsAppState`: `tokens_input: int`, `tokens_output: int`, `tokens_cache_read: int`, `tokens_cache_creation: int`, `model_used: str`
  - [x] 3.2 No `orchestrate_llm`, popular estes campos a partir de `cost_tracker.get_cost_summary()` e `model_name` no dict de retorno
  - [x] 3.3 Acumular tokens (assim como `cost_usd` já acumula) entre iterações do tool loop
  - [x] 3.4 Atualizar `tests/test_whatsapp/conftest.py` — adicionar novos campos ao `make_whatsapp_state`
  - [x] 3.5 Testes unitários para acumulação de tokens no orchestrate_llm — 3 testes em `TestTokenBreakdown`

- [x] Task 4: Criar tracking de ToolExecution via wrapper node (AC: #2)
  - [x] 4.1 Adicionar `tool_executions: list[dict]` ao `WhatsAppState`
  - [x] 4.2 Criar wrapper async `tracked_tools()` em `workflows/whatsapp/nodes/tracked_tools.py` que mede latência e extrai tool names
  - [x] 4.3 Atualizar `graph.py` para usar `tracked_tools` ao invés de `ToolNode(get_tools())` direto
  - [x] 4.4 Manter `handle_tool_errors=True` e `RetryPolicy(max_attempts=3)` do ToolNode existente
  - [x] 4.5 Testes unitários para tracked_tools (tool sucesso, tool erro, latency tracking) — 5 testes

- [x] Task 5: Atualizar persist node para criar CostLog + ToolExecution (AC: #2)
  - [x] 5.1 Importar `CostLog`, `ToolExecution` em `persist.py`
  - [x] 5.2 Criar `CostLog` a partir dos campos de state: user, provider_used, model_used, tokens_*, cost_usd
  - [x] 5.3 Criar `ToolExecution` para cada item em `state["tool_executions"]`
  - [x] 5.4 Manter padrão existente: `DatabaseError` silenciado (user já recebeu resposta)
  - [x] 5.5 Testes unitários para persist com CostLog e ToolExecution — 7 testes (`@pytest.mark.django_db`, BD real)

- [x] Task 6: Registrar Django Admin para CostLog e ToolExecution (AC: #3)
  - [x] 6.1 Adicionar `CostLogAdmin` em `admin.py`
  - [x] 6.2 Adicionar `ToolExecutionAdmin` em `admin.py`
  - [x] 6.3 Testes para admin registration (admin.site check) — 4 testes

- [x] Task 7: Testes end-to-end + lint (AC: #1, #2, #3)
  - [x] 7.1 Teste de integração: CostLog criado via persist com dados corretos (django_db real)
  - [x] 7.2 Teste de precisão de custo ±5% (NFR8) com valores conhecidos — `pytest.approx(abs=0.000001)`
  - [x] 7.3 Teste: mensagem sem tool calls → CostLog criado, zero ToolExecution
  - [x] 7.4 Teste: mensagem com tool calls → CostLog + ToolExecution(s) criados
  - [x] 7.5 630 testes passando, 0 regressões, lint clean em todos os arquivos modificados

## Dev Notes

### O que já existe (NÃO reimplementar)

| Componente | Status Atual | O que falta (esta story) |
|------------|-------------|--------------------------|
| `CostTrackingCallback` em `services/cost_tracker.py` | Implementado — captura tokens, calcula custo, loga via structlog | Atualizar pricing para Haiku 4.5 (ADR-013), tornar model-aware |
| `CostTrackingCallback` no `orchestrate_llm` | Implementado — injected via `config={"callbacks": [cost_tracker]}` | Propagar token breakdown para state |
| `WhatsAppState.cost_usd` | Implementado — acumula custo entre tool loops | Adicionar campos: tokens_input/output/cache_read/cache_creation, model_used |
| `WhatsAppState.provider_used` | Implementado — detecta vertex_ai vs anthropic_direct | Manter (já funciona) |
| `persist` node | Cria Message com cost_usd no assistente | **ADICIONAR** CostLog + ToolExecution records |
| `CostLog` model | **NÃO existe** | **CRIAR** |
| `ToolExecution` model | **NÃO existe** | **CRIAR** |
| Django Admin | User, Message, Config, ConfigHistory registrados | **ADICIONAR** CostLogAdmin, ToolExecutionAdmin |
| Pricing constants | Hardcoded Sonnet 4: input $3.00, output $15.00 | **ATUALIZAR** para dict model-aware (Haiku 4.5 + Sonnet 4) |

### Pricing — Atualização obrigatória (ADR-013)

ADR-013 mudou o modelo de Claude Sonnet 4 para **Claude Haiku 4.5** (71% mais barato). O `cost_tracker.py` atualmente usa pricing de Sonnet 4. Deve ser atualizado para dict model-aware:

```python
# workflows/services/cost_tracker.py
MODEL_PRICING: dict[str, dict[str, float]] = {
    "haiku": {  # Claude Haiku 4.5
        "input": 1.00,
        "cache_read": 0.10,
        "cache_creation": 1.25,
        "output": 5.00,
    },
    "sonnet": {  # Claude Sonnet 4 (fallback / legacy)
        "input": 3.00,
        "cache_read": 0.30,
        "cache_creation": 3.75,
        "output": 15.00,
    },
}
DEFAULT_PRICING_KEY = "haiku"

def _resolve_pricing(model_name: str) -> dict[str, float]:
    """Select pricing tier based on model name substring match."""
    model_lower = model_name.lower()
    if "haiku" in model_lower:
        return MODEL_PRICING["haiku"]
    if "sonnet" in model_lower:
        return MODEL_PRICING["sonnet"]
    return MODEL_PRICING[DEFAULT_PRICING_KEY]
```

**Fonte do pricing:** Anthropic pricing page (março 2026). Vertex AI usa mesmo pricing base.

### CostLog model — Schema exato

```python
class CostLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cost_logs")
    provider = models.CharField(max_length=20)  # "vertex_ai", "anthropic_direct", "unknown"
    model = models.CharField(max_length=100)  # e.g. "claude-haiku-4-5@20251001"
    tokens_input = models.IntegerField()
    tokens_output = models.IntegerField()
    tokens_cache_write = models.IntegerField(default=0)
    tokens_cache_read = models.IntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cost_logs"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self) -> str:
        return f"CostLog(user={self.user_id}, ${self.cost_usd})"
```

### ToolExecution model — Schema exato

```python
class ToolExecution(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tool_executions")
    tool_name = models.CharField(max_length=100)
    latency_ms = models.IntegerField(null=True)
    success = models.BooleanField()
    error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tool_executions"
        indexes = [
            models.Index(fields=["tool_name"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self) -> str:
        return f"ToolExecution({self.tool_name}, success={self.success})"
```

**NOTA:** Não incluir `input_params` e `output` JSONField (presente na arquitetura original). Volume de dados sem benefício imediato. Podem ser adicionados em story futura.

### ToolExecution tracking — Wrapper node approach

ToolNode do LangGraph não expõe timing de execução individual. Abordagem: criar wrapper `tracked_tools()` que mede o tempo do batch e extrai tool names dos ToolMessages.

```python
# workflows/whatsapp/nodes/tracked_tools.py
import time

import structlog
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolNode

from workflows.whatsapp.state import WhatsAppState
from workflows.whatsapp.tools import get_tools

logger = structlog.get_logger(__name__)

_tool_node = ToolNode(get_tools(), handle_tool_errors=True)


async def tracked_tools(state: WhatsAppState) -> dict:
    """Execute tools via ToolNode and track execution metadata."""
    start = time.monotonic()
    result = await _tool_node.ainvoke(state)
    elapsed_ms = int((time.monotonic() - start) * 1000)

    tool_messages = [m for m in result.get("messages", []) if isinstance(m, ToolMessage)]
    prev_executions = state.get("tool_executions") or []
    new_executions = []
    for msg in tool_messages:
        is_error = hasattr(msg, "status") and msg.status == "error"
        new_executions.append({
            "tool_name": msg.name or "unknown",
            "latency_ms": elapsed_ms // len(tool_messages) if tool_messages else elapsed_ms,
            "success": not is_error,
            "error": msg.content[:500] if is_error else None,
        })

    logger.info(
        "tools_executed",
        tool_count=len(new_executions),
        total_latency_ms=elapsed_ms,
        user_id=state.get("user_id"),
    )

    return {
        **result,
        "tool_executions": prev_executions + new_executions,
    }
```

**Sobre graph.py:**
- O nó `tools` atualmente usa `ToolNode(get_tools())` diretamente — substituir por `tracked_tools`
- Manter `retry_policy=RetryPolicy(max_attempts=3, backoff_factor=2.0)` no `builder.add_node`
- A edge condition `tools_condition` continua funcionando (detecta tool_calls no AIMessage)
- `handle_tool_errors=True` configurado no `_tool_node` dentro de `tracked_tools.py`
- Como `parallel_tool_calls=False` (ADR-013), cada tool-loop iteration tem 1 tool call — latency preciso

### Persist node — O que adicionar

Atualização mínima no `persist.py`. Adicionar APÓS a criação dos Messages:

```python
# Create CostLog record
cost_usd = state.get("cost_usd")
if cost_usd and cost_usd > 0:
    await CostLog.objects.acreate(
        user=user,
        provider=state.get("provider_used", "unknown"),
        model=state.get("model_used", "unknown"),
        tokens_input=state.get("tokens_input", 0),
        tokens_output=state.get("tokens_output", 0),
        tokens_cache_write=state.get("tokens_cache_creation", 0),
        tokens_cache_read=state.get("tokens_cache_read", 0),
        cost_usd=Decimal(str(cost_usd)),
    )

# Create ToolExecution records
tool_executions = state.get("tool_executions") or []
for exec_data in tool_executions:
    await ToolExecution.objects.acreate(
        user=user,
        tool_name=exec_data["tool_name"],
        latency_ms=exec_data.get("latency_ms"),
        success=exec_data.get("success", True),
        error=exec_data.get("error"),
    )
```

**Nota:** Manter o pattern de `DatabaseError` silenciado existente. CostLog e ToolExecution são best-effort.

### orchestrate_llm — Campos novos no retorno

Atualmente retorna: `{"messages": [...], "cost_usd": accumulated_cost, "provider_used": provider_used}`

Adicionar ao retorno:

```python
return {
    "messages": return_messages,
    "cost_usd": accumulated_cost,
    "provider_used": provider_used,
    # Story 7.1: token breakdown para CostLog
    "tokens_input": state.get("tokens_input", 0) + cost_summary["input_tokens"],
    "tokens_output": state.get("tokens_output", 0) + cost_summary["output_tokens"],
    "tokens_cache_read": state.get("tokens_cache_read", 0) + cost_summary["cache_read_tokens"],
    "tokens_cache_creation": state.get("tokens_cache_creation", 0) + cost_summary["cache_creation_tokens"],
    "model_used": model_name,
}
```

### WhatsAppState — Campos novos

```python
# Cost tracking fields (Story 7.1)
tokens_input: int
tokens_output: int
tokens_cache_read: int
tokens_cache_creation: int
model_used: str
tool_executions: list[dict]
```

### views.py — Inicialização de state

Adicionar valores default para os novos campos no `initial_state`:

```python
"tokens_input": 0,
"tokens_output": 0,
"tokens_cache_read": 0,
"tokens_cache_creation": 0,
"model_used": "",
"tool_executions": [],
```

### Django Admin — Configuração exata

```python
@admin.register(CostLog)
class CostLogAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "model", "cost_usd", "tokens_input", "tokens_output", "created_at")
    list_filter = ("provider", "model", "created_at")
    date_hierarchy = "created_at"
    raw_id_fields = ("user",)


@admin.register(ToolExecution)
class ToolExecutionAdmin(admin.ModelAdmin):
    list_display = ("user", "tool_name", "latency_ms", "success", "created_at")
    list_filter = ("tool_name", "success")
    raw_id_fields = ("user",)
```

### Retro Watch Items — Exigidos em code review

1. **Over-mocking** — Pelo menos 1 teste de integração real por story. Não mock CostLog.objects.acreate em testes unitários do persist — usar `@pytest.mark.django_db` com BD real.
2. **Pricing accuracy** — Teste NFR8: calcular custo com valores conhecidos e verificar ±5%.
3. **Silent error handlers** — Zero `except Exception` sem log. Flagar no code review.
4. **State fields não inicializados** — Garantir que TODOS os novos campos têm default em `views.py` initial_state.

### Decisões de design relevantes

- **ADR-012:** NUNCA chamar `.bind_tools()` no retorno de `get_model()` — sempre `get_model(tools=get_tools())`
- **ADR-013:** Modelo é Haiku 4.5 (`claude-haiku-4-5@20251001` Vertex / `claude-haiku-4-5-20251001` Direct), `parallel_tool_calls=False`, `max_tokens=1024` (resp final) / `128` (tool re-entry)
- **persist é best-effort** — DatabaseError silenciado, programming errors propagam
- **structlog obrigatório** — NUNCA `print()`, sempre `structlog.get_logger(__name__)`
- **ToolNode handle_tool_errors=True** — Atributo privado `_handle_tool_errors` (Story 5.2)

### Project Structure Notes

- Todos os arquivos seguem a estrutura `workflows/` existente
- Novo arquivo: `workflows/whatsapp/nodes/tracked_tools.py` (wrapper do ToolNode)
- Modificações: `workflows/models.py`, `workflows/admin.py`, `workflows/whatsapp/state.py`, `workflows/whatsapp/nodes/orchestrate_llm.py`, `workflows/whatsapp/nodes/persist.py`, `workflows/whatsapp/graph.py`, `workflows/services/cost_tracker.py`, `workflows/views.py`
- Migration: `workflows/migrations/0010_add_costlog_toolexecution.py`
- Testes: `tests/test_services/test_cost_tracker.py` (atualizar), `tests/test_whatsapp/test_nodes/test_persist.py` (atualizar), `tests/test_whatsapp/test_nodes/test_tracked_tools.py` (novo), `tests/test_whatsapp/test_nodes/test_orchestrate_llm.py` (atualizar)

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 7, Story 7.1]
- [Source: _bmad-output/planning-artifacts/architecture.md — CostTrackingCallback pattern]
- [Source: _bmad-output/planning-artifacts/architecture.md — CostLog + ToolExecution models schema]
- [Source: _bmad-output/planning-artifacts/architecture.md — structlog configuration]
- [Source: _bmad-output/planning-artifacts/architecture.md — Django Admin registrations]
- [Source: _bmad-output/planning-artifacts/adr-012-get-model-tools-bind-pattern.md — get_model(tools=) rule]
- [Source: _bmad-output/planning-artifacts/adr-013-haiku-tool-calling-optimization.md — Haiku 4.5 model switch, pricing]
- [Source: _bmad-output/implementation-artifacts/epic-3-5-retro-2026-03-12.md — Over-mocking, test quality concerns]
- [Source: _bmad-output/implementation-artifacts/5-1-retry-automatico-circuit-breaker.md — RetryPolicy patterns, provider detection]
- [Source: workflows/services/cost_tracker.py — Current CostTrackingCallback implementation]
- [Source: workflows/whatsapp/nodes/orchestrate_llm.py — Current LLM invocation with callback]
- [Source: workflows/whatsapp/nodes/persist.py — Current persist implementation (Messages only)]
- [Source: workflows/models.py — Current models (User, Message, Config, Drug, ConfigHistory)]
- [Source: workflows/admin.py — Current admin registrations]
- [Source: workflows/whatsapp/state.py — Current WhatsAppState fields]
- [Source: workflows/whatsapp/graph.py — Current graph definition with ToolNode]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

N/A

### Completion Notes List

- Migration renumerada para 0011 (conflito com 0010 de Story 6.1 Feedback model)
- Migration merge 0012 criada automaticamente (0011_add_costlog_toolexecution + 0011_add_feedback_configs)
- test_models.py movido para test_models/test_core_models.py (conflito de namespace com diretório test_models/ de Story 6.1)
- Corrigido bug pre-existente: `propagate_attributes(trace_id=...)` em views.py — parâmetro `trace_id` não existe na API do langfuse (Story 7.2 bug)
- Corrigidos testes pre-existentes: test_llm.py (ADR-013 Haiku model), test_error_fallback.py (propagate_attributes TypeError), test_resilience.py (missing cache keys)
- `response_metadata` e `usage_metadata` agora usam pattern `or {}` para tratar None (getattr retorna None quando atributo existe mas é None)
- `asyncio.TimeoutError` → `TimeoutError` (UP041 lint fix)

### File List

**Novos:**
- `workflows/whatsapp/nodes/tracked_tools.py` — wrapper do ToolNode com tracking de latência
- `workflows/migrations/0011_add_costlog_toolexecution.py` — migration CostLog + ToolExecution
- `workflows/migrations/0012_merge_20260315_1227.py` — merge migration
- `tests/test_whatsapp/test_nodes/test_tracked_tools.py` — 5 testes tracked_tools

**Modificados (Story 7.1):**
- `workflows/models.py` — CostLog + ToolExecution models
- `workflows/services/cost_tracker.py` — MODEL_PRICING dict, _resolve_pricing(), model_name param
- `workflows/whatsapp/state.py` — 6 novos campos (tokens_*, model_used, tool_executions)
- `workflows/whatsapp/nodes/orchestrate_llm.py` — token breakdown, None handling, TimeoutError fix
- `workflows/whatsapp/nodes/persist.py` — CostLog + ToolExecution creation
- `workflows/whatsapp/graph.py` — tracked_tools substituindo ToolNode direto
- `workflows/admin.py` — CostLogAdmin + ToolExecutionAdmin
- `workflows/views.py` — 6 novos campos em initial_state, propagate_attributes fix
- `tests/test_whatsapp/conftest.py` — novos campos em make_whatsapp_state
- `tests/test_models/test_core_models.py` — testes CostLog + ToolExecution + admin
- `tests/test_services/test_cost_tracker.py` — reescrito para model-aware pricing
- `tests/test_whatsapp/test_nodes/test_persist.py` — reescrito com CostLog + ToolExecution
- `tests/test_whatsapp/test_nodes/test_orchestrate_llm.py` — TestTokenBreakdown + CostTrackingCallback fix

**Modificados (fixes pre-existentes):**
- `tests/test_providers/test_llm.py` — ADR-013 model/max_tokens assertions
- `tests/test_whatsapp/test_resilience.py` — cache keys em mocked cost_summary
- `tests/test_whatsapp/test_error_fallback.py` — (não modificado, fix foi em views.py)
- `tests/test_views/test_langfuse_integration.py` — removido trace_id assertion
- `tests/test_whatsapp/test_nodes/test_orchestrate_llm_tools.py` — max_tokens + state fields

## Code Review Record

### Review Date
2026-03-15

### Reviewer
Claude Opus 4.6 (adversarial code review workflow)

### Findings (9 total: 2 HIGH, 4 MEDIUM, 3 LOW)

| ID | Severity | Issue | Fix Applied |
|----|----------|-------|-------------|
| H1 | HIGH | `model_name` set AFTER `get_cost_summary()` — pricing always defaulted to Haiku | Moved `cost_tracker.model_name = model_name` BEFORE `get_cost_summary()` in orchestrate_llm.py |
| H2 | HIGH | All tracked_tools tests used mocks, no real ToolNode execution tested | Added 2 real ToolNode tests via mini StateGraph (success + error scenarios) |
| M1 | MEDIUM | `if cost_usd and cost_usd > 0` skipped CostLog for cost=0.0 | Changed to `if cost_usd is not None` for complete tracking |
| M2 | MEDIUM | `int(state["user_id"])` outside try block — ValueError crashes pipeline | Moved inside try, added ValueError to exception tuple |
| M3 | MEDIUM | Model field `tokens_cache_write` ≠ API terminology `cache_creation` | Renamed field + migration 0014 + all references updated |
| M4 | MEDIUM | `elapsed_ms // len(tool_messages)` is no-op with `parallel_tool_calls=False` | Simplified to `elapsed_ms` directly with ADR-013 comment |
| L1 | LOW | CostLogAdmin/ToolExecutionAdmin missing readonly_fields | Added readonly_fields to both admin classes |
| L2 | LOW | Architecture doc pricing tables outdated (Sonnet 4 only) | Noted — planning artifact, not code (to be updated separately) |
| L3 | LOW | Duplicate comment in graph.py (`collect_sources: NO retry`) | Removed duplicate line |

### Post-Review Test Results
- **633 tests passing** (vs 630 claimed in story, +3 from review fixes)
- **0 regressions** from review fixes
- **ruff lint + format clean** on all modified files
- 1 pre-existing failure (test_global_timeout in test_bulas_med.py — unrelated cache issue)

### Files Modified by Review
- `workflows/whatsapp/nodes/orchestrate_llm.py` — H1
- `workflows/whatsapp/nodes/persist.py` — M1, M2
- `workflows/whatsapp/nodes/tracked_tools.py` — M4
- `workflows/whatsapp/graph.py` — L3
- `workflows/models.py` — M3
- `workflows/admin.py` — L1, M3
- `workflows/migrations/0014_rename_tokens_cache_write_to_creation.py` — M3 (new)
- `tests/test_whatsapp/test_nodes/test_tracked_tools.py` — H2
- `tests/test_whatsapp/test_nodes/test_persist.py` — M1, M3
- `tests/test_models/test_core_models.py` — M3
