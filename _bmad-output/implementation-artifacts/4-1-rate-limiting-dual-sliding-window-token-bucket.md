# Story 4.1: Rate Limiting Dual — Sliding Window + Token Bucket

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a aluno,
I want saber quantas perguntas tenho disponíveis e ser protegido contra bloqueio imprevisível,
So that nunca sou surpreendido por um limite invisível.

## Acceptance Criteria

### AC1: Nó rate_limit — Sliding Window (Limite Diário por Tier)

```gherkin
Given o nó `rate_limit` do StateGraph recebe o estado com user_id e subscription_tier
When verifica limites do aluno
Then aplica sliding window via Redis (`ratelimit:daily:{user_id}`, TTL 24h) (FR23)
And limites diários são carregados do Config model por tier:
  - free: 10 perguntas/dia
  - basic: 100 perguntas/dia
  - premium: 1000 perguntas/dia
And o INCR + EXPIRE no Redis é atômico (pipeline ou Lua script) para evitar race conditions
And o campo `remaining_daily` é atualizado no estado com o número de perguntas restantes
And o campo `rate_limit_exceeded` é setado como False quando dentro do limite
```

### AC2: Aviso Quando Próximo do Limite Diário

```gherkin
Given o aluno está a 2 ou menos perguntas do limite diário
When o nó rate_limit calcula o remaining
Then o campo `rate_limit_warning` no estado é preenchido com:
  "⚠️ Você ainda tem {remaining} pergunta(s) disponível(is) hoje. Seu limite reseta amanhã às 00h."
And o aviso é adicionado ao final da resposta formatada pelo nó format_response (FR22)
And o threshold de aviso (2) é configurável via Config model (chave `rate_limit:warning_threshold`)
```

### AC3: Mensagem Quando Atingiu o Limite Diário

```gherkin
Given o aluno atingiu o limite diário (remaining_daily = 0)
When envia uma nova mensagem
Then o nó rate_limit seta `rate_limit_exceeded = True`
And o nó rate_limit envia mensagem diretamente via WhatsApp Cloud API:
  "Você atingiu seu limite de {limit} interações por hoje. Seu limite reseta amanhã às 00h. Até lá!"
And a mensagem de rate limit é configurável via Config model (chave `message:rate_limit_daily`)
And o grafo encerra via edge condicional → END (nenhum nó subsequente é executado)
And nenhuma chamada ao LLM é feita (economia de custo)
And o evento `rate_limit_exceeded` é logado via structlog com user_id, tier, daily_count
```

### AC4: Token Bucket — Anti-Burst

```gherkin
Given o aluno envia 5 mensagens em 3 segundos (burst)
When o nó rate_limit verifica o token bucket via Redis (`ratelimit:burst:{user_id}`, TTL 60s)
Then verifica se há tokens disponíveis no bucket (refill a cada 60 segundos)
And limites de burst por tier:
  - free: 2 tokens/min
  - basic: 5 tokens/min
  - premium: 10 tokens/min
And se tokens <= 0: seta `rate_limit_exceeded = True` e envia via WhatsApp:
  "Muitas mensagens em sequência. Aguarde 1 minuto."
And a mensagem de burst é configurável via Config model (chave `message:rate_limit_burst`)
And o burst check acontece ANTES do sliding window check (mais barato de verificar)
And o evento `burst_limit_exceeded` é logado via structlog
```

### AC5: Integração com Grafo — Edge Condicional

```gherkin
Given o nó rate_limit está inserido no StateGraph entre identify_user e load_context
When o nó rate_limit retorna o estado parcial
Then a função `check_rate_limit(state)` avalia `state["rate_limit_exceeded"]`
And se True → edge para END (pipeline encerra, aluno já recebeu mensagem de rate limit)
And se False → edge para load_context (pipeline continua normalmente)
And o grafo final é: START → identify_user → rate_limit → [condicional] → load_context → ...
```

## Tasks / Subtasks

