# Story 8.2: System Prompt Versionado com Histórico e Rollback

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a equipe Medway,
I want editar o system prompt do Medbrain sem deploy e poder reverter para versões anteriores,
so that itero rapidamente na qualidade das respostas sem risco de perder uma versão boa.

## Acceptance Criteria

1. **AC1 — Model SystemPromptVersion** O model `SystemPromptVersion` em `workflows/models.py`
   - Tem campos: content (TextField), author (CharField max_length=100), is_active (BooleanField default=False), created_at (DateTimeField auto_now_add)
   - O `pk` (BigAutoField) serve como número de versão (auto-incrementa)
   - Apenas UMA versão pode ter `is_active=True` por vez via `UniqueConstraint(condition=Q(is_active=True), fields=["is_active"], name="unique_active_system_prompt")`

2. **AC2 — Ativação com desativação automática** Ao salvar uma nova versão ou ativar uma existente no Django Admin
   - A versão anterior ativa é marcada como `is_active=False` (FR34)
   - A nova versão é marcada como `is_active=True`
   - O `author` é registrado automaticamente a partir do `request.user` (FR35)
   - O cache Redis é invalidado imediatamente

3. **AC3 — Histórico e rollback** A equipe acessa o histórico de versões no Django Admin
   - Vê todas as versões com: número (pk), autor, data de criação, status ativa/inativa (FR35)
   - Pode selecionar qualquer versão e usar ação "Ativar" para restaurá-la (FR36)
   - A ativação é registrada em log structlog

4. **AC4 — get_system_prompt() dinâmico** `workflows/whatsapp/prompts/system.py`
   - `get_system_prompt_async()` busca a versão ativa: Redis cache → DB → fallback hardcoded
   - Cache Redis com chave `config:system_prompt`, TTL 5min (namespace consistente com Story 8.1)
   - Se nenhuma versão ativa no DB, usa fallback para `SYSTEM_PROMPT` hardcoded (zero downtime)
   - `build_system_message()` tornado async, continua com `cache_control: {"type": "ephemeral"}`

5. **AC5 — Seed da versão inicial** Data migration cria a primeira `SystemPromptVersion`
   - Conteúdo: cópia exata do `SYSTEM_PROMPT` hardcoded atual
   - `is_active=True`, `author="system"`
   - Garante funcionamento imediato após migration

6. **AC6 — Testes** Cobrindo:
   - Model: criação, constraint unique active, __str__
   - Admin: ação "Ativar", save_model auto-author, auto-desativação, cache invalidation
   - `get_system_prompt_async()`: cache hit, cache miss + DB, nenhuma versão ativa (hardcoded fallback), Redis error (graceful degradation)
   - Integration: `build_system_message()` async com prompt do DB
   - Pelo menos 1 teste com `@pytest.mark.django_db` usando BD real

## Tasks / Subtasks

