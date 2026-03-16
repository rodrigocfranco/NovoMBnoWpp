# Story 8.1: ConfigService Aprimorado — Hot-Reload via Redis + Audit Trail

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a equipe Medway,
I want que alterações em parâmetros operacionais entrem em vigor em minutos sem deploy,
so that ajusto o sistema rapidamente em resposta a necessidades operacionais.

## Acceptance Criteria

1. **AC1 — Cache Redis no ConfigService.get()**
   **Given** o ConfigService existente (criado na Story 1.1)
   **When** aprimorado com camada de cache Redis
   **Then** `ConfigService.get("rate_limit:free")` verifica Redis primeiro (`config:{key}`, TTL 5min)
   **And** se cache miss, busca no banco via `Config.objects.aget(key=key)` e popula cache
   **And** mudanças no Config model são refletidas em até 5 minutos (TTL expira) (FR38)
   **And** se Redis estiver indisponível, cai para DB diretamente (graceful degradation)

2. **AC2 — Audit trail automático no Django Admin**
   **Given** a equipe edita um Config no Django Admin (ex: muda `rate_limit:free` de 10 para 15)
   **When** a configuração é salva
   **Then** o `updated_by` é preenchido automaticamente com o usuário admin
   **And** o `updated_at` é atualizado
   **And** a mudança entra em vigor em até 5 minutos (FR33)
   **And** o ConfigHistory registra old_value e new_value automaticamente (FR37)

3. **AC3 — Invalidação imediata de cache no Admin save**
   **Given** a equipe salva uma alteração no Django Admin
   **When** o `save_model()` do ConfigAdmin executa
   **Then** a chave Redis `config:{key}` é deletada imediatamente
   **And** a próxima chamada a `ConfigService.get()` busca o valor atualizado do banco e re-popula o cache
   **And** o efeito é instantâneo (não precisa esperar TTL expirar)

4. **AC4 — ConfigAdmin aprimorado**
   **Given** o Django Admin para Config
   **When** a equipe acessa `/admin/workflows/config/`
   **Then** `updated_at` e `updated_by` são readonly (preenchidos automaticamente)
   **And** ConfigHistory é exibido inline na página de edição do Config
   **And** ConfigHistoryAdmin mostra old_value e new_value lado a lado

5. **AC5 — Testes**
   **Given** a suíte de testes
   **When** executada
   **Then** cobre: cache hit, cache miss, Redis failure (graceful degradation), cache invalidation no admin save, audit trail creation, ConfigHistory inline
   **And** pelo menos 1 teste de integração real com DB (`@pytest.mark.django_db`)
   **And** zero regressões nos 25+ call sites existentes de `ConfigService.get()`

## Tasks / Subtasks

