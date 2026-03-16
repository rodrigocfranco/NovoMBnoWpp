# Story 7.2: Traces End-to-End via Langfuse + structlog

Status: done

## Story

As a equipe Medway,
I want traces completos de cada interação para debugging e análise de qualidade,
so that identifico rapidamente a causa de problemas e monitoro qualidade.

## Acceptance Criteria

1. **AC1 — Langfuse Provider** `workflows/providers/langfuse.py` com integração Langfuse
   - Cria `CallbackHandler` do Langfuse para LangChain/LangGraph
   - Envio fire-and-forget (não bloqueia pipeline)
   - Trace end-to-end criado no Langfuse com spans para cada nó do grafo (FR32)
   - Trace inclui: input do usuário, output do LLM, tools chamadas, latência por nó
   - Provider inicializado via `get_client()` singleton com env vars

2. **AC2 — Trace ID propagado** O `trace_id` gerado pelo middleware `trace_id.py` aparece em todos os logs structlog E no trace Langfuse
   - Corrigir gap: `trace_id` do middleware não está sendo capturado no `initial_state` do graph (atualmente `""`)
   - `trace_id` do middleware deve ser passado ao `CallbackHandler` como `trace_id` do trace Langfuse
   - Usar `structlog.contextvars` para capturar o `trace_id` no ponto de construção do graph state

3. **AC3 — structlog JSON** Qualquer log emitido pela aplicação renderiza em JSON com campos: timestamp, level, event, trace_id, contexto relevante
   - Processor `sanitize_pii` redacta automaticamente phone, name, email, cpf, api_key (NFR19)
   - **Já implementado** — validar que funciona com o novo trace_id propagado

4. **AC4 — Langfuse metadata** Cada trace Langfuse inclui metadata de negócio:
   - `user_id` — para filtrar traces por usuário no painel Langfuse
   - `session_id` — phone_number como session (mesma conversa)
   - `tags` — ["whatsapp", message_type]
   - `metadata` — {subscription_tier, provider_used}

5. **AC5 — Custo automático** Langfuse calcula custo automaticamente para modelos Claude pré-configurados
   - NÃO duplicar cálculo de custo do `CostTrackingCallback` (Story 7.1)
   - Langfuse serve como validação cruzada / visualização do custo

6. **AC6 — Flush graceful** Flush/shutdown do Langfuse no shutdown da aplicação
   - Registrar `atexit` handler no `WorkflowsConfig.ready()` em `workflows/apps.py`
   - `get_client().shutdown()` garante envio dos traces pendentes

7. **AC7 — Env vars** Variáveis de ambiente configuradas:
   - `LANGFUSE_SECRET_KEY` — obrigatório
   - `LANGFUSE_PUBLIC_KEY` — obrigatório
   - `LANGFUSE_BASE_URL` — padrão `https://cloud.langfuse.com` (EU) ou `https://us.cloud.langfuse.com` (US)
   - Adicionar ao `.env.example`
   - Adicionar ao `config/settings/base.py`

8. **AC8 — Dependência** Adicionar `langfuse>=4.0` ao `pyproject.toml`

9. **AC9 — Testes** Testes unitários cobrindo:
   - `langfuse.py`: factory function, env var loading, callback handler creation
   - Propagação de trace_id do middleware ao graph state
   - Fire-and-forget: Langfuse handler não bloqueia pipeline (mock flush)
   - Graceful shutdown: atexit handler chamado

## Tasks / Subtasks