- [x] Task 1: Criar `workflows/services/rate_limiter.py` — Serviço de rate limiting dual (AC: #1, #4)
  - [x] 1.1 Criar `workflows/services/rate_limiter.py`
  - [x] 1.2 Implementar classe `RateLimiter` com método `async check(user_id: str, tier: str) -> RateLimitResult`
  - [x] 1.3 Implementar `RateLimitResult` como TypedDict/dataclass: `allowed: bool`, `remaining_daily: int`, `daily_limit: int`, `reason: str`
  - [x] 1.4 Implementar sliding window: Redis INCR + EXPIRE atômico via pipeline (`ratelimit:daily:{user_id}`, TTL 86400s)
  - [x] 1.5 Implementar token bucket: Redis GET/DECR + EXPIRE (`ratelimit:burst:{user_id}`, TTL 60s, refill via TTL expiração)
  - [x] 1.6 Carregar limites por tier do Config model via `ConfigService.get(f"rate_limit:{tier}")`
  - [x] 1.7 Burst check ANTES do sliding window check (fail fast, mais barato)
  - [x] 1.8 Logar eventos via structlog: `rate_limit_checked`, `rate_limit_exceeded`, `burst_limit_exceeded`
  - [x] 1.9 Usar `_get_redis_client()` singleton de `workflows/utils/deduplication.py` (NÃO criar novo client)

- [x] Task 2: Criar `workflows/whatsapp/nodes/rate_limit.py` — Nó rate_limit do StateGraph (AC: #1, #2, #3, #4, #5)
  - [x] 2.1 Criar `workflows/whatsapp/nodes/rate_limit.py`
  - [x] 2.2 Implementar `async def rate_limit(state: WhatsAppState) -> dict` (LangGraph node contract)
  - [x] 2.3 Chamar `RateLimiter.check(state["user_id"], state["subscription_tier"])`
  - [x] 2.4 Se rate limit exceeded (daily ou burst): enviar mensagem via `send_text_message()` diretamente
  - [x] 2.5 Se daily exceeded: mensagem configurável de `ConfigService.get("message:rate_limit_daily")`
  - [x] 2.6 Se burst exceeded: mensagem configurável de `ConfigService.get("message:rate_limit_burst")`
  - [x] 2.7 Calcular warning: se remaining <= warning_threshold (de `ConfigService.get("rate_limit:warning_threshold")`)
  - [x] 2.8 Retornar dict parcial: `{"rate_limit_exceeded": bool, "remaining_daily": int, "rate_limit_warning": str}`
  - [x] 2.9 Em caso de erro Redis (fallback): permitir passagem (fail open) e logar WARNING

- [x] Task 3: Criar função `check_rate_limit()` para edge condicional (AC: #5)
  - [x] 3.1 Implementar `def check_rate_limit(state: WhatsAppState) -> str` em `graph.py` ou `rate_limit.py`
  - [x] 3.2 Retornar `"__end__"` (END) se `state["rate_limit_exceeded"] == True`
  - [x] 3.3 Retornar `"load_context"` se `state["rate_limit_exceeded"] == False`

- [x] Task 4: Atualizar `WhatsAppState` com campos de rate limiting (AC: #1, #2, #3)
  - [x] 4.1 Adicionar `rate_limit_exceeded: bool` ao WhatsAppState em `workflows/whatsapp/state.py`
  - [x] 4.2 Adicionar `remaining_daily: int` ao WhatsAppState
  - [x] 4.3 Adicionar `rate_limit_warning: str` ao WhatsAppState

- [x] Task 5: Atualizar `build_whatsapp_graph()` — Inserir nó rate_limit (AC: #5)
  - [x] 5.1 Importar `rate_limit` node e `check_rate_limit` em `workflows/whatsapp/graph.py`
  - [x] 5.2 Adicionar nó `"rate_limit"` ao StateGraph (sem RetryPolicy — rate limit é local/Redis, não serviço externo)
  - [x] 5.3 Alterar edge: `identify_user → rate_limit` (era `identify_user → load_context`)
  - [x] 5.4 Adicionar conditional edge: `rate_limit → check_rate_limit → {END, load_context}`
  - [x] 5.5 Remover edge direto: `identify_user → load_context`
  - [x] 5.6 Resetar singleton `_compiled_graph = None` (forçar recompilação)

- [x] Task 6: Atualizar `workflows/whatsapp/nodes/format_response.py` — Append warning (AC: #2)
  - [x] 6.1 Após formatação final, verificar se `state.get("rate_limit_warning")` tem conteúdo
  - [x] 6.2 Se sim, adicionar warning ao final do `formatted_response` com separação `\n\n`
  - [x] 6.3 Warning é adicionado ANTES do disclaimer médico (para não ficar perdido após o disclaimer)

- [x] Task 7: Atualizar `workflows/views.py` — Novos campos no initial_state (AC: #1)
  - [x] 7.1 Adicionar `"rate_limit_exceeded": False` ao initial_state
  - [x] 7.2 Adicionar `"remaining_daily": 0` ao initial_state
  - [x] 7.3 Adicionar `"rate_limit_warning": ""` ao initial_state

- [x] Task 8: Atualizar `workflows/whatsapp/nodes/__init__.py` — Export do nó rate_limit
  - [x] 8.1 Adicionar import e export de `rate_limit` do módulo

- [x] Task 9: Data migration — Atualizar configs de rate limit (AC: #1, #4)
  - [x] 9.1 Criar migration `0003_update_rate_limit_configs.py`
  - [x] 9.2 Atualizar `rate_limit:free` para `{"daily": 10, "burst": 2}`
  - [x] 9.3 Criar `rate_limit:basic` com `{"daily": 100, "burst": 5}`
  - [x] 9.4 Atualizar `rate_limit:premium` para `{"daily": 1000, "burst": 10}`
  - [x] 9.5 Criar `rate_limit:warning_threshold` com valor `2`
  - [x] 9.6 Criar `message:rate_limit_daily` com mensagem configurável
  - [x] 9.7 Criar `message:rate_limit_burst` com mensagem configurável
  - [x] 9.8 Atualizar `message:rate_limit` existente (manter para backward compatibility ou remover)

- [x] Task 10: Testes (TODOS os ACs)
  - [x] 10.1 Criar `tests/test_services/test_rate_limiter.py`
  - [x] 10.2 Teste: check() retorna allowed=True quando dentro do limite diário (AC1)
  - [x] 10.3 Teste: check() retorna allowed=False quando limite diário excedido (AC1)
  - [x] 10.4 Teste: check() retorna remaining correto (AC1)
  - [x] 10.5 Teste: check() retorna allowed=False quando burst excedido (AC4)
  - [x] 10.6 Teste: burst check executado antes de sliding window (AC4)
  - [x] 10.7 Teste: limites carregados do ConfigService por tier (AC1)
  - [x] 10.8 Teste: Redis failure → fail open (allowed=True) (fallback)
  - [x] 10.9 Criar `tests/test_whatsapp/test_nodes/test_rate_limit.py`
  - [x] 10.10 Teste: nó rate_limit retorna rate_limit_exceeded=False quando dentro do limite (AC1)
  - [x] 10.11 Teste: nó rate_limit retorna rate_limit_exceeded=True e envia mensagem quando limite excedido (AC3)
  - [x] 10.12 Teste: nó rate_limit retorna rate_limit_warning quando próximo do limite (AC2)
  - [x] 10.13 Teste: nó rate_limit envia mensagem de burst quando token bucket vazio (AC4)
  - [x] 10.14 Teste: check_rate_limit() retorna END quando exceeded (AC5)
  - [x] 10.15 Teste: check_rate_limit() retorna "load_context" quando allowed (AC5)
  - [x] 10.16 Atualizar `tests/test_graph.py`
  - [x] 10.17 Teste: grafo executa flow completo com rate_limit node (allowed) — 7 nós
  - [x] 10.18 Teste: grafo encerra no rate_limit quando exceeded — identify_user → rate_limit → END
  - [x] 10.19 Teste: format_response append warning quando rate_limit_warning preenchido (AC2)

## Dev Notes

### Contexto de Negócio
- Story 4.1 é a **única story do Epic 4** — implementa rate limiting transparente para o aluno.
- O aluno NUNCA deve ser surpreendido por um limite invisível. Se está perto do limite, recebe aviso. Se atingiu, recebe mensagem clara com quando reseta.
- Rate limiting tem 2 propósitos: **proteção contra abuso** (token bucket anti-burst) e **controle de custos** (sliding window diário).
- Quando rate limited, **NENHUMA chamada ao LLM é feita** — economia direta de custo.
- O nó rate_limit envia a mensagem de rate limit **diretamente** via WhatsApp (não passa pelo pipeline format_response → send_whatsapp) porque o pipeline é encerrado.

### Padrões Obrigatórios (Estabelecidos nas Stories 1.1-1.5)
- **SEMPRE** async/await para I/O (NUNCA bloqueante)
- **Django ORM async**: `aget()`, `acreate()` — `afilter()` NÃO existe, usar `.filter()` com async iteration
- **Type hints** em TODAS as funções
- **structlog** para logging (NUNCA `print()`)
- **AppError hierarchy** para exceções (usar `RateLimitError` para falhas de rate limit)
- **Import order**: Standard → Third-party → Local
- **NUNCA** `import *`, sync I/O, commitar secrets, logar PII sem sanitização
- **Nomes**: snake_case (arquivos, funções, variáveis), PascalCase (classes), UPPER_SNAKE_CASE (constantes)
- **LangGraph node contract**: funções async puras → `async def node_name(state: WhatsAppState) -> dict`
- **Retorno parcial**: nós SEMPRE retornam `dict` parcial (apenas campos alterados), NUNCA o estado completo
- **RetryPolicy**: usar `retry_policy=RetryPolicy(...)` (NÃO `retry=` — deprecado no LangGraph 1.0.10)
- **Singleton Redis**: usar `_get_redis_client()` de `workflows/utils/deduplication.py` (NUNCA criar novo client)

### Infraestrutura Já Disponível (Stories 1.1-1.5 — NÃO RECRIAR)
- `workflows/models.py` — User (phone, subscription_tier), Message, Config, ConfigHistory
- `workflows/utils/errors.py` — AppError hierarchy incluindo `RateLimitError(message, retry_after, details)`
- `workflows/utils/deduplication.py` — `_get_redis_client()` singleton Redis async
- `workflows/services/config_service.py` — `ConfigService.get(key)` async (busca Config via Django ORM)
- `workflows/services/cache_manager.py` — CacheManager (session cache Redis, TTL 1h)
- `workflows/providers/whatsapp.py` — `send_text_message(phone, text)` async, `mark_as_read(wamid)` async
- `workflows/whatsapp/state.py` — WhatsAppState TypedDict (17 campos atuais, `add_messages` reducer)
- `workflows/whatsapp/graph.py` — `build_whatsapp_graph()` (6 nós: identify_user → load_context → orchestrate_llm → format_response → send_whatsapp → persist)
- `workflows/whatsapp/nodes/identify_user.py` — Retorna `{"user_id": str, "subscription_tier": str}`
- `workflows/whatsapp/nodes/format_response.py` — Pipeline de formatação (validate_citations, strip_competitor, markdown_to_whatsapp, disclaimer, split)
- `workflows/views.py` — WhatsAppWebhookView, `_process_message()` com initial_state
- `workflows/migrations/0002_initial_configs.py` — Configs iniciais (rate_limit:free, rate_limit:premium, message:rate_limit, etc.)
- 188 testes passando (Stories 1.1-1.5)

### Inteligência das Stories Anteriores (1.1-1.5)

**Lições aprendidas:**
- `ChatAnthropicVertex` foi unificado em `ChatVertexAI` no langchain-google-vertexai 3.2.2 — irrelevante para esta story mas manter awareness
- `retry=` está deprecado em `add_node()` — usar `retry_policy=RetryPolicy(...)`
- `MagicMock()` como checkpointer falha isinstance — usar `InMemorySaver()` em testes
- Django `AsyncClient` em testes: usar `headers={}` dict em vez de `HTTP_*` kwargs
- Redis precisa de connection pooling (singleton) — já implementado em `deduplication.py`
- `afilter()` NÃO existe no Django ORM — usar `.filter()` com `async for`
- `@pytest.mark.django_db` requer `transaction=True` para isolamento com campos unique
- httpx.Response mock: `MagicMock(spec=httpx.Response)` para métodos síncronos `.json()`/`.raise_for_status()`
- Singleton `_compiled_graph` precisa ser None para recompilar ao adicionar nós em testes

**Padrões de código estabelecidos:**
- Nós LangGraph: `async def node_name(state: WhatsAppState) -> dict` retornando dict parcial
- Testes: `@pytest.mark.django_db(transaction=True)` + mocks com `AsyncMock`
- Singleton: `_compiled_graph`, `_model_cache`, `_checkpointer`, `_redis_client`
- Graph: `get_graph()` async singleton via `build_whatsapp_graph().compile()`
- Provider WhatsApp: `send_text_message(phone, text)` já testado e funcional

**Code Review Fixes da Story 1.5 (relevantes):**
- RetryPolicy do send_whatsapp era ineficaz porque `except Exception` capturava tudo — reestruturado para propagar ExternalServiceError
- Regex de concorrentes recompilados a cada chamada — pré-compilados como constantes de módulo → **aplicar mesmo padrão** no rate_limiter se houver regex
- persist capturava todos os erros silenciosamente — agora só captura DatabaseError/DoesNotExist → **rate_limit node: não capturar tudo, fail open em Redis errors**

### Project Structure Notes

#### Arquivos a Criar
```
workflows/
├── services/
│   └── rate_limiter.py            # CRIAR — RateLimiter class (sliding window + token bucket)
└── whatsapp/
    └── nodes/
        └── rate_limit.py          # CRIAR — Nó rate_limit do StateGraph

tests/
├── test_services/
│   └── test_rate_limiter.py       # CRIAR — Testes do RateLimiter service
└── test_whatsapp/
    └── test_nodes/
        └── test_rate_limit.py     # CRIAR — Testes do nó rate_limit
```

#### Arquivos a Modificar
```
workflows/
├── whatsapp/
│   ├── graph.py                   # MODIFICAR — Adicionar nó rate_limit + conditional edge
│   ├── state.py                   # MODIFICAR — Adicionar rate_limit_exceeded, remaining_daily, rate_limit_warning
│   └── nodes/
│       ├── __init__.py            # MODIFICAR — Exportar rate_limit
│       └── format_response.py    # MODIFICAR — Append rate_limit_warning à resposta
├── views.py                       # MODIFICAR — Adicionar novos campos ao initial_state

workflows/migrations/
└── 0003_update_rate_limit_configs.py  # CRIAR — Migration para atualizar configs

tests/
└── test_graph.py                  # MODIFICAR — Testar flow com rate_limit node
```

### Guardrails de Arquitetura

#### ADRs Aplicáveis
| ADR | Decisão | Impacto nesta Story |
|-----|---------|---------------------|
| ADR-003 | Django ORM (não supabase-py) | Config.objects.aget() para carregar limites |
| ADR-007 | Redis 4 camadas (Upstash) | Camada 4: Rate Limiting (`ratelimit:daily:{user_id}`, `ratelimit:burst:{user_id}`) |
| ADR-008 | Segurança 6 camadas | Camada 3: Rate Limiting dual (sliding + token bucket) |
| ADR-009 | App `workflows/` | Service em `workflows/services/`, nó em `workflows/whatsapp/nodes/` |
| ADR-010 | LangGraph + LangChain 1.0 | StateGraph node com edge condicional, sem RetryPolicy (Redis local) |

#### Requisitos Não-Funcionais (NFR)
| NFR | Requisito | Como Implementar |
|-----|-----------|------------------|
| NFR5 | Debounce ≤ 3s | Rate limit check acontece APÓS debounce (Story 1.6) — sem conflito |
| NFR13 | Nenhuma mensagem perdida | Aluno SEMPRE recebe mensagem (rate limit ou resposta normal) |
| NFR21 | Timeout configurável por serviço | Redis timeout padrão do singleton (não configurável separado) |

### Libraries/Frameworks — Versões e Padrões Atualizados

| Lib | Versão | Uso nesta Story | Notas Importantes |
|-----|--------|----------------|-------------------|
| redis-py | 5.2+ | Rate limiting (INCR, EXPIRE, GET, DECR, pipeline) | Import: `import redis.asyncio as aioredis`. Usar pipeline para atomicidade INCR+EXPIRE |
| langgraph | 1.0.10 | StateGraph, add_conditional_edges | `add_conditional_edges("rate_limit", check_rate_limit)` |
| structlog | 24.4+ | Logging em rate_limit node e service | Import: `import structlog; logger = structlog.get_logger(__name__)` |
| django | 5.1+ | Config.objects.aget() para limites | Async ORM para buscar configs |

### Informações Técnicas Atualizadas (Pesquisa Web — Mar 2026)

#### Redis Rate Limiting — Atomicidade com Pipeline

```python
# PROBLEMA: INCR + EXPIRE separados têm race condition
# Se o processo morre entre INCR e EXPIRE, a key nunca expira

# SOLUÇÃO: Usar Redis pipeline para atomicidade
async def atomic_incr_with_expire(redis_client, key: str, ttl: int) -> int:
    """Incrementa key e seta TTL atomicamente via pipeline."""
    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.expire(key, ttl)
        results = await pipe.execute()
        return results[0]  # resultado do INCR
```

#### Redis Token Bucket — Padrão Simplificado

```python
# Token bucket via Redis: usa TTL como mecanismo de refill
# Quando o key expira, tokens são "recarregados" (key não existe = bucket cheio)

async def check_token_bucket(redis_client, key: str, max_tokens: int, ttl: int) -> bool:
    """Verifica e consome um token. Retorna True se permitido."""
    tokens = await redis_client.get(key)

    if tokens is None:
        # Key expirou ou nunca existiu — bucket cheio
        # Setar para max_tokens - 1 (consumindo 1 token)
        await redis_client.set(key, max_tokens - 1, ex=ttl)
        return True

    tokens = int(tokens)
    if tokens <= 0:
        return False  # Sem tokens

    await redis_client.decr(key)
    return True
```

#### LangGraph Conditional Edges — Padrão

```python
from langgraph.graph import END

def check_rate_limit(state: WhatsAppState) -> str:
    """Decide se o pipeline continua ou encerra após rate limit check."""
    if state.get("rate_limit_exceeded", False):
        return END  # "__end__"
    return "load_context"

# No graph builder:
builder.add_conditional_edges("rate_limit", check_rate_limit)
```

#### RateLimiter Service — Padrão Completo

```python
# workflows/services/rate_limiter.py
from dataclasses import dataclass
import structlog
from workflows.utils.deduplication import _get_redis_client
from workflows.services.config_service import ConfigService

logger = structlog.get_logger(__name__)

@dataclass
class RateLimitResult:
    allowed: bool
    remaining_daily: int
    daily_limit: int
    reason: str  # "" se allowed, "daily_exceeded" ou "burst_exceeded"

class RateLimiter:
    @staticmethod
    async def check(user_id: str, tier: str) -> RateLimitResult:
        """Verifica rate limit dual: burst (token bucket) + daily (sliding window)."""
        redis = _get_redis_client()

        try:
            # Carregar limites do Config
            config = await ConfigService.get(f"rate_limit:{tier}")
            daily_limit = config["daily"]
            burst_limit = config["burst"]
        except Exception:
            logger.warning("rate_limit_config_fallback", tier=tier)
            # Fallback hardcoded se Config indisponível
            daily_limit = 10
            burst_limit = 2

        try:
            # 1. Burst check PRIMEIRO (mais barato, fail fast)
            burst_key = f"ratelimit:burst:{user_id}"
            tokens = await redis.get(burst_key)

            if tokens is None:
                # Bucket cheio — consumir 1 token
                await redis.set(burst_key, burst_limit - 1, ex=60)
            else:
                tokens = int(tokens)
                if tokens <= 0:
                    logger.info("burst_limit_exceeded", user_id=user_id, tier=tier)
                    return RateLimitResult(
                        allowed=False,
                        remaining_daily=0,  # Não verificado
                        daily_limit=daily_limit,
                        reason="burst_exceeded",
                    )
                await redis.decr(burst_key)

            # 2. Sliding window (daily limit)
            daily_key = f"ratelimit:daily:{user_id}"
            async with redis.pipeline(transaction=True) as pipe:
                pipe.incr(daily_key)
                pipe.expire(daily_key, 86400)
                results = await pipe.execute()
                daily_count = results[0]

            remaining = max(0, daily_limit - daily_count)

            if daily_count > daily_limit:
                logger.info(
                    "rate_limit_exceeded",
                    user_id=user_id,
                    tier=tier,
                    daily_count=daily_count,
                    daily_limit=daily_limit,
                )
                return RateLimitResult(
                    allowed=False,
                    remaining_daily=0,
                    daily_limit=daily_limit,
                    reason="daily_exceeded",
                )

            logger.debug(
                "rate_limit_checked",
                user_id=user_id,
                tier=tier,
                remaining=remaining,
            )
            return RateLimitResult(
                allowed=True,
                remaining_daily=remaining,
                daily_limit=daily_limit,
                reason="",
            )

        except Exception:
            # Fail open — se Redis falhar, permitir passagem
            logger.exception("rate_limit_redis_error", user_id=user_id)
            return RateLimitResult(
                allowed=True,
                remaining_daily=daily_limit,
                daily_limit=daily_limit,
                reason="",
            )
```

#### rate_limit Node — Padrão Completo

```python
# workflows/whatsapp/nodes/rate_limit.py
import structlog
from workflows.providers.whatsapp import send_text_message
from workflows.services.config_service import ConfigService
from workflows.services.rate_limiter import RateLimiter
from workflows.whatsapp.state import WhatsAppState

logger = structlog.get_logger(__name__)

DEFAULT_DAILY_MESSAGE = (
    "Você atingiu seu limite de {limit} interações por hoje. "
    "Seu limite reseta amanhã às 00h. Até lá!"
)
DEFAULT_BURST_MESSAGE = "Muitas mensagens em sequência. Aguarde 1 minuto."
DEFAULT_WARNING_THRESHOLD = 2

async def rate_limit(state: WhatsAppState) -> dict:
    """Check rate limits and block or warn the user."""
    user_id = state["user_id"]
    tier = state["subscription_tier"]
    phone = state["phone_number"]

    result = await RateLimiter.check(user_id, tier)

    if not result.allowed:
        # Enviar mensagem de rate limit diretamente (pipeline encerra)
        if result.reason == "burst_exceeded":
            try:
                msg = await ConfigService.get("message:rate_limit_burst")
            except Exception:
                msg = DEFAULT_BURST_MESSAGE
        else:
            try:
                msg = await ConfigService.get("message:rate_limit_daily")
            except Exception:
                msg = DEFAULT_DAILY_MESSAGE
            msg = msg.format(limit=result.daily_limit)

        try:
            await send_text_message(phone, msg)
        except Exception:
            logger.exception("rate_limit_message_send_failed", phone=phone)

        return {
            "rate_limit_exceeded": True,
            "remaining_daily": 0,
            "rate_limit_warning": "",
        }

    # Calcular warning
    warning = ""
    try:
        threshold = await ConfigService.get("rate_limit:warning_threshold")
    except Exception:
        threshold = DEFAULT_WARNING_THRESHOLD

    if result.remaining_daily <= threshold:
        s = "s" if result.remaining_daily != 1 else ""
        warning = (
            f"⚠️ Você ainda tem {result.remaining_daily} pergunta{s} "
            f"disponível(is) hoje. Seu limite reseta amanhã às 00h."
        )

    return {
        "rate_limit_exceeded": False,
        "remaining_daily": result.remaining_daily,
        "rate_limit_warning": warning,
    }
```

#### Pitfalls Conhecidos (Story 4.1)

1. **INCR + EXPIRE race condition** — Se processo morre entre INCR e EXPIRE, key nunca expira (memory leak no Redis). SEMPRE usar pipeline atômico.
2. **Token bucket refill via TTL** — Quando o key expira, bucket é considerado cheio. Não usar INCR para refill (complicação desnecessária). TTL de 60s = refill a cada 1 minuto.
3. **Fail open em Redis errors** — Se Redis estiver indisponível, PERMITIR a mensagem (não bloquear o aluno). Logar WARNING e continuar. Rate limiting é proteção, não bloqueio.
4. **Config fallback** — Se ConfigService falhar (DB down), usar limites hardcoded como fallback (free: 10 daily, 2 burst).
5. **Envio direto via WhatsApp** — O nó rate_limit envia a mensagem de rate limit DIRETAMENTE via `send_text_message()`, não via pipeline format_response → send_whatsapp. Isso porque o pipeline é encerrado (edge → END).
6. **Mensagem de rate limit NÃO passa pelo format_response** — Portanto NÃO aplica markdown_to_whatsapp, disclaimer, split. As mensagens de rate limit são curtas e em texto puro — não precisam de formatação.
7. **Warning append em format_response** — O `rate_limit_warning` é adicionado ao FINAL da resposta formatada, ANTES do disclaimer médico. Se a resposta já é longa (> 4096), o warning vai na última parte do split.
8. **Singleton _compiled_graph** — Ao adicionar o nó rate_limit ao graph.py, o singleton precisa ser resetado. Em testes, usar `build_whatsapp_graph()` diretamente sem o singleton.
9. **Edge condicional vs edge normal** — Ao usar `add_conditional_edges("rate_limit", check_rate_limit)`, NÃO adicionar edge normal `add_edge("rate_limit", "load_context")`. O conditional edge já cobre ambos os caminhos.
10. **Burst antes de daily** — Verificar burst ANTES de daily porque é mais barato (1 GET vs INCR+EXPIRE pipeline). Se burst falhar, não gasta o daily counter.
11. **daily_count > daily_limit** — Usar `>` (não `>=`) porque INCR retorna o valor APÓS incremento. Se limit=10, count=10 é a 10a mensagem (permitida), count=11 é a 11a (bloqueada).
12. **ConfigService.get() pode retornar string** — A migration vai configurar valores como dict/int. Verificar tipo retornado e converter se necessário.

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 4, Story 4.1]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-007 Cache e Rate Limiting (Redis 4 camadas)]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-008 Security Architecture (Camada 3: Rate Limiting)]
- [Source: _bmad-output/planning-artifacts/architecture.md — StateGraph flow (rate_limit node com edge condicional)]
- [Source: _bmad-output/planning-artifacts/architecture.md — RateLimiter class pattern (sliding window + token bucket)]
- [Source: _bmad-output/planning-artifacts/architecture.md — CacheManager.check_rate_limit() reference implementation]
- [Source: _bmad-output/planning-artifacts/architecture.md — Enforcement Rules (MUST/MUST NOT)]
- [Source: _bmad-output/planning-artifacts/architecture.md — File structure (rate_limiter.py, rate_limit.py)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Error hierarchy (RateLimitError)]
- [Source: _bmad-output/planning-artifacts/prd.md — FR22 (visualizar perguntas restantes), FR23 (limitar interações), FR24 (anti-burst)]
- [Source: _bmad-output/planning-artifacts/prd.md — NFR5 (debounce ≤ 3s), NFR13 (zero mensagens perdidas)]
- [Source: _bmad-output/implementation-artifacts/1-5-formatacao-envio-whatsapp-persistencia.md — Dev Notes, Lessons Learned, Code Review Fixes]
- [Source: workflows/utils/deduplication.py — _get_redis_client() singleton]
- [Source: workflows/services/config_service.py — ConfigService.get(key)]
- [Source: workflows/whatsapp/graph.py — build_whatsapp_graph() current flow]
- [Source: workflows/whatsapp/state.py — WhatsAppState current fields]
- [Source: workflows/views.py — _process_message() initial_state]
- [Source: workflows/migrations/0002_initial_configs.py — Current rate_limit configs]
- [Source: Web — Redis rate limiting best practices: atomic INCR+EXPIRE via pipeline]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

Nenhum debug log necessário — implementação seguiu padrões da Dev Notes sem bloqueios.

### Completion Notes List

- **Task 1-3:** Criados `RateLimiter` service (sliding window + token bucket), nó `rate_limit`, e `check_rate_limit()` edge function. Padrão: burst check antes de daily (fail fast), INCR+EXPIRE atômico via pipeline, fail open em Redis errors.
- **Task 4:** Adicionados 3 campos ao `WhatsAppState`: `rate_limit_exceeded`, `remaining_daily`, `rate_limit_warning`.
- **Task 5:** Grafo atualizado: `identify_user → rate_limit → [conditional] → load_context → ...`. Sem RetryPolicy no rate_limit (Redis local).
- **Task 6:** `format_response` agora appenda `rate_limit_warning` ao final da resposta (após disclaimer, antes do split).
- **Task 7:** `initial_state` em `views.py` atualizado com novos campos (defaults: False, 0, "").
- **Task 8:** `__init__.py` exporta `rate_limit` e `check_rate_limit`.
- **Task 9:** Migration `0004_rate_limit_configs.py` — atualiza rate_limit:free/premium para formato daily/burst, cria rate_limit:basic, warning_threshold, mensagens configuráveis.
- **Task 10:** 17 novos testes: 8 unit (RateLimiter service), 6 unit (rate_limit node + edge), 1 integration (grafo com rate_limit exceeded → END), 2 format_response (warning append).
- **Resultados:** 217 passed, 6 failed (pré-existentes em test_debounce.py — Story 1.6, não relacionados).

### File List

**Criados:**
- `workflows/services/rate_limiter.py` — RateLimiter class (sliding window + token bucket)
- `workflows/whatsapp/nodes/rate_limit.py` — Nó rate_limit + check_rate_limit() edge
- `workflows/migrations/0004_rate_limit_configs.py` — Data migration para configs de rate limit
- `tests/test_services/test_rate_limiter.py` — 8 testes do RateLimiter service
- `tests/test_whatsapp/test_nodes/test_rate_limit.py` — 8 testes do nó rate_limit (+2 edge cases da review)

**Modificados:**
- `workflows/whatsapp/state.py` — +3 campos: rate_limit_exceeded, remaining_daily, rate_limit_warning
- `workflows/whatsapp/graph.py` — +rate_limit node, +conditional edge, flow atualizado (7 nós)
- `workflows/whatsapp/nodes/__init__.py` — +exports rate_limit, check_rate_limit
- `workflows/whatsapp/nodes/format_response.py` — +append rate_limit_warning
- `workflows/views.py` — +3 campos no initial_state
- `tests/test_graph.py` — +rate_limit mocks nos testes existentes, +1 novo teste (exceeded → END)
- `tests/test_whatsapp/test_nodes/test_format_response.py` — +2 testes (warning append)

## Change Log

- **2026-03-08:** Story 4.1 implementada — Rate limiting dual (sliding window + token bucket) com integração no StateGraph, mensagens configuráveis, warning de proximidade ao limite, e 17 novos testes.
- **2026-03-08:** Code Review (Claude Opus 4.6) — 9 issues encontrados (3 HIGH, 3 MEDIUM, 3 LOW), todos corrigidos:
  - H1: Token bucket race condition corrigida via Lua script atômico (rate_limiter.py)
  - H2: Warning reposicionado ANTES do disclaimer em format_response.py (conforme spec)
  - H3: PII (phone) sanitizado nos logs de rate_limit.py (phone_suffix)
  - M3: +2 testes edge case para warning (remaining=0, remaining=1)
  - L1: _make_state() de test_format_response.py completado com campos faltantes
  - L3: Mensagem "última pergunta" para remaining=0 (UX melhorada)
  - 44 testes passando (0 falhas nos arquivos da story)
