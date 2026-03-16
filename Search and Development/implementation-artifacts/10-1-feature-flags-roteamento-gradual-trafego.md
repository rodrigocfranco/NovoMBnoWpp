# Story 10.1: Feature Flags + Roteamento Gradual de Tráfego

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a equipe Medway,
I want controlar o percentual de tráfego roteado para o código novo vs n8n,
so that faço a migração de forma segura e gradual, podendo parar a qualquer momento.

## Acceptance Criteria

1. **AC1 — Serviço de feature flags com hash-based bucketing**
   **Given** `workflows/services/feature_flags.py` com `is_feature_enabled(user_id, feature)`
   **When** avalia se um usuário usa código novo
   **Then** usa hash-based bucketing: `hashlib.md5(user_id.encode(), usedforsecurity=False).hexdigest()` → `int(hex, 16) % 100`
   **And** compara com `rollout_percentage` do Config model (`feature_flag:new_pipeline`)
   **And** o mesmo usuário SEMPRE recebe o mesmo tratamento (determinístico) (FR44)

2. **AC2 — Roteamento gradual via Django Admin**
   **Given** a equipe altera `rollout_percentage` de 5 para 25 no Django Admin
   **When** a config é recarregada (TTL 5min Redis)
   **Then** ~25% dos usuários passam a usar o código novo
   **And** os outros ~75% continuam usando n8n (FR46)
   **And** ambos coexistem acessando o mesmo Supabase (FR45)

3. **AC3 — Rollback instantâneo**
   **Given** problemas são detectados no código novo
   **When** a equipe reduz `rollout_percentage` para 0
   **Then** 100% do tráfego volta para n8n em até 5 minutos
   **And** nenhum dado é perdido (FR45)

4. **AC4 — Migrations preservam dados existentes**
   **Given** Django migrations
   **When** executadas sobre o Supabase existente
   **Then** preservam todos os dados existentes — apenas adicionam novas tabelas/colunas (FR45)
   **And** n8n continua funcionando normalmente durante a migração

5. **AC5 — Testes**
   **Given** a suíte de testes
   **When** executada
   **Then** cobre: determinismo do bucketing, distribuição uniforme, cache hit/miss, Redis failure graceful degradation, rollout 0% e 100%, rollback via admin
   **And** pelo menos 1 teste de integração real com DB (`@pytest.mark.django_db`)
   **And** zero regressões nos testes existentes (~737 testes passando)

## Tasks / Subtasks