- [x] Task 1: Criar `workflows/providers/langfuse.py` (AC: #1, #4, #6)
  - [x] 1.1: Implementar `get_langfuse_handler(trace_id)` que retorna `CallbackHandler` configurado (metadata via `propagate_attributes` no call site)
  - [x] 1.2: Usar `langfuse.get_client()` singleton internamente (via shutdown_langfuse)
  - [x] 1.3: trace_id propagado via `propagate_attributes()` context manager no call site (SDK v4 pattern)
  - [x] 1.4: Passar metadata de negócio via `propagate_attributes()` do SDK v4 (call site em views.py)
  - [x] 1.5: Envio é fire-and-forget por default do SDK (background thread batching)

- [x] Task 2: Corrigir propagação de trace_id (AC: #2)
  - [x] 2.1: Em `views.py` `_process_message()`, capturar `trace_id` de `structlog.contextvars.get_contextvars()` antes de construir `initial_state`
  - [x] 2.2: Popular `"trace_id": trace_id` no `initial_state` dict (corrigido de `""` para valor real)
  - [x] 2.3: Validar que todos os nodes que logam `trace_id=state.get("trace_id")` agora recebem valor real (via testes)

- [x] Task 3: Integrar Langfuse no graph invoke (AC: #1, #4, #5)
  - [x] 3.1: Em `views.py` `_process_message()`, criar `langfuse_handler` via factory do Task 1
  - [x] 3.2: Adicionar ao `config={"callbacks": [langfuse_handler], "configurable": {"thread_id": phone}}`
  - [x] 3.3: O `CostTrackingCallback` existente continua no `orchestrate_llm` node (não duplicar)
  - [x] 3.4: Langfuse `CallbackHandler` fica no nível do graph.ainvoke (captura todos os nós)

- [x] Task 4: Registrar atexit handler (AC: #6)
  - [x] 4.1: Em `workflows/apps.py` `WorkflowsConfig.ready()`, `atexit.register(shutdown_langfuse)` via provider
  - [x] 4.2: Condicional via `is_langfuse_enabled()` — só registrar se LANGFUSE_ENABLED=True

- [x] Task 5: Configuração e dependências (AC: #7, #8)
  - [x] 5.1: Adicionar `langfuse>=4.0` em `pyproject.toml` dependencies (via `uv add`)
  - [x] 5.2: Adicionar vars ao `.env.example`: `LANGFUSE_ENABLED`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_BASE_URL`
  - [x] 5.3: Adicionar settings em `config/settings/base.py`: `LANGFUSE_ENABLED = env.bool("LANGFUSE_ENABLED", default=False)`
  - [x] 5.4: `uv add langfuse>=4.0` executado (lock + sync automático)

- [x] Task 6: Testes (AC: #9)
  - [x] 6.1: `tests/test_providers/test_langfuse.py` — 7 testes: factory, handler, enabled/disabled, shutdown
  - [x] 6.2: `tests/test_views/test_trace_id_propagation.py` — 2 testes: trace_id propagado, fallback UUID
  - [x] 6.3: `tests/test_apps/test_atexit_handler.py` — 2 testes: atexit registrado/não registrado
  - [x] 6.4: Mocks: `@patch("langfuse.get_client")`, `@patch("CallbackHandler")` — zero chamadas reais
  - [x] 6.5: Ruff lint+format passam (0 errors)

## Dev Notes

### Arquitetura — O que já existe (NÃO reinventar)

- **structlog JSON** — Já configurado em `workflows/apps.py:12-25` com processors: `merge_contextvars`, `add_log_level`, `add_logger_name`, `sanitize_pii`, `TimeStamper`, `JSONRenderer`
- **TraceIDMiddleware** — Já em `workflows/middleware/trace_id.py` — gera UUID, propaga via `structlog.contextvars.bind_contextvars(trace_id=trace_id)`, adiciona header `X-Trace-ID`
- **CostTrackingCallback** — Já em `workflows/services/cost_tracker.py` — `AsyncCallbackHandler` do LangChain que extrai `usage_metadata` e calcula custo. Usado no `orchestrate_llm` node, NÃO no nível do graph
- **PII sanitization** — Já em `workflows/utils/sanitization.py` — redacta phone, name, email, cpf, api_key em todos os logs
- **32 arquivos** já usam structlog com padrão `logger = structlog.get_logger(__name__)`

### Gap crítico a corrigir

**`trace_id` não conectado ao graph state.** Em `views.py:192`, o `initial_state` seta `"trace_id": ""`. O middleware gera o UUID e faz `bind_contextvars`, mas a view NÃO captura esse valor para o state. Resultado: todos os nodes logam `trace_id=""`.

**Correção:** Antes de construir `initial_state`, fazer:
```python
ctx = structlog.contextvars.get_contextvars()
trace_id = ctx.get("trace_id", str(uuid.uuid4()))
```

### Langfuse SDK v4 — Padrão de integração

```python
# workflows/providers/langfuse.py
from langfuse import get_client, Langfuse, propagate_attributes
from langfuse.langchain import CallbackHandler

def get_langfuse_handler(
    trace_id: str,
    user_id: str = "",
    session_id: str = "",
    tags: list[str] | None = None,
    metadata: dict | None = None,
) -> CallbackHandler:
    """Create Langfuse CallbackHandler for LangGraph tracing."""
    handler = CallbackHandler()
    # trace_id correlacionado com structlog
    # metadata, user_id, session_id via propagate_attributes() context manager
    return handler
```

**Uso em views.py:**
```python
from langfuse import propagate_attributes
from workflows.providers.langfuse import get_langfuse_handler

handler = get_langfuse_handler(trace_id=trace_id, ...)
with propagate_attributes(
    user_id=user_id,
    session_id=phone,
    tags=["whatsapp", message_type],
    metadata={"subscription_tier": tier, "provider_used": provider},
):
    result = await graph.ainvoke(
        initial_state,
        config={
            "callbacks": [handler],
            "configurable": {"thread_id": phone},
        },
    )
```

### Envio fire-and-forget

O SDK Langfuse v4 usa background thread para enviar spans em batches. Configurável via:
- `LANGFUSE_FLUSH_AT=15` — número de eventos antes do flush
- `LANGFUSE_FLUSH_INTERVAL=1` — segundos entre flushes

**NÃO** bloqueia o pipeline. Latência adicionada ao request: ~0ms.

### Flush/Shutdown

Para Django (longa vida), o batching cuida sozinho. Mas no Cloud Run (SIGTERM → 10s grace), registrar shutdown:
```python
import atexit
from langfuse import get_client
atexit.register(lambda: get_client().shutdown())
```

### LANGFUSE_ENABLED pattern

Para ambientes sem Langfuse (dev local, CI), usar feature flag:
```python
LANGFUSE_ENABLED = env.bool("LANGFUSE_ENABLED", default=False)
```
Se `False`, NÃO criar handler, NÃO registrar atexit. O `_process_message()` deve verificar antes de adicionar callback.

### ADR-012: NÃO usar bind_tools() em get_model()

O Langfuse `CallbackHandler` é passado no **graph.ainvoke** (nível do grafo), NÃO no `get_model()`. Isso é diferente do `CostTrackingCallback` que é passado no nível do node `orchestrate_llm`. O handler do Langfuse precisa estar no nível do grafo para capturar spans de TODOS os nós.

### Retro Watch Items (herdados de Sprint 6)

- **Error handler silencioso** — zero `except Exception` sem log. Todo novo `except` DEVE ter `logger.exception()` ou `logger.error()`.
- **Over-mocking** — Story 7.2 é essencialmente sobre observabilidade, então mocks são aceitáveis para testes unitários (Langfuse não roda local). Mas validar que a integração funciona com env vars reais seria ideal em teste e2e.
- **Exceção raw para LLM** — N/A para esta story (não adiciona tools).

### Project Structure Notes

- Novo arquivo: `workflows/providers/langfuse.py` — consistente com `workflows/providers/{llm,checkpointer,redis,whatsapp,pinecone,whisper}.py`
- Modificados: `workflows/views.py` (trace_id + handler), `workflows/apps.py` (atexit), `pyproject.toml`, `.env.example`, `config/settings/base.py`
- Testes: `tests/test_providers/test_langfuse.py`, `tests/test_views/test_trace_id_propagation.py`
- **Não criar** `workflows/services/langfuse_service.py` — o provider pattern é suficiente

### Dependências de versão

| Pacote | Versão | Notas |
|--------|--------|-------|
| `langfuse` | `>=4.0` | SDK v4 (mar 2026), OpenTelemetry-based, `propagate_attributes()` |
| `structlog` | `>=24.4` | Já instalado |

### Pricing — Custo Langfuse

Langfuse Cloud tem tier gratuito com 50k observations/mês. Para o volume do mb-wpp (MVP), suficiente. Tier pago a partir de $59/mês se ultrapassar.

### References

- [Source: _bmad-output/planning-artifacts/architecture.md — Linhas 723-725: Langfuse SDK spec]
- [Source: _bmad-output/planning-artifacts/architecture.md — Linhas 1367-1381: providers directory structure com langfuse.py]
- [Source: _bmad-output/planning-artifacts/architecture.md — Linhas 1700-1741: structlog patterns e log levels]
- [Source: _bmad-output/planning-artifacts/architecture.md — Linhas 1729-1741: trace_id propagation pattern]
- [Source: _bmad-output/planning-artifacts/epics.md — Story 7.2: Traces End-to-End via Langfuse + structlog]
- [Source: workflows/middleware/trace_id.py — TraceIDMiddleware existente]
- [Source: workflows/services/cost_tracker.py — CostTrackingCallback existente]
- [Source: workflows/views.py:192 — trace_id="" gap]
- [Source: workflows/apps.py:12-25 — structlog config existente]
- [Source: workflows/whatsapp/state.py:40 — trace_id field no WhatsAppState]
- [Source: Langfuse docs — langfuse.com/integrations/frameworks/langchain]
- [Source: Langfuse docs — langfuse.com/docs/observability/sdk/python/setup]
- [Source: Langfuse docs — langfuse.com/docs/observability/features/queuing-batching]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

- Ruff lint: 3 auto-fixed (unused imports, isort) — zero remaining
- Pre-existing test failures: 16 (orchestrate_llm model mismatch, bulas_med timeout) — not introduced by this story

### Completion Notes List

- **Task 1:** Created `workflows/providers/langfuse.py` with `get_langfuse_handler()`, `is_langfuse_enabled()`, `shutdown_langfuse()`. SDK v4 pattern: handler is no-arg constructor, metadata via `propagate_attributes()` context manager at call site.
- **Task 2:** Fixed critical gap — `trace_id` was `""` in `initial_state`. Now captured from `structlog.contextvars.get_contextvars()` with UUID fallback.
- **Task 3:** Integrated Langfuse handler in `graph.ainvoke()` at graph level. `propagate_attributes()` wraps invoke with `session_id=phone`, `tags=["whatsapp", message_type]`. Handler only added when `LANGFUSE_ENABLED=True`.
- **Task 4:** `atexit.register(shutdown_langfuse)` in `WorkflowsConfig.ready()`, conditional on `is_langfuse_enabled()`.
- **Task 5:** `langfuse>=4.0` added to pyproject.toml. Env vars in `.env.example`. `LANGFUSE_ENABLED` setting in `base.py`.
- **Task 6:** 14 unit tests — all passing. TDD approach: tests written before implementation for each task.

### File List

**New files:**
- `workflows/providers/langfuse.py` — Langfuse provider (handler factory, enabled check, shutdown)
- `tests/test_providers/test_langfuse.py` — 7 tests for provider
- `tests/test_views/__init__.py` — package init
- `tests/test_views/test_trace_id_propagation.py` — 2 tests for trace_id fix
- `tests/test_views/test_langfuse_integration.py` — 3 tests for graph integration
- `tests/test_apps/__init__.py` — package init
- `tests/test_apps/test_atexit_handler.py` — 2 tests for atexit handler

**Modified files:**
- `workflows/views.py` — trace_id from contextvars, Langfuse handler in graph.ainvoke, propagate_attributes
- `workflows/apps.py` — atexit.register(shutdown_langfuse) conditional
- `config/settings/base.py` — LANGFUSE_ENABLED setting
- `.env.example` — Langfuse env vars
- `pyproject.toml` — langfuse>=4.0 dependency
- `uv.lock` — updated lockfile

## Change Log

- 2026-03-15: Story 7.2 implemented — Langfuse tracing, trace_id fix, atexit handler, 14 tests
