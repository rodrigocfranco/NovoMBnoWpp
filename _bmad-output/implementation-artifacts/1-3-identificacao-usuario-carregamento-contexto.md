# Story 1.3: Identificação de Usuário + Carregamento de Contexto

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a aluno Medway ou não-aluno,
I want ser identificado automaticamente pelo meu número de telefone,
So that recebo experiência personalizada conforme meu tipo de usuário.

## Acceptance Criteria

### AC1: Identificação de Usuário Existente

```gherkin
Given uma mensagem de um número de telefone cadastrado como aluno Medway
When o nó `identify_user` do StateGraph processa o estado
Then o sistema busca o User via Django ORM async (`User.objects.aget(phone=phone)`)
And retorna `user_id` e `subscription_tier` no estado
And o resultado é cacheado no Redis (`session:{user_id}`, TTL 1h)
```

### AC2: Novo Usuário (Número Desconhecido)

```gherkin
Given uma mensagem de um número desconhecido
When o nó `identify_user` processa
Then o sistema cria um novo User com `subscription_tier="free"` via `User.objects.acreate()`
And retorna o novo user no estado
And o resultado é cacheado no Redis (`session:{user_id}`, TTL 1h)
```

### AC3: Carregamento de Contexto de Conversa

```gherkin
Given um User já identificado
When o nó `load_context` processa
Then o sistema verifica cache Redis antes do banco (session cache)
And carrega as últimas 20 mensagens via Django ORM async (`Message.objects.filter(user=user).order_by("-created_at")[:20]`)
And formata como LangChain messages (HumanMessage, AIMessage) para o contexto do LLM
And cacheia o resultado no Redis (`session:{user_id}`, TTL 1h)
```

### AC4: WhatsAppState Schema Definido

```gherkin
Given o arquivo `workflows/whatsapp/state.py`
When definido
Then contém `WhatsAppState(TypedDict)` com todos os campos necessários para o pipeline
And usa `Annotated[list[AnyMessage], add_messages]` para acumulação de mensagens
And define campos para input (phone_number, user_message, message_type, wamid), identificação (user_id, subscription_tier), contexto (messages) e output
```

### AC5: Integração com Webhook (Graph Dispatch)

```gherkin
Given a função `_process_message()` em `workflows/views.py`
When atualizada para usar o grafo
Then invoca o StateGraph compilado com os dados da mensagem validada
And usa `thread_id = phone_number` para identificar a sessão
And loga `graph_execution_started` e `graph_execution_completed` via structlog
```

## Tasks / Subtasks