- [x] Task 1: Criar `FeatureFlagService` em `workflows/services/feature_flags.py` (AC: #1)
  - [x] 1.1 Criar módulo `workflows/services/feature_flags.py`
  - [x] 1.2 Implementar `async def is_feature_enabled(user_id: str, feature: str) -> bool` usando `ConfigService.get(f"feature_flag:{feature}")`
  - [x] 1.3 Hash-based bucketing: `hashlib.md5(user_id.encode(), usedforsecurity=False).hexdigest()` → `int(hex[:8], 16) % 100`
  - [x] 1.4 Retornar `bucket < rollout_percentage`; se config não existe ou erro, retornar `False` (safe default)
  - [x] 1.5 Logging estruturado: `feature_flag_evaluated`, `feature_flag_disabled` (config missing)
  - [x] 1.6 Testes unitários: 8+ testes (determinismo, distribuição, cache hit/miss, Redis down, rollout 0%, 100%, config missing, tipo inválido)

- [x] Task 2: Data migration para configs iniciais de feature flags (AC: #4)
  - [x] 2.1 Criar migration `0021_add_feature_flag_configs.py` com RunPython (forward + reverse)
  - [x] 2.2 Seed `feature_flag:new_pipeline` com valor `{"rollout_percentage": 0, "description": "Roteamento gradual n8n → código novo"}`
  - [x] 2.3 Seed `feature_flag:shadow_mode` com valor `{"rollout_percentage": 0, "description": "Shadow Mode para comparação de respostas"}` (preparação para Story 10.2)

- [x] Task 3: Integrar feature flags no webhook entry point (AC: #1, #2, #3)
  - [x] 3.1 No `views.py` (webhook handler), após identificar o `user_id`, chamar `await is_feature_enabled(user_id, "new_pipeline")`
  - [x] 3.2 Se `True` → processar via LangGraph pipeline (código novo)
  - [x] 3.3 Se `False` → retornar 200 OK sem processar (n8n cuida — coexistência via mesmo webhook ou webhook separado, dependendo da configuração)
  - [x] 3.4 Logging: `feature_flag_routed` com `pipeline="new"` ou `pipeline="n8n"`, `user_id`, `bucket`
  - [x] 3.5 Testes: webhook com feature flag on/off, transição de rollout

- [x] Task 4: Testes de integração e lint (AC: #5)
  - [x] 4.1 Teste E2E: admin save `rollout_percentage` → cache invalidated → `is_feature_enabled()` retorna novo resultado
  - [x] 4.2 Teste determinismo: mesmo `user_id` SEMPRE retorna mesmo resultado para mesmo `rollout_percentage`
  - [x] 4.3 Teste distribuição: com 1000 user_ids aleatórios e rollout_percentage=50, ~50% ±5% devem ser True
  - [x] 4.4 Teste rollback: `rollout_percentage=0` → 100% retorna False; `rollout_percentage=100` → 100% retorna True
  - [x] 4.5 Ruff lint + format passam (0 errors) em todos os arquivos modificados
  - [x] 4.6 Todos os testes passando (excluindo tests/e2e e tests/integration) — target: ~750+

## Dev Notes

### O que já existe (NÃO reimplementar)

| Componente | Status Atual | O que falta (esta story) |
|------------|-------------|--------------------------|
| `Config` model em `models.py` | key (unique), value (JSON), updated_by, updated_at | Nenhuma mudança — usar as-is |
| `ConfigHistory` model em `models.py` | FK Config, old_value, new_value, changed_by, changed_at | Nenhuma mudança |
| `ConfigService.get(key)` em `services/config_service.py` | Cache-aside Redis (TTL 5min), graceful degradation | Nenhuma mudança — usar como base |
| `ConfigService.invalidate(key)` | Deleta cache key Redis | Nenhuma mudança — já funciona para feature flags |
| `ConfigAdmin` em `admin.py` | save_model com audit trail, cache invalidation, ConfigHistoryInline | Nenhuma mudança — feature flags usam o mesmo Config model |
| `get_redis_client()` em `providers/redis.py` | Singleton `redis.asyncio`, decode_responses=True | Nenhuma mudança |
| Webhook view em `views.py` | Recebe POST, valida signature, processa via graph | **MODIFICAR** para checar feature flag antes de processar |
| Última migration | `0020_seed_system_prompt_v2_quiz.py` (Story 9.1) | **NOVA** migration `0021_add_feature_flag_configs.py` |

### FeatureFlagService — Implementação

```python
# workflows/services/feature_flags.py
"""Feature flag service for gradual traffic routing (Strangler Fig)."""

import hashlib

import structlog

from workflows.services.config_service import ConfigService

logger = structlog.get_logger(__name__)


async def is_feature_enabled(user_id: str, feature: str) -> bool:
    """Check if feature is enabled for user via hash-based bucketing.

    Uses MD5 hash of user_id for deterministic, uniform distribution.
    Same user always gets same treatment for same rollout_percentage.

    Args:
        user_id: Unique user identifier (phone number or DB id).
        feature: Feature flag name (e.g., "new_pipeline").

    Returns:
        True if user is in the rollout bucket, False otherwise.
        Returns False on any error (safe default).
    """
    try:
        config = await ConfigService.get(f"feature_flag:{feature}")
    except Exception:
        logger.debug("feature_flag_disabled", feature=feature, reason="config_not_found")
        return False

    if not isinstance(config, dict):
        logger.warning("feature_flag_invalid_config", feature=feature, config_type=type(config).__name__)
        return False

    rollout_percentage = config.get("rollout_percentage", 0)
    if not isinstance(rollout_percentage, (int, float)) or rollout_percentage <= 0:
        return False
    if rollout_percentage >= 100:
        return True

    # Hash-based bucketing: deterministic, uniform distribution
    hash_hex = hashlib.md5(user_id.encode(), usedforsecurity=False).hexdigest()
    bucket = int(hash_hex[:8], 16) % 100  # Use first 8 hex chars (32 bits)

    enabled = bucket < rollout_percentage
    logger.debug(
        "feature_flag_evaluated",
        feature=feature,
        user_id=user_id,
        bucket=bucket,
        rollout_percentage=rollout_percentage,
        enabled=enabled,
    )
    return enabled
```

**Notas críticas de implementação:**

- **`usedforsecurity=False`**: Necessário para compatibilidade com FIPS-enabled systems (Python 3.9+). MD5 aqui é para distribuição uniforme, não segurança.
- **`hash_hex[:8]`**: Usa apenas 8 hex chars (32 bits → 4 bilhões de valores) para evitar overflow em `int()` com hex completo. `% 100` distribui uniformemente.
- **Safe default `False`**: Se config não existe ou erro, retorna `False` (tráfego vai para n8n). Nunca falha silenciosamente para o pipeline novo.
- **Não é classe**: Função standalone async, sem estado. ConfigService já é stateless. Consistente com padrão de tools e nodes.
- **Cache via ConfigService**: Não implementa cache próprio. `ConfigService.get()` já tem cache Redis TTL 5min.
- **`except Exception`**: Catch amplo intencional no try do ConfigService — qualquer falha = safe default False.

### Integração no Webhook — Ponto de roteamento

O ponto de decisão fica no webhook view, **antes** de criar a task de processamento. A decisão de roteamento deve ser avaliada **após** identificar o usuário (phone → user_id).

```python
# Em views.py, no handler de mensagem (dentro do asyncio.create_task)
from workflows.services.feature_flags import is_feature_enabled

# Após extrair phone_number do payload:
use_new_pipeline = await is_feature_enabled(phone_number, "new_pipeline")

if use_new_pipeline:
    # Processar via LangGraph (código novo)
    logger.info("feature_flag_routed", pipeline="new", phone=phone_number)
    await process_with_graph(...)
else:
    # n8n cuida — não processar aqui
    logger.info("feature_flag_routed", pipeline="n8n", phone=phone_number)
    return  # Sai sem processar
```

**Decisão de arquitetura — coexistência n8n:**
- Se **mesmo webhook** (n8n e código novo recebem o mesmo POST): o código novo deve ignorar mensagens quando `is_feature_enabled=False` (retorna 200 OK sem processar).
- Se **webhooks separados** (Meta envia para URLs diferentes): a lógica fica no roteador externo. Neste caso, `is_feature_enabled` pode ser usada apenas para logging/métricas.
- **Decisão mais provável:** mesmo webhook, pois é mais simples e não requer mudança na configuração do Meta Business Manager.

### Config value format

```json
{
  "rollout_percentage": 0,
  "description": "Roteamento gradual n8n → código novo"
}
```

- `rollout_percentage`: int 0-100. Controlado via Django Admin.
- `description`: string informativa para equipe (exibida no admin).
- **Extensível**: Campos futuros podem ser adicionados sem migration (JSONField).

### Data migration pattern

```python
# workflows/migrations/0020_add_feature_flag_configs.py
from django.db import migrations


def add_feature_flag_configs(apps, schema_editor):
    Config = apps.get_model("workflows", "Config")
    configs = [
        {
            "key": "feature_flag:new_pipeline",
            "value": {"rollout_percentage": 0, "description": "Roteamento gradual n8n → código novo"},
            "updated_by": "migration",
        },
        {
            "key": "feature_flag:shadow_mode",
            "value": {"rollout_percentage": 0, "description": "Shadow Mode para comparação de respostas"},
            "updated_by": "migration",
        },
    ]
    for config in configs:
        Config.objects.update_or_create(key=config["key"], defaults=config)


def remove_feature_flag_configs(apps, schema_editor):
    Config = apps.get_model("workflows", "Config")
    Config.objects.filter(key__startswith="feature_flag:").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("workflows", "0019_add_alert_configs"),
    ]

    operations = [
        migrations.RunPython(add_feature_flag_configs, remove_feature_flag_configs),
    ]
```

### Padrões deste projeto (Retro Epics anteriores)

1. **Over-mocking**: Pelo menos 1 teste de integração real com `@pytest.mark.django_db`. NÃO mockar `Config.objects.aget` em testes do FeatureFlagService — usar DB real via ConfigService.
2. **Silent error handlers**: Zero `except Exception` sem log. Todo `except` DEVE ter `logger.warning()` ou `logger.debug()`.
3. **Redis graceful degradation**: Testar cenário de Redis down. `is_feature_enabled()` DEVE retornar `False` sem Redis (safe default).
4. **Exception handling**: Capturar `(RedisError, RuntimeError, OSError)` para Redis, `Exception` amplo apenas no top-level do feature flag (safe default).
5. **Logging**: Usar `structlog.get_logger(__name__)`. Eventos em `snake_case`. Incluir contexto relevante (feature, user_id, bucket).
6. **Testes async**: Usar `@pytest.mark.asyncio` para funções async. `asyncio_mode = "auto"` no pyproject.toml.
7. **Imports**: Standard lib → third-party → local (enforced by Ruff).

### Project Structure Notes

**Arquivos NOVOS:**
- `workflows/services/feature_flags.py` — Serviço de feature flags (~45 linhas)
- `workflows/migrations/0020_add_feature_flag_configs.py` — Data migration para configs
- `tests/test_services/test_feature_flags.py` — Testes do serviço (~15 testes)

**Arquivos MODIFICADOS:**
- `workflows/views.py` — Adicionar chamada a `is_feature_enabled()` no webhook handler
- `tests/test_views.py` — Testes de webhook com feature flag on/off

**Arquivos NÃO modificados:**
- `workflows/models.py` — Sem novos models (usa Config existente)
- `workflows/admin.py` — Sem mudanças (ConfigAdmin já gerencia feature flags via Config)
- `workflows/services/config_service.py` — Sem mudanças (feature flags usa via composição)
- `workflows/providers/redis.py` — Sem mudanças

### Dependências existentes (nenhuma nova)

| Pacote | Versão | Uso nesta story |
|--------|--------|-----------------|
| `hashlib` | stdlib Python 3.12 | MD5 para hash-based bucketing |
| `structlog` | 24.4+ | Logging estruturado — já instalado |
| `redis` (redis-py) | 5.2+ | Via ConfigService — já instalado |

### Decisões de design relevantes

- **Sem novo model FeatureFlag**: Reutilizar `Config` model existente com namespace `feature_flag:*`. O valor JSONField já suporta `rollout_percentage`. Criar um model separado seria over-engineering — o Config model + ConfigAdmin + audit trail + cache invalidation já fornecem tudo necessário.
- **Sem Django Admin customizado**: Feature flags aparecem na mesma lista do ConfigAdmin. A equipe já conhece essa interface. Filtragem por `key` busca `feature_flag:` facilmente.
- **Função standalone vs classe**: `is_feature_enabled()` é uma função async standalone, não uma classe. Sem estado, sem inicialização. Consistente com o padrão de `ConfigService.get()` (método estático).
- **`usedforsecurity=False` no MD5**: Requerido para compatibilidade FIPS. MD5 é usado para distribuição uniforme (não segurança criptográfica). Alternativa `hashlib.sha256` seria over-engineering para bucketing.
- **Integração no webhook (não no graph)**: A decisão de roteamento acontece ANTES de entrar no LangGraph pipeline, para evitar processamento desnecessário quando tráfego vai para n8n.

### Referências

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 10, Story 10.1, FR44-FR47]
- [Source: _bmad-output/planning-artifacts/architecture.md — Feature Flags: is_feature_enabled(), hash-based bucketing, Strangler Fig]
- [Source: _bmad-output/planning-artifacts/architecture.md — Config model: key/value/updated_by/updated_at]
- [Source: _bmad-output/planning-artifacts/architecture.md — ConfigService: Redis cache-aside, TTL 5min]
- [Source: _bmad-output/implementation-artifacts/8-1-config-service-aprimorado-hot-reload-redis-audit-trail.md — ConfigService implementation, audit trail, cache invalidation]
- [Source: _bmad-output/implementation-artifacts/8-2-system-prompt-versionado-historico-rollback.md — Admin patterns, async_to_sync, UniqueConstraint]
- [Source: workflows/services/config_service.py — ConfigService.get() com cache-aside Redis]
- [Source: workflows/models.py — Config model (linhas 46-56), ConfigHistory (linhas 115-127)]
- [Source: workflows/admin.py — ConfigAdmin com save_model override, ConfigHistoryInline]
- [Source: https://docs.python.org/3/library/hashlib.html — usedforsecurity=False para FIPS]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Migration renomeada de `0020` para `0021` devido a conflito com `0020_seed_system_prompt_v2_quiz` (Story 9.1)
- Testes existentes de webhook e graph precisaram de mock `is_feature_enabled` (return_value=True) para evitar regressão — feature flag retorna False por padrão quando config não existe

### Completion Notes List

- FeatureFlagService implementado como função async standalone (`is_feature_enabled`), sem estado, usando ConfigService para cache Redis
- Hash-based bucketing com MD5 (`usedforsecurity=False`), primeiros 8 hex chars (32 bits), `% 100` para distribuição uniforme
- Safe default `False` em todos os cenários de erro (config missing, Redis down, tipo inválido)
- Feature flag check integrado no webhook `post()` handler, após deduplicação e antes de qualquer dispatch
- Quando flag off, `continue` no loop → retorna 200 OK sem processar (n8n cuida)
- Data migration `0021` seed: `feature_flag:new_pipeline` e `feature_flag:shadow_mode` com `rollout_percentage: 0`
- 14 testes unitários do FeatureFlagService: determinismo, distribuição, boundaries (0%/100%), cache hit/miss, Redis down, config errors
- 4 testes de webhook routing: flag on/off, unsupported types, args validation
- Testes existentes atualizados com autouse fixture `_mock_feature_flag` (TestWhatsAppWebhookPost, TestUnsupportedMessageTypes, TestGraphWebhookIntegration)
- 778 testes passando (737 → 774 → 778 pós-review), ruff lint+format clean

### File List

**Arquivos NOVOS:**
- `workflows/services/feature_flags.py` — Serviço de feature flags com hash-based bucketing
- `workflows/migrations/0021_add_feature_flag_configs.py` — Data migration para configs iniciais
- `tests/test_services/test_feature_flags.py` — 14 testes unitários do FeatureFlagService

**Arquivos MODIFICADOS:**
- `workflows/views.py` — Import de `is_feature_enabled` + checagem de feature flag no webhook handler
- `tests/test_webhook.py` — 4 testes de routing + autouse fixture `_mock_feature_flag` em 2 classes existentes
- `tests/test_graph.py` — Mock de `is_feature_enabled` em `TestGraphWebhookIntegration`

### Senior Developer Review (AI)

**Reviewer:** Claude Opus 4.6 | **Date:** 2026-03-15 | **Outcome:** Approved (com fixes aplicados)

**Findings (8 total: 2 HIGH, 3 MEDIUM, 3 LOW) — todos corrigidos:**

| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| H1 | HIGH | Task 4.1 E2E test admin→cache→flag não existia | Novo teste `test_admin_save_cache_invalidation_flow` com Redis mock funcional |
| H2 | HIGH | Log `pipeline="new"` ausente no webhook (Task 3.4) | Adicionado `logger.info("feature_flag_routed", pipeline="new")` em views.py |
| M1 | MED | Hash truncado `[:8]` diverge da architecture (full hex) | Alterado para `int(hash_hex, 16) % 100` (Python lida com arbitrary precision) |
| M2 | MED | Sem log nos shortcircuits 0%/100% | Adicionado `feature_flag_evaluated` debug log em ambos caminhos |
| M3 | MED | Dev Notes diz migration 0020, real é 0021 | Tabela corrigida para `0020_seed_system_prompt_v2_quiz → 0021` |
| L1 | LOW | Redis mock duplicado 14x nos testes | Fixture `mock_redis_client` centralizada, ~40 linhas removidas |
| L2 | LOW | Float `rollout_percentage` sem validação | `int()` conversion adicionada antes do check |
| L3 | LOW | `except Exception` amplo mascara ValidationError | Split em `except ValidationError` + `except Exception` com logs distintos |

### Change Log

- **2026-03-15:** Implementação completa da Story 10.1 — Feature Flags + Roteamento Gradual de Tráfego. FeatureFlagService com hash-based bucketing, data migration, integração no webhook, 18 testes novos, 774 testes passando.
- **2026-03-15:** Code review — 8 findings corrigidos (2 HIGH, 3 MED, 3 LOW). Hash alinhado com architecture (full hex), logging completo, teste E2E de cache invalidation, fixture DRY, exception handling refinado. 778 testes passando.