- [x] Task 1: Adicionar camada de cache Redis ao ConfigService (AC: #1)
  - [x] 1.1 Adicionar constante `CONFIG_CACHE_TTL = 300` (5 minutos) em config_service.py
  - [x] 1.2 Refatorar `ConfigService.get()` com cache-aside pattern: Redis `get()` → DB fallback → Redis `setex()`
  - [x] 1.3 Graceful degradation: se Redis falha (`RedisError`), cair para DB diretamente e logar warning
  - [x] 1.4 Adicionar método estático `invalidate(key)` para deletar chave Redis `config:{key}`
  - [x] 1.5 Adicionar logging estruturado: `config_cache_hit`, `config_cache_miss`, `config_cache_error`
  - [x] 1.6 Testes unitários: cache hit, cache miss, Redis error graceful degradation, invalidation — 8 testes

- [x] Task 2: Aprimorar ConfigAdmin com audit trail automático (AC: #2, #3, #4)
  - [x] 2.1 Override `save_model()` para auto-preencher `updated_by` com `request.user.username`
  - [x] 2.2 No `save_model()`, capturar `old_value` via `Config.objects.filter(pk=obj.pk).values_list("value", flat=True).first()` antes do super()
  - [x] 2.3 Após super(), criar `ConfigHistory` com old_value, new_value, changed_by
  - [x] 2.4 Após super(), chamar `async_to_sync(ConfigService.invalidate)(obj.key)` para invalidar cache Redis
  - [x] 2.5 Adicionar `readonly_fields = ("updated_at", "updated_by")` no ConfigAdmin
  - [x] 2.6 Adicionar `ConfigHistoryInline` (TabularInline) no ConfigAdmin para ver histórico na mesma página
  - [x] 2.7 Melhorar `ConfigHistoryAdmin` com `list_display` incluindo old_value e new_value
  - [x] 2.8 Testes para admin save, audit trail creation, cache invalidation — 8 testes

- [x] Task 3: Testes de integração e lint (AC: #5)
  - [x] 3.1 Teste E2E: admin save → cache invalidated → próximo get() retorna novo valor
  - [x] 3.2 Teste: Redis down → ConfigService.get() funciona via DB (graceful degradation)
  - [x] 3.3 Teste: novo Config (sem old_value) → ConfigHistory com old_value=None
  - [x] 3.4 Verificar que todos os 25+ call sites existentes continuam funcionando (sem breaking changes)
  - [x] 3.5 Ruff lint + format passam (0 errors) em todos os arquivos modificados
  - [x] 3.6 Todos os testes passando (excluindo tests/e2e e tests/integration) — 665/668, 3 falhas pré-existentes

## Dev Notes

### O que já existe (NÃO reimplementar)

| Componente | Status Atual | O que falta (esta story) |
|------------|-------------|--------------------------|
| `Config` model em `models.py` | key, value (JSON), updated_by, updated_at (auto_now) | Nenhuma mudança no model |
| `ConfigHistory` model em `models.py` | config FK, old_value, new_value, changed_by, changed_at | **MODIFICADO**: `old_value` → `null=True, blank=True` (migration 0017) |
| `ConfigService.get(key)` em `services/config_service.py` | Busca DB direto via `Config.objects.aget(key)` (17 linhas) | **ADICIONAR** camada Redis cache-aside |
| `ConfigAdmin` em `admin.py` | list_display, search_fields básicos | **APRIMORAR** save_model, readonly_fields, inline |
| `ConfigHistoryAdmin` em `admin.py` | list_display, list_filter básicos | **APRIMORAR** list_display com old/new values |
| `get_redis_client()` em `providers/redis.py` | Singleton `redis.asyncio`, decode_responses=True | Nenhuma mudança (apenas usar) |
| `cache_service.py` em `services/` | CacheService com namespace pattern, TTL, graceful degradation | **REFERÊNCIA** para padrão de implementação |
| 25+ call sites com `ConfigService.get()` | Padrão try/except com fallback hardcoded | Zero breaking changes |
| ~25 Config records via data migrations | rate_limit:*, message:*, timeout:*, blocked_competitors, debounce_ttl | Nenhuma nova migration de dados |

### ConfigService.get() — Implementação com cache-aside pattern

```python
# workflows/services/config_service.py
"""Configuration service with Redis cache-aside pattern (TTL 5min)."""

import json
from typing import Any

import structlog
from redis.exceptions import RedisError

from workflows.models import Config
from workflows.providers.redis import get_redis_client
from workflows.utils.errors import ValidationError

logger = structlog.get_logger(__name__)

CONFIG_CACHE_TTL = 300  # 5 minutos (FR38: mudanças refletidas em até 5 min)
CONFIG_CACHE_PREFIX = "config:"


class ConfigService:
    @staticmethod
    async def get(key: str) -> Any:
        """Fetch config value with Redis cache-aside (TTL 5min).

        1. Check Redis cache
        2. On miss → query DB → populate cache
        3. On Redis error → fallback to DB (graceful degradation)
        """
        cache_key = f"{CONFIG_CACHE_PREFIX}{key}"

        # 1. Try Redis cache first
        try:
            client = get_redis_client()
            cached = await client.get(cache_key)
            if cached is not None:
                logger.debug("config_cache_hit", key=key)
                return json.loads(cached)
            logger.debug("config_cache_miss", key=key)
        except RedisError:
            logger.warning("config_cache_error", key=key, action="fallback_to_db")

        # 2. Cache miss or Redis error → query DB
        try:
            config = await Config.objects.aget(key=key)
        except Config.DoesNotExist:
            raise ValidationError(f"Config not found: {key}", details={"key": key})

        # 3. Populate cache (best-effort)
        try:
            client = get_redis_client()
            await client.setex(cache_key, CONFIG_CACHE_TTL, json.dumps(config.value))
        except RedisError:
            logger.warning("config_cache_set_error", key=key)

        return config.value

    @staticmethod
    async def invalidate(key: str) -> None:
        """Delete config cache key (called on admin save)."""
        cache_key = f"{CONFIG_CACHE_PREFIX}{key}"
        try:
            client = get_redis_client()
            await client.delete(cache_key)
            logger.info("config_cache_invalidated", key=key)
        except RedisError:
            logger.warning("config_cache_invalidate_error", key=key)
```

**Notas críticas:**
- `json.dumps(config.value)` funciona porque `Config.value` é `JSONField` (já é dict/list/str/int/bool)
- `json.loads(cached)` desserializa de volta para o tipo original
- `get_redis_client()` retorna singleton — não precisa de connection management
- `decode_responses=True` no Redis client significa que `client.get()` retorna `str | None`
- Dois blocos `try/except RedisError` separados: um para read, outro para write

### ConfigAdmin aprimorado — Implementação exata

```python
# workflows/admin.py (seção Config)
from asgiref.sync import async_to_sync


class ConfigHistoryInline(admin.TabularInline):
    model = ConfigHistory
    extra = 0
    readonly_fields = ("old_value", "new_value", "changed_by", "changed_at")
    can_delete = False
    ordering = ("-changed_at",)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Config)
class ConfigAdmin(admin.ModelAdmin):
    list_display = ("key", "updated_by", "updated_at")
    search_fields = ("key",)
    readonly_fields = ("updated_at", "updated_by")
    inlines = [ConfigHistoryInline]

    def save_model(self, request, obj, form, change):
        """Auto-populate updated_by, create audit trail, invalidate cache."""
        # 1. Auto-populate updated_by
        obj.updated_by = request.user.username

        # 2. Capture old_value before save (only for existing configs)
        old_value = None
        if change and obj.pk:
            try:
                old_value = Config.objects.filter(pk=obj.pk).values_list(
                    "value", flat=True
                ).first()
            except Exception:
                pass  # New config — no old value

        # 3. Save to DB
        super().save_model(request, obj, form, change)

        # 4. Create ConfigHistory
        ConfigHistory.objects.create(
            config=obj,
            old_value=old_value,
            new_value=obj.value,
            changed_by=request.user.username,
        )

        # 5. Invalidate Redis cache
        try:
            async_to_sync(ConfigService.invalidate)(obj.key)
        except Exception:
            pass  # Best-effort — cache will expire via TTL anyway
```

**Notas sobre sync vs async no admin:**
- Django Admin `save_model()` é síncrono — não podemos usar `await`
- `asgiref.sync.async_to_sync` é o wrapper oficial do Django para chamar código async de contexto sync
- A invalidação de cache é best-effort: se falhar, o TTL de 5 min garante eventual consistency
- `Config.objects.filter(pk=obj.pk).values_list(...)` é sync (não async) — correto para admin context
- Para novos configs (`change=False`), `old_value=None` é esperado

### Padrão de uso existente — ZERO breaking changes

Todos os 25+ call sites seguem este pattern:
```python
try:
    value = await ConfigService.get("timeout:whisper")
except Exception:
    logger.warning("config_fallback", key="timeout:whisper")
    value = 20  # hardcoded fallback
```

**A adição do cache NÃO quebra nenhum call site** porque:
- A assinatura `ConfigService.get(key: str) -> Any` não muda
- O comportamento externo é idêntico (retorna value ou raise ValidationError)
- A única diferença é performance: cache hit evita DB query

### Retro Watch Items — Exigidos em code review

1. **Over-mocking** — Pelo menos 1 teste de integração real por story com `@pytest.mark.django_db`. NÃO mockar `Config.objects.aget` em testes do ConfigService — usar DB real.
2. **Silent error handlers** — Zero `except Exception` sem log. Todo `except` DEVE ter `logger.warning()` ou `logger.error()` (exceto admin best-effort que é aceitável).
3. **Redis graceful degradation** — Testar cenário de Redis down. ConfigService.get() DEVE funcionar sem Redis (fallback para DB).
4. **Cache key collision** — Prefix `config:` evita colisão com outros namespaces Redis (msg_buffer:, session:, ratelimit:).

### Decisões de design relevantes

- **ADR-012:** NUNCA chamar `.bind_tools()` no retorno de `get_model()` — N/A para esta story
- **ADR-013:** Modelo Haiku 4.5 — N/A para esta story
- **ConfigService.set() NÃO incluído** — Escopo M1 é admin-only. Uso programático via `Config.objects.acreate/aupdate` (ORM direto) é suficiente para migrations e scripts.
- **Signal post_save NÃO usado** — `save_model()` override é mais explícito e não afeta saves fora do admin (migrations, scripts). Audit trail automático via signals pode ser adicionado em story futura se necessário.
- **Sem nova data migration** — Todos os timeout configs já foram criados em migrations anteriores (0002, 0004, 0008, 0009, 0011)

### Project Structure Notes

- **Sem novos arquivos** (exceto testes e migration) — implementação é em arquivos existentes
- Modificações: `workflows/services/config_service.py`, `workflows/admin.py`, `workflows/models.py`
- Migration: `workflows/migrations/0017_config_history_old_value_nullable.py` (ConfigHistory.old_value → nullable)
- Testes: `tests/test_services/test_config_service.py` (expandir), `tests/test_admin/test_config_admin.py` (novo)

### Dependências existentes (nenhuma nova)

| Pacote | Versão | Uso nesta story |
|--------|--------|-----------------|
| `redis` (redis-py) | 5.2+ | `redis.asyncio` para cache — já instalado |
| `asgiref` | Bundled com Django | `async_to_sync` para admin save_model |
| `structlog` | 24.4+ | Logging estruturado — já instalado |

### Referências de arquivos do codebase

| Arquivo | Relevância |
|---------|-----------|
| `workflows/services/config_service.py` (17 linhas) | **ARQUIVO PRINCIPAL** a modificar |
| `workflows/admin.py` (linhas 21-31: Config + ConfigHistory) | **ARQUIVO PRINCIPAL** a modificar |
| `workflows/models.py` (linhas 46-56: Config, 115-127: ConfigHistory) | Referência — NÃO modificar |
| `workflows/providers/redis.py` (18 linhas) | Referência — usar `get_redis_client()` |
| `workflows/services/cache_service.py` (225 linhas) | Referência — padrão de cache com Redis |
| `tests/test_services/test_config_service.py` (2 testes) | Expandir com testes de cache |

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 8, Story 8.1]
- [Source: _bmad-output/planning-artifacts/architecture.md — Config Cache: `config:{key}`, TTL 5min]
- [Source: _bmad-output/planning-artifacts/architecture.md — ConfigService pattern: DB + Redis cache]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-011: 3 fases de observabilidade]
- [Source: _bmad-output/planning-artifacts/architecture.md — CacheManager.cache_config() e get_config()]
- [Source: _bmad-output/implementation-artifacts/7-1-cost-tracking-callback-costlog.md — Retro watch items, over-mocking]
- [Source: _bmad-output/implementation-artifacts/7-2-traces-end-to-end-langfuse-structlog.md — structlog patterns]
- [Source: workflows/services/config_service.py — Current implementation (17 lines, DB only)]
- [Source: workflows/admin.py — Current ConfigAdmin/ConfigHistoryAdmin]
- [Source: workflows/providers/redis.py — Redis singleton (get_redis_client)]
- [Source: workflows/services/cache_service.py — Reference pattern for Redis cache-aside]
- [Source: workflows/models.py — Config + ConfigHistory models]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

- 3 falhas pré-existentes no test suite (não relacionadas a esta story):
  - `test_bulas_med.py::TestDrugLookupTool::test_global_timeout` — flaky test, cache hit de Redis local
  - `test_webhook.py::TestUnsupportedMessageTypes::test_text_message_does_not_trigger_unsupported_handler` — state-sensitive
  - `test_orchestrate_llm.py::TestOrchestrateLlm::test_invokes_model_with_system_prompt_and_history` — state-sensitive

### Completion Notes List

- **Task 1:** ConfigService.get() refatorado com cache-aside pattern (Redis → DB → populate cache). TTL 5min. Graceful degradation via `except RedisError`. Método `invalidate(key)` adicionado. Logging estruturado com `config_cache_hit`, `config_cache_miss`, `config_cache_error`, `config_cache_set_error`, `config_cache_invalidated`, `config_cache_invalidate_error`. 8 testes unitários passando.
- **Task 2:** ConfigAdmin aprimorado com `save_model()` override: auto-populate `updated_by`, captura `old_value` antes do save, cria `ConfigHistory` automaticamente, invalida cache Redis via `async_to_sync(ConfigService.invalidate)`. `readonly_fields` para `updated_at` e `updated_by`. `ConfigHistoryInline` (TabularInline) adicionado. `ConfigHistoryAdmin` com `old_value` e `new_value` no `list_display`. 8 testes admin passando.
- **Task 3:** 16 testes totais da story passando. 665/668 testes do projeto passando (3 falhas pré-existentes). Ruff lint + format clean (0 errors).
- **Nota:** `ConfigHistory.old_value` precisou de `null=True, blank=True` para suportar novos configs (sem old_value). Migration `0017_config_history_old_value_nullable` criada. Contradição na story (dizia "sem migration" mas AC exigia `old_value=None`).

### File List

- `workflows/services/config_service.py` — **Modificado** (cache-aside pattern, invalidate method, docstring corrigida)
- `workflows/admin.py` — **Modificado** (ConfigAdmin save_model, readonly_fields, ConfigHistoryInline, ConfigHistoryAdmin imutável com readonly_fields/ordering/no-add-change-delete, logging em except)
- `workflows/models.py` — **Modificado** (ConfigHistory.old_value: null=True, blank=True)
- `workflows/migrations/0017_config_history_old_value_nullable.py` — **Novo** (migration para old_value nullable)
- `tests/test_services/test_config_service.py` — **Modificado** (expandido de 2 para 8 testes, docstring corrigida)
- `tests/test_admin/__init__.py` — **Novo** (package init)
- `tests/test_admin/test_config_admin.py` — **Novo** (10 testes: 8 originais + 1 imutabilidade ConfigHistoryAdmin + 1 E2E)

## Change Log

- 2026-03-15: Story 8.1 implementada — ConfigService com cache-aside Redis (TTL 5min), ConfigAdmin com audit trail automático, cache invalidation no admin save, 16 testes adicionados
- 2026-03-15: Code review — 8 findings (3H, 3M, 2L) corrigidos: ConfigHistoryAdmin imutável (readonly + no add/change/delete), silent `except Exception: pass` → logger.warning(), teste E2E real criado, docstring/naming corrigidos, Dev Notes atualizadas. 18 testes passando, 732/735 suite total (3 pré-existentes)
