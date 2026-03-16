# Story 1.6: Debounce, Boas-vindas e Mensagens Não Suportadas

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a aluno,
I want que o sistema acumule minhas mensagens rápidas e me receba bem na primeira vez,
So that não recebo respostas parciais e tenho uma boa primeira impressão.

## Acceptance Criteria

### AC1: Debounce — Acumulação de Mensagens Rápidas via Redis

```gherkin
Given um aluno que envia 3 mensagens em 2 segundos
When as mensagens são recebidas pelo webhook
Then o sistema acumula via Redis message buffer (`msg_buffer:{phone}`, TTL configurável via `debounce_ttl`)
And processa todas as mensagens acumuladas como uma única entrada após o período de debounce
And o período de debounce default é 3 segundos (configurável via Config model / Django Admin)
And cada nova mensagem durante o período "reseta" o timer (last-message-wins)
And o mecanismo é multi-instance safe (Cloud Run com múltiplas instâncias)
```

### AC2: Debounce — Mensagem Única (Sem Acumulação)

```gherkin
Given um aluno que envia uma única mensagem
When a mensagem é recebida pelo webhook
Then o sistema aguarda o período de debounce (3s default)
And após o período sem novas mensagens, processa normalmente como entrada única
And o comportamento é transparente para o usuário (não percebe o delay de 3s)
```

### AC3: Boas-vindas — Primeira Interação

```gherkin
Given um número de telefone que nunca interagiu com o sistema
When envia a primeira mensagem
Then o sistema envia mensagem de boas-vindas ANTES da resposta do LLM
And a boas-vindas vem do Config model (key `message:welcome`)
And o texto default é: "Olá! Sou o Medbrain, seu tutor médico pelo WhatsApp. Pode me perguntar qualquer dúvida médica — respondo com fontes verificáveis."
And a boas-vindas é enviada apenas UMA VEZ (na primeira mensagem do usuário)
And após a boas-vindas, a resposta normal do LLM é enviada em seguida
```

### AC4: Boas-vindas — Usuário Recorrente

```gherkin
Given um número de telefone que já interagiu com o sistema antes
When envia uma nova mensagem
Then o sistema NÃO envia mensagem de boas-vindas
And processa a mensagem normalmente
```

### AC5: Mensagens Não Suportadas — Tipos Não Processáveis

```gherkin
Given um aluno que envia sticker, localização, documento, contato ou vídeo
When o webhook recebe o tipo não suportado
Then o sistema responde com mensagem informativa do Config model (key `message:unsupported_type`)
And o texto default é: "Desculpe, no momento só consigo processar mensagens de texto, áudio e imagem."
And a mensagem informativa é enviada diretamente via WhatsApp Cloud API (sem invocar o grafo LangGraph)
And nenhuma chamada ao LLM é feita (economia de custo)
And a mensagem é logada via structlog como `unsupported_message_handled`
```

### AC6: Mensagens Não Suportadas — A Mensagem é Configurável

```gherkin
Given a equipe Medway edita `message:unsupported_type` no Django Admin
When a próxima mensagem não suportada é recebida
Then usa o texto atualizado do Config model
And a atualização entra em vigor sem deploy (config dinâmica)
```

## Tasks / Subtasks