- [x] Task 1: Criar `WhatsAppState` TypedDict (AC: #4)
  - [x] 1.1 Criar `workflows/whatsapp/state.py` com `WhatsAppState(TypedDict)`
  - [x] 1.2 Definir campos de input: `phone_number`, `user_message`, `message_type`, `media_url`, `wamid`
  - [x] 1.3 Definir campos de identificação: `user_id`, `subscription_tier`
  - [x] 1.4 Definir campo de contexto: `messages: Annotated[list[AnyMessage], add_messages]`
  - [x] 1.5 Definir campos de output (placeholder): `formatted_response`, `response_sent`
  - [x] 1.6 Definir campos de observabilidade: `trace_id`, `cost_usd`
  - [x] 1.7 Definir campos de citação (placeholder): `retrieved_sources`, `cited_source_indices`, `web_sources`
  - [x] 1.8 Definir campo `transcribed_text` (placeholder para Story 3.1)

- [x] Task 2: Criar `CacheManager` para Session Cache (AC: #1, #2, #3)
  - [x] 2.1 Criar `workflows/services/cache_manager.py`
  - [x] 2.2 Reusar o padrão singleton de Redis de `workflows/utils/deduplication.py` (`_get_redis_client()`)
  - [x] 2.3 Implementar `cache_session(user_id, data)` com key `session:{user_id}`, TTL 1h
  - [x] 2.4 Implementar `get_session(user_id)` que retorna dados ou None
  - [x] 2.5 Implementar `invalidate_session(user_id)` para remover cache
  - [x] 2.6 Usar `json.dumps()`/`json.loads()` para serialização

- [x] Task 3: Criar nó `identify_user` (AC: #1, #2)
  - [x] 3.1 Criar `workflows/whatsapp/nodes/identify_user.py`
  - [x] 3.2 Implementar `async def identify_user(state: WhatsAppState) -> dict` seguindo node contract
  - [x] 3.3 Verificar cache Redis (`session:{phone}`) antes do banco
  - [x] 3.4 Buscar User via `User.objects.aget(phone=phone)` (async)
  - [x] 3.5 Se `User.DoesNotExist` → `User.objects.acreate(phone=phone, subscription_tier="free")`
  - [x] 3.6 Cachear resultado no Redis com TTL 1h
  - [x] 3.7 Retornar dict parcial: `{"user_id": str(user.id), "subscription_tier": user.subscription_tier}`
  - [x] 3.8 Logar `user_identified` ou `user_created` via structlog

- [x] Task 4: Criar nó `load_context` (AC: #3)
  - [x] 4.1 Criar `workflows/whatsapp/nodes/load_context.py`
  - [x] 4.2 Implementar `async def load_context(state: WhatsAppState) -> dict` seguindo node contract
  - [x] 4.3 Verificar cache Redis (`session:{user_id}:messages`) antes do banco
  - [x] 4.4 Buscar últimas 20 mensagens: `Message.objects.filter(user_id=user_id).order_by("-created_at")[:20]`
  - [x] 4.5 Usar async iteration: `[msg async for msg in queryset]`
  - [x] 4.6 Converter para LangChain messages: `HumanMessage` (role="user"), `AIMessage` (role="assistant")
  - [x] 4.7 Inverter ordem (oldest first) para contexto cronológico do LLM
  - [x] 4.8 Cachear resultado no Redis com TTL 1h
  - [x] 4.9 Retornar dict parcial: `{"messages": langchain_messages}`
  - [x] 4.10 Logar `context_loaded` com `message_count` via structlog

- [x] Task 5: Criar `build_whatsapp_graph()` inicial (AC: #5)
  - [x] 5.1 Implementar `workflows/whatsapp/graph.py` com `build_whatsapp_graph()`
  - [x] 5.2 Criar `StateGraph(WhatsAppState)` com nós: `identify_user` → `load_context` → END
  - [x] 5.3 Adicionar edges: `START → identify_user → load_context → END`
  - [x] 5.4 Compilar o grafo: `graph = builder.compile()`
  - [x] 5.5 Exportar função `get_graph()` que retorna o grafo compilado (singleton)
  - [x] 5.6 Nota: Story 1.4 adicionará `orchestrate_llm` e checkpointer

- [x] Task 6: Integrar grafo no webhook (AC: #5)
  - [x] 6.1 Atualizar `_process_message()` em `workflows/views.py`
  - [x] 6.2 Importar e invocar o grafo: `await graph.ainvoke(initial_state, config={"configurable": {"thread_id": phone}})`
  - [x] 6.3 Construir `initial_state` a partir dos dados validados do webhook
  - [x] 6.4 Logar `graph_execution_started` e `graph_execution_completed`
  - [x] 6.5 Tratar exceções com `GraphNodeError` e log de erro

- [x] Task 7: Testes (TODOS os ACs)
  - [x] 7.1 Criar `tests/test_identify_user.py`
  - [x] 7.2 Teste: usuário existente → retorna user_id e subscription_tier corretos (AC1)
  - [x] 7.3 Teste: usuário novo → cria com tier="free" e retorna dados (AC2)
  - [x] 7.4 Teste: cache hit → não consulta banco (AC1)
  - [x] 7.5 Teste: cache miss → consulta banco e popula cache (AC1)
  - [x] 7.6 Criar `tests/test_load_context.py`
  - [x] 7.7 Teste: carrega últimas 20 mensagens ordenadas cronologicamente (AC3)
  - [x] 7.8 Teste: formata corretamente como HumanMessage/AIMessage (AC3)
  - [x] 7.9 Teste: cache hit retorna mensagens sem query ao banco (AC3)
  - [x] 7.10 Teste: usuário sem mensagens retorna lista vazia (AC3)
  - [x] 7.11 Criar `tests/test_state.py`
  - [x] 7.12 Teste: WhatsAppState aceita todos os campos definidos (AC4)
  - [x] 7.13 Criar `tests/test_graph.py`
  - [x] 7.14 Teste: grafo executa identify_user → load_context → END com estado completo (AC5)
  - [x] 7.15 Teste: grafo integrado com webhook processa mensagem corretamente (AC5)

## Dev Notes

### Contexto de Negócio
- Story 1.3 define a **identificação de usuários** e o **carregamento de contexto de conversa** — pré-requisitos para o LLM responder de forma personalizada
- A identificação por telefone é o mecanismo primário; `medway_id` será usado em futuras integrações com API Medway (timeout 8s, 3x retry, fallback: guest access)
- O `subscription_tier` (free/basic/premium) será usado no nó `rate_limit` (Story 4.1) para aplicar limites diferenciados
- **ATENÇÃO BSUID:** A partir de junho 2026, a Meta pode introduzir BSUID (Business-Scoped User ID) que substitui phone numbers. Para esta story, implementar normalmente com phone. Considerar adicionar campo `bsuid` no User model como preparação futura
- Esta story cria as bases do LangGraph StateGraph que será expandido nas Stories 1.4 (LLM), 1.5 (formatação) e 1.6 (debounce)

### Padrões Obrigatórios (Estabelecidos na Story 1.1 e 1.2)
- **SEMPRE** async/await para I/O (NUNCA bloqueante)
- **Django ORM async**: `aget()`, `acreate()` — `afilter()` NÃO existe, usar `.filter()` com async iteration
- **Type hints** em TODAS as funções
- **structlog** para logging (NUNCA `print()`)
- **AppError hierarchy** para exceções (usar `GraphNodeError` para falhas em nós)
- **Import order**: Standard → Third-party → Local
- **NUNCA** `import *`, sync I/O, commitar secrets, logar PII sem sanitização
- **Nomes**: snake_case (arquivos, funções, variáveis), PascalCase (classes), UPPER_SNAKE_CASE (constantes)
- **LangGraph node contract**: funções async puras → `async def node_name(state: WhatsAppState) -> dict`
- **Retorno parcial**: nós SEMPRE retornam `dict` parcial (apenas campos alterados), NUNCA o estado completo

### Infraestrutura Já Disponível (Stories 1.1 e 1.2 — NÃO RECRIAR)
- `workflows/models.py` — User (phone, medway_id, subscription_tier, metadata, created_at), Message (user FK, content, role, message_type, tokens, cost, created_at), Config, ConfigHistory
- `workflows/utils/errors.py` — AppError, ValidationError, AuthenticationError, RateLimitError, ExternalServiceError, GraphNodeError
- `workflows/utils/sanitization.py` — PII redaction processor para structlog
- `workflows/utils/deduplication.py` — Redis singleton `_get_redis_client()` + `is_duplicate_message()`
- `workflows/services/config_service.py` — ConfigService.get() async
- `workflows/middleware/webhook_signature.py` — HMAC SHA-256 validation
- `workflows/middleware/trace_id.py` — UUID trace_id + structlog contextvars
- `workflows/views.py` — WhatsAppWebhookView (GET handshake + POST fire-and-forget com `_process_message()` placeholder)
- `workflows/serializers.py` — WhatsAppMessageSerializer (phone regex, timestamp, type)
- `workflows/urls.py` — URL routing (`webhook/whatsapp/`)
- `workflows/apps.py` — WorkflowsConfig com structlog configure (inclui `merge_contextvars`)
- `config/settings/base.py` — REDIS_URL, middlewares, structlog
- `config/settings/test.py` — Settings de teste com webhook secrets
- `docker-compose.yml` — PostgreSQL 16 + Redis 7
- 63 testes passando

### Correções Críticas da Story 1.2 (Manter Compatibilidade)
- Redis singleton em `deduplication.py` usa `aioredis.from_url()` com pool interno — REUSAR mesmo padrão
- `asyncio.create_task()` tem `_handle_task_exception` callback — manter para graph dispatch
- structlog config em `WorkflowsConfig.ready()` com `merge_contextvars` — trace_id propaga automaticamente
- TraceIDMiddleware com try/finally para cleanup de contextvars

### Inteligência da Story Anterior (1-2)

**Lições aprendidas:**
- Django `AsyncClient` em testes: usar `headers={}` dict (Django 5.2+) em vez de `HTTP_*` kwargs
- Redis precisa de connection pooling (singleton) — NÃO criar conexão nova por request
- Testes devem incluir settings de teste com secrets definidos
- Event filtering: processar TODOS os elementos dos arrays (não apenas `[0]`)
- HMAC validation usa `request.body` (RAW bytes) — nunca `request.data`

**Padrões de código estabelecidos:**
- Middleware: async-capable dual-mode
- Views: `adrf.views.APIView` com `async def post()/get()`
- Serializers: DRF com validação regex, timestamp, type
- Deduplicação: Redis SETNX, fail-open (processa se Redis indisponível)
- Testes: `@pytest.mark.django_db` + mocks com `AsyncMock`

**Arquivos criados na Story 1.2 que impactam Story 1.3:**
- `workflows/views.py` — Contém `_process_message()` placeholder que DEVE ser atualizado nesta story
- `workflows/utils/deduplication.py` — Padrão Redis singleton que DEVE ser reusado para session cache

### Project Structure Notes

#### Arquivos a Criar
```
workflows/
├── whatsapp/
│   ├── state.py                   # CRIAR — WhatsAppState TypedDict
│   ├── graph.py                   # IMPLEMENTAR (existe vazio) — build_whatsapp_graph()
│   └── nodes/
│       ├── __init__.py            # JÁ EXISTE (vazio)
│       ├── identify_user.py       # CRIAR — nó identify_user
│       └── load_context.py        # CRIAR — nó load_context
└── services/
    └── cache_manager.py           # CRIAR — CacheManager (session cache Redis)

tests/
├── test_identify_user.py          # CRIAR — Testes do nó identify_user
├── test_load_context.py           # CRIAR — Testes do nó load_context
├── test_state.py                  # CRIAR — Testes do WhatsAppState
└── test_graph.py                  # CRIAR — Testes do grafo completo
```

#### Arquivos a Modificar
```
workflows/
├── views.py                       # MODIFICAR — Substituir _process_message() placeholder
└── whatsapp/
    └── graph.py                   # IMPLEMENTAR (existe mas vazio)

workflows/whatsapp/nodes/
└── __init__.py                    # MODIFICAR — Exportar nós
```

#### Alignment com Estrutura Existente
- Nós em `workflows/whatsapp/nodes/` (conforme architecture.md)
- State em `workflows/whatsapp/state.py` (conforme architecture.md)
- Graph em `workflows/whatsapp/graph.py` (conforme architecture.md)
- Services em `workflows/services/` (padrão da Story 1.1)
- Testes em `tests/` na raiz do projeto (padrão das Stories 1.1/1.2)

### Guardrails de Arquitetura

#### ADRs Aplicáveis
| ADR | Decisão | Impacto nesta Story |
|-----|---------|---------------------|
| ADR-003 | Django ORM (não supabase-py) | User.objects.aget(), Message.objects.filter() async |
| ADR-007 | Redis 4 camadas | Session cache: `session:{user_id}`, TTL 1h |
| ADR-009 | App `workflows/` | Localização de nós, state, graph |
| ADR-010 | LangGraph + LangChain 1.0 | StateGraph, node contract async, add_messages reducer |

#### Requisitos Não-Funcionais (NFR)
| NFR | Requisito | Como Implementar |
|-----|-----------|------------------|
| NFR4 | 50 conversas concorrentes | `asyncio.Semaphore(50)` no graph dispatch (Story 1.4, preparar aqui) |
| NFR13 | Nenhuma mensagem perdida | Tratar exceções no graph dispatch com fallback de resposta |
| NFR15 | Dados protegidos com RLS | Django ORM + Supabase RLS como defense-in-depth |

#### Libraries/Frameworks — Versões e Padrões Atualizados

| Lib | Versão | Uso nesta Story | Notas Importantes |
|-----|--------|----------------|-------------------|
| Django | 5.2 LTS | ORM async: `aget()`, `acreate()`, async iteration | `afilter()` NÃO existe — usar `.filter()` com `async for` |
| LangGraph | 1.0 | StateGraph, node functions, `add_messages` | Zero breaking changes de 0.x; nodes retornam dict parcial |
| LangChain | 1.0 | `HumanMessage`, `AIMessage`, `AnyMessage` | Import: `langchain_core.messages` |
| redis-py | 5.2+ | Session cache, `from_url()` singleton | `from_url()` cria pool interno; usar `set(..., ex=TTL)` |
| structlog | 24.4+ | Logging com PII sanitization | Já configurado no WorkflowsConfig.ready() |

### Informações Técnicas Atualizadas (Pesquisa Web — Mar 2026)

#### LangGraph 1.0 — Padrões de Node
```python
# CORRETO: Node async retornando dict parcial
async def identify_user(state: WhatsAppState) -> dict:
    # ... lógica ...
    return {"user_id": "123", "subscription_tier": "free"}  # Parcial

# ERRADO: Retornar estado completo (anti-pattern)
async def identify_user(state: WhatsAppState) -> WhatsAppState:
    state["user_id"] = "123"
    return state  # NÃO fazer isso
```

#### Django ORM Async — Padrões Corretos
```python
# aget() — busca unitária (async)
user = await User.objects.aget(phone=phone)

# acreate() — criação (async)
user = await User.objects.acreate(phone=phone, subscription_tier="free")

# filter() + async iteration — NÃO existe afilter()
messages = [msg async for msg in Message.objects.filter(user_id=uid).order_by("-created_at")[:20]]

# afirst() — primeiro resultado (async)
first_msg = await Message.objects.filter(user_id=uid).afirst()
```

#### Redis Async — Session Cache
```python
# Singleton pattern (reusar de deduplication.py)
import redis.asyncio as aioredis
_redis_client: aioredis.Redis | None = None

def _get_redis_client() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client

# set() com TTL (preferido em redis-py 5.x sobre setex())
await client.set(f"session:{user_id}", json.dumps(data), ex=3600)

# get() com decode automático
data = await client.get(f"session:{user_id}")
return json.loads(data) if data else None
```

#### LangChain Messages — Conversão Correta
```python
from langchain_core.messages import HumanMessage, AIMessage, AnyMessage

# Converter Django Message → LangChain Message
for msg in reversed(messages):  # Oldest first para contexto cronológico
    if msg.role == "user":
        lc_messages.append(HumanMessage(content=msg.content))
    elif msg.role == "assistant":
        lc_messages.append(AIMessage(content=msg.content))
```

#### WhatsAppState — add_messages Reducer
```python
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage

class WhatsAppState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]  # Acumula automaticamente
```
O reducer `add_messages` concatena novas mensagens à lista existente automaticamente. Nós retornam `{"messages": [new_msg]}` e o LangGraph faz o merge.

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 1, Story 1.3]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-003 (Django ORM async patterns)]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-007 (Redis 4 Camadas, Session Cache)]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-010 (LangGraph StateGraph, Node Contract)]
- [Source: _bmad-output/planning-artifacts/architecture.md — WhatsAppState TypedDict definition]
- [Source: _bmad-output/planning-artifacts/architecture.md — Testing Standards (conftest.py fixtures)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Medway API timeout 8s, 3x retry, fallback guest]
- [Source: _bmad-output/implementation-artifacts/1-2-webhook-whatsapp-middleware-seguranca.md — Dev Notes, File List, Code Review]
- [Source: LangGraph 1.0 Documentation — StateGraph, add_messages, async nodes]
- [Source: Django 5.2 Async ORM Documentation — aget(), acreate(), async iteration]
- [Source: redis-py 5.x Documentation — from_url() pooling, set() with ex parameter]
- [Source: Meta WhatsApp Cloud API — BSUID notice June 2026]

## Change Log

- **2026-03-07:** Implementação completa da Story 1.3 — Identificação de Usuário + Carregamento de Contexto. Criados WhatsAppState TypedDict, CacheManager (session cache Redis), nós identify_user e load_context, grafo LangGraph inicial (START → identify_user → load_context → END), integração com webhook. 84 testes passando (21 novos), zero regressão.
- **2026-03-07:** Code Review (AI) — 7 issues encontradas e corrigidas (1 CRITICAL, 2 HIGH, 3 MEDIUM, 1 LOW). Ver seção "Senior Developer Review (AI)" abaixo. 84 testes passando após correções.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Testes async com `@pytest.mark.django_db` requerem `transaction=True` para isolamento correto do banco entre testes que criam model instances com campos unique. Sem isso, testes que criam Users com mesmo phone number colidem via `IntegrityError: UNIQUE constraint failed`.

### Completion Notes List

- **Task 1:** WhatsAppState TypedDict criado com 15 campos: input (5), identificação (2), contexto com `add_messages` reducer (1), output placeholder (2), observabilidade (2), citação placeholder (3), transcrição placeholder (1)
- **Task 2:** CacheManager com 3 métodos estáticos (`cache_session`, `get_session`, `invalidate_session`), reutilizando `_get_redis_client()` singleton de `deduplication.py`, fail-safe em caso de erro Redis
- **Task 3:** Nó `identify_user` — verifica cache Redis → busca/cria User via Django ORM async → cacheia resultado. Retorna dict parcial `{user_id, subscription_tier}`
- **Task 4:** Nó `load_context` — verifica cache Redis → busca últimas 20 mensagens via async iteration → converte para HumanMessage/AIMessage → inverte para ordem cronológica → cacheia. Retorna dict parcial `{messages}`
- **Task 5:** `build_whatsapp_graph()` com StateGraph(WhatsAppState), flow START → identify_user → load_context → END, `get_graph()` singleton
- **Task 6:** `_process_message()` atualizado: constrói initial_state, invoca grafo com `thread_id=phone`, loga `graph_execution_started/completed`, trata `GraphNodeError` e exceções genéricas
- **Task 7:** 21 testes novos cobrindo todos os 5 ACs: 4 testes identify_user, 4 testes load_context, 3 testes state, 6 testes cache_manager, 4 testes graph (construção + execução + webhook integração)

### File List

**Novos:**
- `workflows/whatsapp/state.py` — WhatsAppState TypedDict (15 campos, add_messages reducer)
- `workflows/services/cache_manager.py` — CacheManager (session cache Redis, TTL 1h)
- `workflows/whatsapp/nodes/identify_user.py` — Nó identify_user (busca/cria User, cache)
- `workflows/whatsapp/nodes/load_context.py` — Nó load_context (últimas 20 msgs, LangChain conversion)
- `tests/test_state.py` — 3 testes para WhatsAppState (AC4)
- `tests/test_cache_manager.py` — 6 testes para CacheManager
- `tests/test_identify_user.py` — 4 testes para identify_user (AC1, AC2)
- `tests/test_load_context.py` — 4 testes para load_context (AC3)
- `tests/test_graph.py` — 4 testes para grafo + integração webhook (AC5)

**Modificados:**
- `workflows/whatsapp/graph.py` — Implementado build_whatsapp_graph() e get_graph() (era stub vazio)
- `workflows/whatsapp/nodes/__init__.py` — Exporta identify_user e load_context (era vazio)
- `workflows/views.py` — _process_message() atualizado: placeholder → graph execution com logging

## Senior Developer Review (AI)

**Reviewer:** Claude Opus 4.6 (adversarial code review)
**Data:** 2026-03-07
**Resultado:** Aprovado após correções

### Issues Encontradas e Corrigidas

| # | Severidade | Issue | Arquivo | Correção |
|---|-----------|-------|---------|----------|
| 1 | CRITICAL | Cache key mismatch: `get_session(phone)` vs `cache_session(user_id)` — cache NUNCA funcionava | `identify_user.py` | Alterado para `cache_session(phone, ...)` — chave consistente |
| 2 | HIGH | Testes over-mocked não detectavam bug #1 — falsa sensação de segurança | `test_identify_user.py` | Adicionadas assertions de consistência de chave get/set |
| 3 | MEDIUM | Return type annotations erradas: `-> StateGraph` em vez de `-> CompiledStateGraph` | `graph.py` | Corrigido para `-> CompiledStateGraph` |
| 4 | MEDIUM | Mensagens com roles desconhecidos descartadas silenciosamente | `load_context.py` | Adicionado `logger.warning("message_role_skipped")` |
| 5 | MEDIUM | Teste webhook não verificava execução do grafo (fire-and-forget gap) | `test_graph.py` | Adicionada verificação de side effect: User criado no banco |
| 6 | MEDIUM | NFR13 fallback não documentado como limitação | `views.py` | Adicionados TODOs para Story 1.5 |
| 7 | LOW | Singleton test com side effects no módulo (sem cleanup) | `test_graph.py` | Adicionado try/finally com restauração do estado original |

### Falso Positivo Identificado

- **PII logging (phone):** Inicialmente flagged como HIGH, mas o `sanitize_pii` processor já está no pipeline structlog (`apps.py:17`) e `"phone"` está em `SENSITIVE_FIELDS`. Logs são sanitizados automaticamente.

### Verificação Final

- 84 testes passando (zero regressão)
- Todos os 5 ACs implementados e verificados
- Todas as 7 Tasks completadas conforme especificação