- [x] Task 1: Criar model SystemPromptVersion (AC: #1, #5)
  - [x] 1.1 Adicionar `SystemPromptVersion` ao `workflows/models.py`
  - [x] 1.2 Adicionar `UniqueConstraint` no Meta para garantir máximo 1 versão ativa
  - [x] 1.3 Criar migration `workflows/migrations/0015_add_system_prompt_version.py` (ou próximo número disponível pós 8.1)
  - [x] 1.4 Criar data migration que copia `SYSTEM_PROMPT` hardcoded como primeira versão ativa (author="system")
  - [x] 1.5 Testes unitários para model — `tests/test_models/test_core_models.py`

- [x] Task 2: Criar SystemPromptVersionAdmin com ação "Ativar" (AC: #2, #3)
  - [x] 2.1 Adicionar `SystemPromptVersionAdmin` em `workflows/admin.py`
  - [x] 2.2 Implementar ação admin `activate_version` que desativa todas e ativa a selecionada
  - [x] 2.3 Override `save_model()` para auto-preencher author, desativar versão anterior, invalidar cache
  - [x] 2.4 Testes para admin — `tests/test_admin/test_system_prompt_admin.py` (novo)

- [x] Task 3: Atualizar get_system_prompt() com cache Redis + DB fallback (AC: #4)
  - [x] 3.1 Criar `get_system_prompt_async()` com cache-aside: Redis → DB → hardcoded
  - [x] 3.2 Tornar `build_system_message()` async
  - [x] 3.3 Atualizar `orchestrate_llm.py` para `await build_system_message()`
  - [x] 3.4 Testes — `tests/test_whatsapp/test_prompts/test_system.py` (novo)

- [x] Task 4: Testes de integração + lint (AC: #6)
  - [x] 4.1 Teste integração: ativar versão → get_system_prompt retorna conteúdo correto
  - [x] 4.2 Teste: build_system_message() retorna SystemMessage com cache_control
  - [x] 4.3 Todos os testes passando, 0 regressões, ruff lint+format clean

## Dev Notes

### Dependência de Story 8.1 (ConfigService + Redis)

**Story 8.1 DEVE ser implementada antes de 8.2.** Story 8.1 introduz:
- `ConfigService.get()` com cache-aside Redis (`config:{key}`, TTL 5min)
- `ConfigService.invalidate(key)` para deletar cache imediatamente
- `async_to_sync` pattern no admin `save_model()` para chamar código async
- `ConfigHistoryInline` como referência de pattern para admin UX

Story 8.2 reutiliza o **namespace** `config:` e o **pattern `async_to_sync`** de 8.1, mas NÃO usa `ConfigService.get()` diretamente (SystemPromptVersion é model separado, não Config).

### O que já existe (NÃO reimplementar)

| Componente | Status Atual | O que falta (esta story) |
|------------|-------------|--------------------------|
| `SYSTEM_PROMPT` em `prompts/system.py` | Hardcoded — 93 linhas | Manter como **fallback** (não deletar) |
| `get_system_prompt()` | Retorna constante string (sync) | **ADICIONAR** `get_system_prompt_async()` com cache |
| `build_system_message()` | Sync, wraps com `cache_control: {"type": "ephemeral"}` | **TORNAR ASYNC** |
| `orchestrate_llm.py` | Chama `build_system_message()` sync | **ATUALIZAR** para `await build_system_message()` |
| `get_redis_client()` em `providers/redis.py` | Singleton `redis.asyncio`, `decode_responses=True` | Usar diretamente para cache |
| Django Admin | Todos os models registrados (Story 8.1 aprimora ConfigAdmin) | **ADICIONAR** SystemPromptVersionAdmin |
| `async_to_sync` pattern | Introduzido em Story 8.1 no ConfigAdmin | Reutilizar no SystemPromptVersionAdmin |

### SystemPromptVersion model — Schema exato

```python
class SystemPromptVersion(models.Model):
    """Versioned system prompt with activation control (FR34-FR36)."""

    content = models.TextField()
    author = models.CharField(max_length=100)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "system_prompt_versions"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                condition=models.Q(is_active=True),
                fields=["is_active"],
                name="unique_active_system_prompt",
            ),
        ]

    def __str__(self) -> str:
        status = "ATIVA" if self.is_active else "inativa"
        return f"SystemPromptVersion(v{self.pk}, {status}, {self.author})"
```

**Design notes:**
- O `pk` (BigAutoField) serve como número de versão — sem campo `version` separado
- `UniqueConstraint` com `condition=Q(is_active=True)` cria partial unique index no PostgreSQL
- `ordering = ["-created_at"]` mostra versões mais recentes primeiro no admin
- `db_table = "system_prompt_versions"` — naming convention consistente com demais tabelas

### Django Admin — SystemPromptVersionAdmin

```python
from asgiref.sync import async_to_sync

from workflows.models import SystemPromptVersion
from workflows.providers.redis import get_redis_client

PROMPT_CACHE_KEY = "config:system_prompt"


def _invalidate_prompt_cache():
    """Invalidar cache Redis do system prompt (sync context)."""
    async def _delete():
        redis = get_redis_client()
        await redis.delete(PROMPT_CACHE_KEY)

    try:
        async_to_sync(_delete)()
    except Exception:
        pass  # Best-effort — TTL de 5 min garante eventual consistency


@admin.register(SystemPromptVersion)
class SystemPromptVersionAdmin(admin.ModelAdmin):
    list_display = ("pk", "author", "is_active", "content_preview", "created_at")
    list_filter = ("is_active", "author")
    readonly_fields = ("created_at",)
    actions = ["activate_version"]
    ordering = ["-created_at"]

    @admin.display(description="Conteúdo (preview)")
    def content_preview(self, obj):
        return obj.content[:100] + "..." if len(obj.content) > 100 else obj.content

    @admin.action(description="Ativar versão selecionada (desativa as demais)")
    def activate_version(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request, "Selecione exatamente UMA versão.", level="error"
            )
            return
        version = queryset.first()
        SystemPromptVersion.objects.filter(is_active=True).update(is_active=False)
        version.is_active = True
        version.save(update_fields=["is_active"])
        _invalidate_prompt_cache()
        logger.info(
            "system_prompt_activated",
            version_id=version.pk,
            activated_by=request.user.username,
        )
        self.message_user(request, f"Versão {version.pk} ativada com sucesso.")

    def save_model(self, request, obj, form, change):
        if not obj.author:
            obj.author = request.user.username or request.user.email or "admin"
        if obj.is_active:
            SystemPromptVersion.objects.filter(is_active=True).exclude(
                pk=obj.pk
            ).update(is_active=False)
        super().save_model(request, obj, form, change)
        if obj.is_active:
            _invalidate_prompt_cache()
```

**Notas:**
- `_invalidate_prompt_cache()` usa `async_to_sync` (padrão de Story 8.1) para chamar Redis async de contexto sync
- Best-effort: se cache invalidation falha, TTL de 5 min garante eventual consistency
- `activate_version` valida seleção única, desativa todas, ativa selecionada, invalida cache
- `save_model` auto-preenche author e gerencia is_active

### get_system_prompt_async() — Implementação com cache Redis

```python
# workflows/whatsapp/prompts/system.py
import structlog

from langchain_core.messages import SystemMessage
from redis.exceptions import RedisError

from workflows.providers.redis import get_redis_client

logger = structlog.get_logger(__name__)

CACHE_KEY = "config:system_prompt"
CACHE_TTL = 300  # 5 minutos (consistente com FR33, Story 8.1 TTL)

SYSTEM_PROMPT = """\
...  # Manter constante hardcoded existente INTACTA como fallback
"""


async def get_system_prompt_async() -> str:
    """Fetch active system prompt: Redis cache → DB → hardcoded fallback.

    Fallback chain garante zero downtime:
    1. Redis cache (config:system_prompt, TTL 5min)
    2. DB query (SystemPromptVersion where is_active=True)
    3. Hardcoded SYSTEM_PROMPT constant (último recurso)
    """
    # 1. Tentar cache Redis
    try:
        redis = get_redis_client()
        cached = await redis.get(CACHE_KEY)
        if cached:
            logger.debug("system_prompt_cache_hit")
            return cached
        logger.debug("system_prompt_cache_miss")
    except RedisError:
        logger.warning("system_prompt_cache_error", action="fallback_to_db")

    # 2. Buscar no DB
    try:
        from workflows.models import SystemPromptVersion

        version = await SystemPromptVersion.objects.filter(is_active=True).afirst()
        if version:
            # Popular cache (best-effort)
            try:
                redis = get_redis_client()
                await redis.setex(CACHE_KEY, CACHE_TTL, version.content)
            except RedisError:
                logger.warning("system_prompt_cache_set_error")
            logger.info("system_prompt_loaded_from_db", version_id=version.pk)
            return version.content
    except Exception:
        logger.exception("system_prompt_db_error")

    # 3. Fallback hardcoded
    logger.warning("system_prompt_using_hardcoded_fallback")
    return SYSTEM_PROMPT


def get_system_prompt() -> str:
    """Sync wrapper — retorna hardcoded (backward compat para testes sync)."""
    return SYSTEM_PROMPT


async def build_system_message() -> SystemMessage:
    """Build SystemMessage with Anthropic Prompt Caching (cache_control ephemeral).

    Agora async — busca prompt versionado do DB/Redis.
    """
    prompt = await get_system_prompt_async()
    return SystemMessage(
        content=[
            {
                "type": "text",
                "text": prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]
    )
```

**Notas críticas:**
- `decode_responses=True` no Redis client significa que `redis.get()` retorna `str | None` (não bytes)
- O prompt é text puro, NÃO precisa de `json.dumps/loads` (diferente do `ConfigService.get()` que lida com JSONField)
- Import de `SystemPromptVersion` é lazy (dentro da função) para evitar circular imports
- `RedisError` importado de `redis.exceptions` para catch preciso (não `Exception` genérico)
- `SYSTEM_PROMPT` constante hardcoded mantida INTACTA — nunca deletar, é o safety net

### orchestrate_llm.py — Mudança mínima

```python
# ANTES (2 locais — primeira entrada e re-entry de tools):
if is_tool_reentry:
    messages = [build_system_message(), *current_messages]
else:
    messages = [build_system_message(), *current_messages, user_msg]

# DEPOIS:
system_msg = await build_system_message()
if is_tool_reentry:
    messages = [system_msg, *current_messages]
else:
    messages = [system_msg, *current_messages, user_msg]
```

**IMPORTANTE:** Uma única chamada `await build_system_message()` ANTES do if/else. Não chamar duas vezes (seria 2 cache lookups desnecessários).

### Data Migration — Seed da versão inicial

```python
# workflows/migrations/XXXX_seed_initial_system_prompt.py
from django.db import migrations


INITIAL_PROMPT = """\
Você é o **Medbrain**, tutor médico virtual da **Medway**, especializado em ajudar \
alunos de medicina e residentes com dúvidas médicas.
...
"""  # Copiar EXATAMENTE todo o SYSTEM_PROMPT de prompts/system.py (93 linhas)


def seed_initial_prompt(apps, schema_editor):
    SystemPromptVersion = apps.get_model("workflows", "SystemPromptVersion")
    if not SystemPromptVersion.objects.filter(is_active=True).exists():
        SystemPromptVersion.objects.create(
            content=INITIAL_PROMPT,
            author="system",
            is_active=True,
        )


def reverse_seed(apps, schema_editor):
    SystemPromptVersion = apps.get_model("workflows", "SystemPromptVersion")
    SystemPromptVersion.objects.filter(author="system").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("workflows", "XXXX_add_system_prompt_version"),  # migration anterior
    ]

    operations = [
        migrations.RunPython(seed_initial_prompt, reverse_seed),
    ]
```

**NOTA:** Números de migration dependem de quantas migrations Story 8.1 criar. Se 8.1 cria 0 novas migrations (só modifica code), então 0015 e 0016. Se 8.1 cria migrations, ajustar.

### Decisões de design relevantes

- **ADR-012:** NUNCA chamar `.bind_tools()` no retorno de `get_model()` — N/A para esta story
- **ADR-013:** Modelo Haiku 4.5 — N/A, mas prompt é usado nesse modelo
- **structlog obrigatório** — NUNCA `print()`, sempre `structlog.get_logger(__name__)`
- **Model dedicado vs Config** — SystemPromptVersion é model dedicado (não Config) porque: (a) conteúdo é grande (TextField vs JSONField), (b) versionamento nativo (cada row = 1 versão), (c) histórico é a própria tabela (não precisa de ConfigHistory separado)
- **Fallback hardcoded obrigatório** — Se DB e Redis falharem, sistema DEVE continuar com prompt hardcoded (zero downtime)
- **Cache key** — `config:system_prompt` usa namespace `config:` consistente com Story 8.1 (camada 3 do Redis)
- **`get_system_prompt()` sync mantido** — Backward compat para testes sync e possível uso em contextos não-async

### Retro Watch Items — Exigidos em code review

1. **Over-mocking** — Pelo menos 1 teste de integração real com `@pytest.mark.django_db`. NÃO mockar `SystemPromptVersion.objects` nos testes do `get_system_prompt_async()`.
2. **Error handler silencioso** — Zero `except Exception` sem log. Todo `except` DEVE ter `logger.warning()` ou `logger.exception()`.
3. **Cache invalidation** — Testar que ativação de nova versão no admin invalida cache Redis.
4. **Async/sync boundary** — Verificar que `build_system_message()` async funciona em `orchestrate_llm.py` (já é contexto async). Verificar que testes existentes não quebram.
5. **Data migration** — Diff com SYSTEM_PROMPT original — conteúdo deve ser EXATAMENTE idêntico.
6. **UniqueConstraint** — Testar que DB rejeita dois registros com `is_active=True` simultâneos.

### Impacto nos testes existentes

| Arquivo de teste | Impacto | Ação necessária |
|-----------------|---------|-----------------|
| `tests/test_whatsapp/test_nodes/test_orchestrate_llm.py` | `build_system_message()` agora é async | Mock ou patch deve retornar coroutine (ou usar `AsyncMock`) |
| `tests/test_whatsapp/test_error_fallback.py` | `TestSystemPromptPartialResponse` valida conteúdo | Continua ok se importa `SYSTEM_PROMPT` diretamente (constante mantida) |
| `tests/test_whatsapp/test_nodes/test_orchestrate_llm_tools.py` | Mesma mudança do orchestrate_llm | Mock/patch de `build_system_message` precisa ser async |
| `tests/test_whatsapp/conftest.py` | Pode precisar fixture para mock de `build_system_message` | Avaliar durante implementação |

**CUIDADO:** A mudança de `build_system_message()` de sync para async é a maior causa potencial de regressão. Todos os testes que importam ou mocam essa função precisam ser atualizados.

### Project Structure Notes

- Novo model: `SystemPromptVersion` em `workflows/models.py`
- Modificados: `workflows/whatsapp/prompts/system.py` (async + cache), `workflows/whatsapp/nodes/orchestrate_llm.py` (await), `workflows/admin.py` (SystemPromptVersionAdmin)
- Novas migrations: 2 (schema + data seed) — números dependem de Story 8.1
- Novos testes: `tests/test_whatsapp/test_prompts/__init__.py`, `tests/test_whatsapp/test_prompts/test_system.py`, `tests/test_admin/test_system_prompt_admin.py`
- Testes atualizados: `tests/test_whatsapp/test_nodes/test_orchestrate_llm.py`, `tests/test_whatsapp/test_nodes/test_orchestrate_llm_tools.py`
- Testes atualizados: `tests/test_models/test_core_models.py` (model tests SystemPromptVersion)

### Dependências de versão

| Pacote | Versão | Notas |
|--------|--------|-------|
| `django` | `>=5.1` | Já instalado — `UniqueConstraint(condition=)` suportado |
| `redis` (redis-py) | `5.2+` | Já instalado — `redis.asyncio` para cache |
| `asgiref` | Bundled Django | `async_to_sync` para admin context (Story 8.1 pattern) |
| `structlog` | `>=24.4` | Já instalado |

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 8, Story 8.2: System Prompt Versionado]
- [Source: _bmad-output/planning-artifacts/architecture.md — Lines 993-1069: Redis Cache Layers (config:key, TTL 5min)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Lines 654-671: AnthropicPromptCachingMiddleware pattern]
- [Source: _bmad-output/planning-artifacts/architecture.md — Lines 1517-1541: Django Admin patterns]
- [Source: _bmad-output/planning-artifacts/architecture.md — Lines 2530-2551: Database schema management]
- [Source: _bmad-output/implementation-artifacts/8-1-config-service-aprimorado-hot-reload-redis-audit-trail.md — ConfigService cache-aside, async_to_sync pattern, invalidate()]
- [Source: workflows/whatsapp/prompts/system.py — Current SYSTEM_PROMPT hardcoded + build_system_message()]
- [Source: workflows/services/config_service.py — Current ConfigService (será aprimorado em 8.1)]
- [Source: workflows/providers/redis.py — get_redis_client() singleton]
- [Source: workflows/models.py — Config, ConfigHistory models]
- [Source: workflows/admin.py — Current admin registrations]
- [Source: workflows/whatsapp/nodes/orchestrate_llm.py — build_system_message() usage (lines 11, 58, 61)]
- [Source: _bmad-output/implementation-artifacts/7-1-cost-tracking-callback-costlog.md — Code review learnings (over-mocking)]
- [Source: _bmad-output/implementation-artifacts/7-2-traces-end-to-end-langfuse-structlog.md — Async patterns, structlog]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

- Data migration seed: conteúdo do SYSTEM_PROMPT copiado EXATAMENTE (93 linhas) para migration 0016
- SQLite partial unique index: funcional com UniqueConstraint(condition=Q(is_active=True))
- Tests que não mockavam build_system_message tentavam conexão Redis real — corrigido adicionando @patch

### Completion Notes List

- Task 1: Model SystemPromptVersion criado com UniqueConstraint partial index, migrations 0015 (schema) e 0016 (data seed), 8 testes unitários passando
- Task 2: SystemPromptVersionAdmin com ação activate_version, save_model auto-author, cache invalidation via _invalidate_prompt_cache(), 12 testes passando
- Task 3: get_system_prompt_async() com fallback chain Redis→DB→hardcoded, build_system_message() tornado async, orchestrate_llm.py atualizado para await, 9 testes novos passando
- Task 4: Testes existentes atualizados (test_orchestrate_llm_tools.py — 4 testes precisavam mock de build_system_message), 100 testes story-related passando, ruff clean
- Retro items: 1 teste integração real com @pytest.mark.django_db(transaction=True), todo except tem logger, UniqueConstraint testado

### File List

**Novos:**
- workflows/migrations/0015_add_system_prompt_version.py
- workflows/migrations/0016_seed_initial_system_prompt.py
- tests/test_admin/test_system_prompt_admin.py
- tests/test_whatsapp/test_prompts/__init__.py
- tests/test_whatsapp/test_prompts/test_system.py

**Modificados:**
- workflows/models.py
- workflows/admin.py
- workflows/whatsapp/prompts/system.py
- workflows/whatsapp/nodes/orchestrate_llm.py
- tests/test_models/test_core_models.py
- tests/test_whatsapp/test_nodes/test_orchestrate_llm_tools.py
- tests/test_graph.py (review fix: mock build_system_message async)

### Change Log

- 2026-03-15: Implementação completa da Story 8.2 — SystemPromptVersion model, admin com ativação/rollback, get_system_prompt_async() com cache Redis + DB fallback, build_system_message() async, 29 testes novos
- 2026-03-15: Code Review (AI) — 8 issues encontrados (3H, 3M, 2L), todos corrigidos:
  - H1: Regressão test_graph.py — build_system_message async tentava Redis sem mock (adicionado mock)
  - H2: Over-mocking em test_system.py — 3 testes convertidos para DB real com @pytest.mark.django_db
  - H3: transaction.atomic() adicionado em activate_version e save_model (integridade de dados)
  - M1: _invalidate_prompt_cache agora captura (RedisError, RuntimeError, OSError) em vez de Exception
  - M2: get_system_prompt_async() agora captura (RedisError, RuntimeError, OSError) para Redis
  - M3: _make_state() delegado a make_whatsapp_state do conftest (DRY)
  - L1: sync_to_async substituído por async ORM nativo (.aupdate, .acreate)
  - L2: Teste automatizado verificando INITIAL_PROMPT == SYSTEM_PROMPT (Retro Watch Item #5)