- [x] Task 1: Criar `workflows/services/debounce.py` — Serviço de debounce com Redis (AC: #1, #2)
  - [x] 1.1 Criar `workflows/services/debounce.py`
  - [x] 1.2 Implementar `buffer_message(phone: str, message_data: str) -> None` — RPUSH para `msg_buffer:{phone}` + EXPIRE (pipeline atômico)
  - [x] 1.3 Implementar `get_and_clear_buffer(phone: str) -> list[str]` — LRANGE 0 -1 + DELETE (atômico)
  - [x] 1.4 Implementar `schedule_processing(phone: str, validated_data: dict, process_callback) -> None`:
    - Buffer a mensagem via `buffer_message()`
    - SET `msg_timer:{phone}` com timestamp próprio + EX (debounce_ttl + 5)
    - `asyncio.sleep(debounce_ttl)` (chamado via `asyncio.create_task` em `views.py`)
    - Após sleep, verificar se `msg_timer:{phone}` ainda contém nosso timestamp (last-message-wins)
    - Se sim: `get_and_clear_buffer()` (Lua script atômico) → combinar mensagens → chamar `process_callback()`
    - Se não: skip (outro timer mais recente processará)
  - [x] 1.5 Carregar `debounce_ttl` do ConfigService (key `debounce_ttl`, default 3)
  - [x] 1.6 Usar Redis singleton de `workflows/utils/deduplication.py` (`_get_redis_client()`)
  - [x] 1.7 Logar via structlog: `message_buffered`, `debounce_timer_set`, `debounce_batch_processing`, `debounce_timer_superseded`

- [x] Task 2: Atualizar `workflows/views.py` — Integrar debounce e tipos não suportados (AC: #1, #2, #5, #6)
  - [x] 2.1 Definir `SUPPORTED_TYPES = {"text", "audio", "image"}` (tipos que passam pelo grafo)
  - [x] 2.2 Definir `UNSUPPORTED_RESPONSE_TYPES = {"sticker", "location", "document", "contacts", "video"}` (tipos que recebem mensagem informativa)
  - [x] 2.3 Após dedup check, verificar `message_type`:
    - Se `message_type in UNSUPPORTED_RESPONSE_TYPES` → criar task para `_handle_unsupported_message(phone, message_type)`
    - Se `message_type in SUPPORTED_TYPES` → criar task para debounce: `schedule_processing(phone, validated, debounce_ttl)`
  - [x] 2.4 Implementar `_handle_unsupported_message(phone: str, message_type: str)`:
    - Carregar texto do ConfigService (key `message:unsupported_type`)
    - Enviar via `send_text_message(phone, texto)`
    - Logar `unsupported_message_handled` com phone, message_type
  - [x] 2.5 Remover chamada direta a `_process_message()` (agora é feita pelo debounce service)
  - [x] 2.6 Tratar caso onde ConfigService falha (usar texto default hardcoded como fallback)

- [x] Task 3: Atualizar `workflows/whatsapp/nodes/identify_user.py` — Flag de novo usuário (AC: #3, #4)
  - [x] 3.1 Quando `User.DoesNotExist` → criar user E retornar `"is_new_user": True`
  - [x] 3.2 Quando user já existe (cache hit ou DB hit) → retornar `"is_new_user": False`
  - [x] 3.3 Logar `user_created` com `is_new_user=True` via structlog

- [x] Task 4: Atualizar `workflows/whatsapp/state.py` — Novos campos (AC: #1, #3)
  - [x] 4.1 Adicionar campo `is_new_user: bool` ao WhatsAppState

- [x] Task 5: Atualizar `workflows/whatsapp/nodes/send_whatsapp.py` — Boas-vindas (AC: #3, #4)
  - [x] 5.1 Antes de enviar `formatted_response`, verificar `state["is_new_user"]`
  - [x] 5.2 Se `is_new_user is True`:
    - Carregar mensagem de boas-vindas do ConfigService (key `message:welcome`)
    - Enviar via `send_text_message(phone, welcome_message)` ANTES da resposta
    - Logar `welcome_message_sent` com phone via structlog
  - [x] 5.3 Se ConfigService falha, usar texto default hardcoded como fallback
  - [x] 5.4 Continuar com o fluxo normal de envio (formatted_response + additional_responses)

- [x] Task 6: Atualizar `workflows/views.py` — initial_state com is_new_user (AC: #3)
  - [x] 6.1 Adicionar `"is_new_user": False` ao `initial_state` em `_process_message()`

- [x] Task 7: Atualizar dados de configuração — Mensagens configuráveis (AC: #3, #5, #6)
  - [x] 7.1 Verificar que data migration 0002 já contém `message:welcome`, `message:unsupported_type`, `debounce_ttl`
  - [x] 7.2 Atualizar `message:welcome` para o texto exato do AC: "Olá! Sou o Medbrain, seu tutor médico pelo WhatsApp. Pode me perguntar qualquer dúvida médica — respondo com fontes verificáveis."
  - [x] 7.3 Atualizar `message:unsupported_type` para o texto exato do AC: "Desculpe, no momento só consigo processar mensagens de texto, áudio e imagem."
  - [x] 7.4 Criar nova data migration `0003_update_config_messages.py` com os textos atualizados

- [x] Task 8: Testes (TODOS os ACs)
  - [x] 8.1 Criar `tests/test_services/test_debounce.py`
  - [x] 8.2 Teste: `buffer_message()` faz RPUSH + EXPIRE correto no Redis (AC1)
  - [x] 8.3 Teste: `get_and_clear_buffer()` retorna mensagens e limpa buffer (AC1)
  - [x] 8.4 Teste: `schedule_processing()` — mensagem única processada após debounce_ttl (AC2)
  - [x] 8.5 Teste: `schedule_processing()` — 3 mensagens rápidas combinadas em uma entrada (AC1)
  - [x] 8.6 Teste: `schedule_processing()` — last-message-wins: timer antigo não processa (AC1)
  - [x] 8.7 Teste: debounce_ttl carregado do ConfigService (AC1)
  - [x] 8.8 Estendido `tests/test_identify_user.py` com assertions de is_new_user
  - [x] 8.9 Teste: novo user retorna `is_new_user: True` (AC3)
  - [x] 8.10 Teste: user existente retorna `is_new_user: False` (AC4)
  - [x] 8.11 Teste: user no cache retorna `is_new_user: False` (AC4)
  - [x] 8.12 Atualizado `tests/test_whatsapp/test_nodes/test_send_whatsapp.py`
  - [x] 8.13 Teste: `is_new_user=True` → envia welcome message ANTES da resposta (AC3)
  - [x] 8.14 Teste: `is_new_user=False` → NÃO envia welcome message (AC4)
  - [x] 8.15 Teste: welcome message vem do ConfigService (AC3)
  - [x] 8.16 Teste: ConfigService falha → usa texto default (AC3)
  - [x] 8.17 Estendido `tests/test_webhook.py` com TestUnsupportedMessageTypes
  - [x] 8.18 Teste: sticker message → handler chamado (AC5)
  - [x] 8.19 Teste: location message → handler chamado (AC5)
  - [x] 8.20 Teste: document message → handler chamado (AC5)
  - [x] 8.21 Teste: contacts message → handler chamado (AC5)
  - [x] 8.22 Teste: video message → handler chamado (AC5)
  - [x] 8.23 Teste: text message → NÃO envia unsupported message (AC5)
  - [x] 8.24 Teste: unsupported type NÃO invoca o grafo LangGraph (AC5)
  - [x] 8.25 Atualizado `tests/test_graph.py` com `is_new_user` no initial_state

## Dev Notes

### Contexto de Negócio
- Story 1.6 é a **última story do Epic 1** — completa a experiência UX do pipeline de texto.
- Após esta story, o pipeline E2E está completo com debounce, boas-vindas e tratamento gracioso de mensagens não suportadas.
- O debounce é CRÍTICO para evitar respostas parciais quando o aluno "fragmenta" uma pergunta em várias mensagens rápidas (comportamento comum no WhatsApp).
- A mensagem de boas-vindas é a PRIMEIRA impressão do aluno — deve ser acolhedora e informativa.
- Mensagens não suportadas: NÃO invocar o LLM = economia de custo + resposta mais rápida.

### Padrões Obrigatórios (Estabelecidos nas Stories 1.1-1.5)
- **SEMPRE** async/await para I/O (NUNCA bloqueante)
- **Django ORM async**: `aget()`, `acreate()` — `afilter()` NÃO existe, usar `.filter()` com async iteration
- **Type hints** em TODAS as funções
- **structlog** para logging (NUNCA `print()`)
- **AppError hierarchy** para exceções (usar `GraphNodeError` para falhas em nós, `ExternalServiceError` para WhatsApp API)
- **Import order**: Standard → Third-party → Local
- **NUNCA** `import *`, sync I/O, commitar secrets, logar PII sem sanitização
- **Nomes**: snake_case (arquivos, funções, variáveis), PascalCase (classes), UPPER_SNAKE_CASE (constantes)
- **LangGraph node contract**: `async def node_name(state: WhatsAppState) -> dict` retornando dict parcial
- **Retorno parcial**: nós SEMPRE retornam `dict` parcial (apenas campos alterados), NUNCA o estado completo
- **RetryPolicy**: usar `retry_policy=RetryPolicy(...)` (NÃO `retry=` — deprecado no LangGraph 1.0.10)

### Infraestrutura Já Disponível (Stories 1.1-1.5 — NÃO RECRIAR)
- `workflows/models.py` — User, Message, Config, ConfigHistory (NÃO tem CostLog/ToolExecution)
- `workflows/utils/errors.py` — AppError, ValidationError, AuthenticationError, RateLimitError, ExternalServiceError, GraphNodeError
- `workflows/utils/sanitization.py` — PII redaction processor para structlog
- `workflows/utils/deduplication.py` — Redis singleton `_get_redis_client()` + `is_duplicate_message()`
- `workflows/services/config_service.py` — ConfigService.get() async
- `workflows/services/cache_manager.py` — CacheManager (session cache Redis, TTL 1h)
- `workflows/services/cost_tracker.py` — CostTrackingCallback (AsyncCallbackHandler)
- `workflows/middleware/webhook_signature.py` — HMAC SHA-256 validation
- `workflows/middleware/trace_id.py` — UUID trace_id + structlog contextvars
- `workflows/views.py` — WhatsAppWebhookView (GET handshake + POST fire-and-forget com `_process_message()`)
- `workflows/serializers.py` — WhatsAppMessageSerializer (rejeita system, unknown, ephemeral, unsupported)
- `workflows/whatsapp/state.py` — WhatsAppState TypedDict (15 campos, `add_messages` reducer)
- `workflows/whatsapp/graph.py` — `build_whatsapp_graph()` (START → identify_user → load_context → orchestrate_llm → format_response → send_whatsapp → persist → END) + `get_graph()` async singleton
- `workflows/whatsapp/nodes/identify_user.py` — Nó identify_user (busca/cria User, cache Redis session)
- `workflows/whatsapp/nodes/load_context.py` — Nó load_context (últimas 20 msgs, LangChain conversion)
- `workflows/whatsapp/nodes/orchestrate_llm.py` — Nó orchestrate_llm com cost tracking
- `workflows/whatsapp/nodes/format_response.py` — Nó format_response (validate, strip, format, split)
- `workflows/whatsapp/nodes/send_whatsapp.py` — Nó send_whatsapp (Cloud API + typing indicator + retry)
- `workflows/whatsapp/nodes/persist.py` — Nó persist (Django ORM Message)
- `workflows/providers/whatsapp.py` — WhatsApp Cloud API client (httpx async singleton, `send_text_message()`, `mark_as_read()`)
- `workflows/providers/llm.py` — get_model() singleton com ChatVertexAI + ChatAnthropic fallback
- `workflows/providers/checkpointer.py` — get_checkpointer() singleton com AsyncPostgresSaver
- `workflows/utils/formatters.py` — Markdown → WhatsApp formatting + disclaimer + content type detection
- `workflows/utils/message_splitter.py` — Split mensagens > 4096 chars
- `config/settings/base.py` — REDIS_URL, WHATSAPP_WEBHOOK_SECRET, WHATSAPP_VERIFY_TOKEN, VERTEX_PROJECT_ID, etc.
- Data migration `0002_initial_configs.py` — configs: `message:welcome`, `message:unsupported_type`, `debounce_ttl`, `rate_limit:free`, `rate_limit:premium`, `blocked_competitors`, `message:rate_limit`
- 188 testes passando (Stories 1.1-1.5)

### Inteligência da Story Anterior (1-5)

**Lições aprendidas:**
- `ChatAnthropicVertex` foi unificado em `ChatVertexAI` no langchain-google-vertexai 3.2.2
- `retry=` está deprecado em `add_node()` — usar `retry_policy=RetryPolicy(...)`
- `MagicMock()` como checkpointer falha isinstance — usar `InMemorySaver()` em testes
- `LLMResult` com Pydantic v2: usar `ChatGeneration(message=AIMessage(...))` em vez de MagicMock
- Django `AsyncClient` em testes: usar `headers={}` dict em vez de `HTTP_*` kwargs
- Redis precisa de connection pooling (singleton)
- `afilter()` NÃO existe no Django ORM — usar `.filter()` com `async for`
- `@pytest.mark.django_db` requer `transaction=True` para isolamento com campos unique
- httpx.Response mock: `MagicMock(spec=httpx.Response)` em vez de `AsyncMock` para métodos síncronos `.json()` / `.raise_for_status()`
- httpx.AsyncClient singleton: NÃO criar novo client por request (connection pooling)
- WhatsApp typing indicator é best-effort — se falhar, NÃO bloquear o pipeline
- persist node NÃO deve falhar o pipeline — se Django ORM falhar, logar ERROR mas NÃO re-raise
- graph singleton reset — ao adicionar novos nós, `_compiled_graph` precisa ser `None` para recompilar. Em testes, usar `build_whatsapp_graph()` diretamente
- Phone number format — WhatsApp espera número sem `+` no payload de envio (ex: `5511999999999`)

**Padrões de código estabelecidos:**
- Nós LangGraph: `async def node_name(state: WhatsAppState) -> dict` retornando dict parcial
- Testes: `@pytest.mark.django_db(transaction=True)` + mocks com `AsyncMock`
- Singleton: `_compiled_graph`, `_model_cache`, `_checkpointer`, `_redis_client`, `_client` (httpx)
- Graph: `get_graph()` async singleton via `build_whatsapp_graph().compile()`
- Redis: `_get_redis_client()` de `workflows/utils/deduplication.py` como singleton compartilhado
- WhatsApp client: `send_text_message(phone, text)` e `mark_as_read(wamid)` de `workflows/providers/whatsapp.py`

### Decisão Arquitetural: Mecanismo de Debounce Multi-Instance

**Problema:** Cloud Run pode ter múltiplas instâncias processando webhooks do mesmo user simultaneamente. O debounce precisa ser multi-instance safe.

**Solução: Last-Message-Wins com Redis Timer**

```python
# Fluxo do debounce (multi-instance safe):
# 1. Webhook recebe mensagem → RPUSH para msg_buffer:{phone}
# 2. SET msg_timer:{phone} = meu_timestamp (EX = debounce_ttl + 5s safety margin)
# 3. asyncio.create_task → asyncio.sleep(debounce_ttl)
# 4. Após sleep, GET msg_timer:{phone}:
#    - Se == meu_timestamp → eu sou o timer mais recente → processar batch
#    - Se != meu_timestamp → timer mais recente vai processar → skip
# 5. Processar: LRANGE msg_buffer:{phone} 0 -1 → DELETE → combinar → invocar grafo

# Chaves Redis:
# msg_buffer:{phone} → lista de mensagens (RPUSH, LRANGE, DELETE)
# msg_timer:{phone}  → timestamp do último timer (SET, GET, DELETE)
```

**Por que esta abordagem:**
- Cada nova mensagem reseta o timer (SET sobrescreve o timestamp anterior)
- Após o sleep, apenas o timer mais recente processa (comparação de timestamp)
- Funciona com múltiplas instâncias: Redis é o árbitro
- Sem locks distribuídos complexos
- Sem dependências extras (Celery, Cloud Tasks, etc.)

**Fluxo de debounce na views.py (NOVO):**
```
webhook POST → should_process_event → dedup:
  ├── message_type in UNSUPPORTED → _handle_unsupported_message() → return 200
  └── message_type in SUPPORTED → schedule_processing(phone, data, debounce_ttl) → return 200
                                     └── (após delay) → _process_message() → graph.ainvoke
```

### Decisão: Tipos de Mensagem Suportados vs Não Suportados

| Tipo | Status | Ação |
|------|--------|------|
| `text` | ✅ Suportado | Debounce → grafo → resposta LLM |
| `audio` | ✅ Suportado (Epic 3.1) | Debounce → grafo → (sem transcrição até Epic 3) |
| `image` | ✅ Suportado (Epic 3.2) | Debounce → grafo → (sem análise até Epic 3) |
| `sticker` | ❌ Não suportado | Mensagem informativa direta |
| `location` | ❌ Não suportado | Mensagem informativa direta |
| `document` | ❌ Não suportado | Mensagem informativa direta |
| `contacts` | ❌ Não suportado | Mensagem informativa direta |
| `video` | ❌ Não suportado | Mensagem informativa direta |

**Nota:** `audio` e `image` são listados como "suportados" na mensagem de unsupported_type. Eles passam pelo grafo, mas sem processamento real até os Epics 3.1/3.2. Se alguém enviar áudio/imagem agora, o LLM receberá uma mensagem vazia — comportamento subótimo mas sem crash.

### Decisão: Debounce para Audio/Image

- Debounce aplica-se a TODOS os tipos suportados (text, audio, image)
- Caso de uso: aluno envia "vou mandar uma foto" (texto) seguido de uma imagem 2s depois → debounce acumula ambos
- Para texto, as mensagens são combinadas com `\n` como separador
- Para audio/image, o buffer armazena os metadados (media_url, message_type) — processamento real no Epic 3

### Project Structure Notes

#### Arquivos a Criar
```
workflows/
└── services/
    └── debounce.py              # CRIAR — Serviço de debounce com Redis (buffer + timer)

tests/
└── test_services/
    └── test_debounce.py         # CRIAR — Testes do serviço de debounce
```

#### Arquivos a Modificar
```
workflows/
├── views.py                     # MODIFICAR — Integrar debounce + unsupported types handling
├── whatsapp/
│   ├── state.py                 # MODIFICAR — Adicionar is_new_user
│   └── nodes/
│       ├── identify_user.py     # MODIFICAR — Retornar is_new_user flag
│       └── send_whatsapp.py     # MODIFICAR — Enviar welcome message para novos users
└── migrations/
    └── 0003_update_config_messages.py  # CRIAR — Atualizar textos de mensagens configuráveis

tests/
├── test_services/
│   ├── __init__.py              # CRIAR — Package init
│   └── test_debounce.py         # CRIAR — Testes do debounce
├── test_whatsapp/
│   └── test_nodes/
│       ├── test_identify_user.py  # MODIFICAR — Testar is_new_user flag
│       └── test_send_whatsapp.py  # MODIFICAR — Testar welcome message
├── test_views.py                # MODIFICAR — Testar unsupported types + debounce integration
└── test_graph.py                # MODIFICAR — Atualizar initial_state com is_new_user
```

### Guardrails de Arquitetura

#### ADRs Aplicáveis
| ADR | Decisão | Impacto nesta Story |
|-----|---------|---------------------|
| ADR-002 | Django + DRF + adrf | Async views, webhook handling |
| ADR-007 | Redis 4 camadas (CacheManager) | Message Buffer (`msg_buffer:{phone}`, TTL 3s) é a Camada 1 |
| ADR-009 | App `workflows/` | Debounce em `workflows/services/`, nodes em `workflows/whatsapp/nodes/` |
| ADR-010 | LangGraph + LangChain 1.0 | Nodes retornam dict parcial, WhatsAppState TypedDict |

#### Requisitos Não-Funcionais (NFR)
| NFR | Requisito | Como Implementar |
|-----|-----------|------------------|
| NFR5 | Debounce ≤ 3s | TTL configurável via Config model `debounce_ttl` (default 3) |
| NFR13 | Nenhuma mensagem perdida | Unsupported types recebem resposta, debounce garante processamento de todas as mensagens bufferizadas |
| NFR14 | Webhook 200 OK < 3s | fire-and-forget: debounce é asyncio.create_task, webhook retorna imediatamente |
| NFR17 | Credenciais em env vars | Já implementado (reusa settings existentes) |
| NFR19 | Logs sem PII | Phone já redacted pelo sanitize_pii processor |

### Libraries/Frameworks — Versões e Padrões

| Lib | Versão | Uso nesta Story | Notas Importantes |
|-----|--------|----------------|-------------------|
| redis-py | 5.2+ | Message buffer (RPUSH, LRANGE, DELETE, EXPIRE, SET, GET) | Import: `from workflows.utils.deduplication import _get_redis_client`. Pipeline atômico para RPUSH+EXPIRE |
| httpx | 0.28+ | Envio de unsupported + welcome messages | Reusa singleton de `workflows/providers/whatsapp.py` |
| structlog | 24.4+ | Logging em todos os novos componentes | Import: `import structlog; logger = structlog.get_logger(__name__)` |
| django | 5.1+ | ORM async, data migrations | `Config.objects.aget(key=...)` via ConfigService |
| langgraph | 1.0.10 | WhatsAppState TypedDict (adicionar `is_new_user`) | Nó `identify_user` retorna dict parcial com `is_new_user` |
| asyncio | stdlib | Debounce timer (create_task + sleep) | `asyncio.create_task()` para fire-and-forget, `asyncio.sleep()` para delay |

### Informações Técnicas Atualizadas (Pesquisa Web — Mar 2026)

#### Redis Async API para Message Buffer (redis-py 5.2+)

```python
# Imports e setup
from workflows.utils.deduplication import _get_redis_client

redis = _get_redis_client()  # Singleton, decode_responses=True

# RPUSH + EXPIRE atômico via pipeline
async with redis.pipeline(transaction=True) as pipe:
    pipe.rpush(f"msg_buffer:{phone}", json.dumps(message_data))
    pipe.expire(f"msg_buffer:{phone}", debounce_ttl + 5)
    await pipe.execute()

# LRANGE + DELETE para processar batch
messages = await redis.lrange(f"msg_buffer:{phone}", 0, -1)
await redis.delete(f"msg_buffer:{phone}")
# Nota: decode_responses=True já retorna strings (não bytes)

# SET timer com TTL
await redis.set(f"msg_timer:{phone}", my_timestamp, ex=debounce_ttl + 5)

# GET timer para verificar last-message-wins
current = await redis.get(f"msg_timer:{phone}")
if current == my_timestamp:
    # Eu sou o timer mais recente → processar
    ...
```

#### WhatsApp Cloud API — Tipos de Mensagem no Webhook

```json
// Sticker
{"type": "sticker", "sticker": {"mime_type": "image/webp", "sha256": "...", "id": "STICKER_ID"}}

// Location
{"type": "location", "location": {"latitude": -23.55, "longitude": -46.63, "name": "...", "address": "..."}}

// Document
{"type": "document", "document": {"filename": "doc.pdf", "mime_type": "application/pdf", "id": "DOC_ID"}}

// Contacts
{"type": "contacts", "contacts": [{"name": {"formatted_name": "João"}, "phones": [{"phone": "+55..."}]}]}

// Video
{"type": "video", "video": {"mime_type": "video/mp4", "id": "VIDEO_ID"}}
```

**Nota:** O tipo de contato no WhatsApp webhook é `"contacts"` (plural), não `"contact"`.

#### Debounce Service — Padrão Recomendado

```python
# workflows/services/debounce.py
import asyncio
import json
import time
from typing import Any

import structlog

from workflows.services.config_service import ConfigService
from workflows.utils.deduplication import _get_redis_client

logger = structlog.get_logger(__name__)

BUFFER_KEY_PREFIX = "msg_buffer"
TIMER_KEY_PREFIX = "msg_timer"
DEFAULT_DEBOUNCE_TTL = 3

async def _get_debounce_ttl() -> int:
    """Get debounce TTL from config (default 3s)."""
    try:
        return int(await ConfigService.get("debounce_ttl"))
    except Exception:
        return DEFAULT_DEBOUNCE_TTL

async def buffer_message(phone: str, message_data: str, ttl: int) -> None:
    """Buffer message in Redis list with TTL."""
    redis = _get_redis_client()
    key = f"{BUFFER_KEY_PREFIX}:{phone}"
    async with redis.pipeline(transaction=True) as pipe:
        pipe.rpush(key, message_data)
        pipe.expire(key, ttl + 5)  # Safety margin
        await pipe.execute()
    logger.info("message_buffered", phone=phone)

async def get_and_clear_buffer(phone: str) -> list[str]:
    """Get all buffered messages and clear the buffer."""
    redis = _get_redis_client()
    key = f"{BUFFER_KEY_PREFIX}:{phone}"
    messages = await redis.lrange(key, 0, -1)
    await redis.delete(key)
    return messages  # decode_responses=True → already strings

async def schedule_processing(
    phone: str,
    validated_data: dict[str, Any],
    process_callback,  # async callable
) -> None:
    """Buffer message and schedule processing after debounce period."""
    debounce_ttl = await _get_debounce_ttl()

    # 1. Buffer the message
    await buffer_message(phone, json.dumps(validated_data), debounce_ttl)

    # 2. Set timer with our timestamp
    redis = _get_redis_client()
    timer_key = f"{TIMER_KEY_PREFIX}:{phone}"
    my_timestamp = str(time.monotonic_ns())
    await redis.set(timer_key, my_timestamp, ex=debounce_ttl + 5)
    logger.info("debounce_timer_set", phone=phone, ttl=debounce_ttl)

    # 3. Sleep for debounce period
    await asyncio.sleep(debounce_ttl)

    # 4. Check if we're the latest timer
    current = await redis.get(timer_key)
    if current != my_timestamp:
        logger.debug("debounce_timer_superseded", phone=phone)
        return

    # 5. We're the latest → process the batch
    await redis.delete(timer_key)
    raw_messages = await get_and_clear_buffer(phone)

    if not raw_messages:
        logger.warning("debounce_empty_buffer", phone=phone)
        return

    # Combine messages
    messages = [json.loads(m) for m in raw_messages]
    combined_body = "\n".join(m.get("body", "") for m in messages if m.get("body"))
    logger.info(
        "debounce_batch_processing",
        phone=phone,
        message_count=len(messages),
    )

    # Use first message as base, override body with combined
    batch_data = messages[0].copy()
    batch_data["body"] = combined_body or batch_data.get("body", "")

    await process_callback(batch_data)
```

### Pitfalls Conhecidos (Story 1.6)

1. **`time.monotonic_ns()` vs `time.time()`** — Usar `time.monotonic_ns()` para timestamps de timer (mais preciso, monotônico). Mas em multi-instance, `time.time()` + mais dígitos é mais seguro pois `monotonic_ns()` é por-processo. **Usar `f"{time.time():.9f}:{id(asyncio.current_task())}"`** para máxima unicidade entre instâncias.

2. **decode_responses=True** — O Redis client em `_get_redis_client()` usa `decode_responses=True`, então LRANGE retorna `list[str]` (não `list[bytes]`). NÃO fazer `.decode()`.

3. **Pipeline atômico para buffer** — RPUSH + EXPIRE devem ser atômicos via `redis.pipeline(transaction=True)`. Caso contrário, se o processo crash entre RPUSH e EXPIRE, a chave pode ficar sem TTL.

4. **Debounce + dedup** — A deduplicação (`is_duplicate_message`) acontece ANTES do debounce. Isso é correto: se o WhatsApp reenvia a mesma mensagem, ela é ignorada antes de entrar no buffer.

5. **ConfigService pode falhar** — Se o Config model não tem a key (ex: `debounce_ttl` não existe), `ConfigService.get()` levanta `ValidationError`. Usar try/except com fallback para default.

6. **Unsupported message response não deve falhar o webhook** — Se o envio da mensagem informativa falhar, logar ERROR mas NÃO re-raise. O webhook DEVE retornar 200 OK.

7. **Welcome message é best-effort** — Se o envio falhar, logar WARNING mas NÃO bloquear o envio da resposta principal. O aluno não deve perder a resposta do LLM por causa de falha no welcome.

8. **`contacts` (plural) no WhatsApp** — O tipo é `"contacts"` (com 's'), não `"contact"`. Garantir que o UNSUPPORTED_RESPONSE_TYPES inclui `"contacts"`.

9. **initial_state precisa de `is_new_user`** — O `initial_state` em `_process_message()` precisa incluir `"is_new_user": False`. O nó `identify_user` sobrescreve para `True` quando detecta novo user.

10. **Debounce com audio/image** — Quando audio/image são bufferizados junto com texto, o `combined_body` pode ficar parcialmente vazio. O `batch_data` deve preservar o `message_type` do PRIMEIRO tipo não-texto (se houver), ou "text" se todos são texto.

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 1, Story 1.6]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-007 (Redis 4 camadas, Message Buffer)]
- [Source: _bmad-output/planning-artifacts/architecture.md — CacheManager pattern (msg_buffer:{phone})]
- [Source: _bmad-output/planning-artifacts/architecture.md — WhatsApp webhook handling (event filtering)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Config model (message:welcome, message:unsupported_type, debounce_ttl)]
- [Source: _bmad-output/planning-artifacts/architecture.md — StateGraph nodes (identify_user, send_whatsapp)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Enforcement Rules (MUST/MUST NOT)]
- [Source: _bmad-output/planning-artifacts/prd.md — FR6 (debounce), FR7 (unsupported types), FR10 (boas-vindas)]
- [Source: _bmad-output/planning-artifacts/prd.md — NFR5 (debounce ≤ 3s), NFR13 (zero mensagens perdidas), NFR14 (webhook 200 < 3s)]
- [Source: _bmad-output/implementation-artifacts/1-5-formatacao-envio-whatsapp-persistencia.md — Dev Notes, Lessons Learned, Code Review Fixes]
- [Source: workflows/views.py — PROCESSABLE_MESSAGE_TYPES, _process_message(), should_process_event()]
- [Source: workflows/whatsapp/state.py — WhatsAppState TypedDict atual (15 campos)]
- [Source: workflows/whatsapp/graph.py — build_whatsapp_graph() flow linear atual]
- [Source: workflows/whatsapp/nodes/identify_user.py — User.DoesNotExist → acreate (first-time detection)]
- [Source: workflows/utils/deduplication.py — _get_redis_client() singleton, Redis patterns]
- [Source: workflows/services/cache_manager.py — CacheManager pattern (session cache)]
- [Source: workflows/services/config_service.py — ConfigService.get() async]
- [Source: workflows/serializers.py — WhatsAppMessageSerializer (rejeita system, unknown)]
- [Source: workflows/migrations/0002_initial_configs.py — Config keys existentes]
- [Source: redis-py 5.2+ docs — RPUSH, LRANGE, DELETE, EXPIRE, pipeline async]
- [Source: WhatsApp Cloud API docs — Message types (sticker, location, document, contacts, video)]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Pipeline mock fix: redis-py `pipeline()` is synchronous (returns async context manager directly), so mock needed `MagicMock` instead of `AsyncMock`

### Completion Notes List

- Implemented debounce service with Redis buffer + last-message-wins timer pattern (multi-instance safe)
- Integrated debounce into webhook POST: supported types go through `schedule_processing()`, unsupported types get informative message via `_handle_unsupported_message()`
- Added `is_new_user` flag to identify_user node (True for new users, False for existing/cached)
- Added welcome message to send_whatsapp node (sent before main response for new users)
- Created data migration 0003 to update config message texts to match AC specifications
- Updated existing webhook tests to patch `schedule_processing` instead of `_process_message`
- Updated existing graph integration test with debounce bypass pattern
- 18 novos test cases para Story 1.6 (7 debounce + 4 welcome + 7 unsupported types)

### Known Limitations

- **Read receipts no debounce batch:** Quando múltiplas mensagens são acumuladas, apenas a primeira recebe `mark_as_read()`. As demais ficam como "delivered" no WhatsApp do aluno (usa `wamid` do `messages[0]`).
- **Mensagens perdidas em restart:** Se uma instância Cloud Run for killed durante `asyncio.sleep(debounce_ttl)`, mensagens no buffer expiram sem processamento (TTL = debounce_ttl + 5s). Uma solução definitiva requer Cloud Tasks ou fila persistente.

### File List

**New files:**
- `workflows/services/debounce.py` — Debounce service (buffer_message, get_and_clear_buffer, schedule_processing)
- `workflows/migrations/0003_update_config_messages.py` — Update config message texts per ACs
- `tests/test_services/test_debounce.py` — 9 tests for debounce service

**Modified files:**
- `workflows/views.py` — Added SUPPORTED_TYPES, UNSUPPORTED_RESPONSE_TYPES, _handle_unsupported_message, debounce routing, is_new_user in initial_state
- `workflows/whatsapp/state.py` — Added `is_new_user: bool` field
- `workflows/whatsapp/nodes/identify_user.py` — Returns `is_new_user` flag (True/False)
- `workflows/whatsapp/nodes/send_whatsapp.py` — Sends welcome message for new users before main response
- `tests/test_identify_user.py` — Added is_new_user assertions to 3 existing tests
- `tests/test_whatsapp/test_nodes/test_send_whatsapp.py` — Added is_new_user to _make_state, 4 new welcome message tests
- `tests/test_webhook.py` — Updated 6 tests to patch schedule_processing, 7 unsupported type tests, 3 unit tests para _handle_unsupported_message, assertion fix no parametrized test
- `tests/test_graph.py` — Added is_new_user to _make_initial_state, updated integration test with debounce bypass

### Change Log

- **2026-03-08:** Story 1.6 implementation complete — Debounce, boas-vindas, e mensagens não suportadas.
- **2026-03-08:** Code review fixes — Race condition get_and_clear_buffer (Lua script atômico), json.loads error handling, testes unitários para _handle_unsupported_message, assertion faltando em test_unsupported_type_triggers_handler, state.get → state[] em send_whatsapp.
