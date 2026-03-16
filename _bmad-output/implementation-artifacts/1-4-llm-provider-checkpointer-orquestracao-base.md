# Story 1.4: LLM Provider + Checkpointer + Orquestração Base

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a aluno,
I want fazer uma pergunta médica por texto e receber uma resposta contextualizada,
So that resolvo minha dúvida rapidamente sem sair do WhatsApp.

## Acceptance Criteria

### AC1: LLM Provider Factory com Fallback Automático

```gherkin
Given `workflows/providers/llm.py` com `get_model()`
When o provider é inicializado
Then `ChatAnthropicVertex` é o primary (model `claude-sonnet-4@20250514`, streaming=True, max_retries=2)
And `ChatAnthropic` é o fallback com `model.with_fallbacks([fallback])`
And credenciais Vertex usam service_account.Credentials do GCP
```

### AC2: Checkpointer Singleton com AsyncPostgresSaver

```gherkin
Given `workflows/providers/checkpointer.py`
When `get_checkpointer()` é chamado
Then retorna `AsyncPostgresSaver` singleton com `AsyncConnectionPool` (min_size=5, max_size=20, schema=langgraph)
```

### AC3: Nó orchestrate_llm com Cost Tracking

```gherkin
Given o nó `orchestrate_llm` do StateGraph
When processa uma mensagem de texto do aluno
Then invoca o modelo com system prompt + histórico da conversa
And `CostTrackingCallback` registra tokens_input, tokens_output, cache_read, cache_creation via structlog (logs JSON) — persistência no banco (CostLog model) e integração Langfuse são adicionadas na Story 7.1
And a resposta do Claude é adicionada ao estado como `response_text`
```

### AC4: Prompt Caching Manual via cache_control

```gherkin
Given o system prompt em `workflows/whatsapp/prompts/system.py`
When carregado para o LLM via nó orchestrate_llm
Then o system prompt usa `cache_control: {"type": "ephemeral"}` para habilitar Prompt Caching (TTL 5min)
And o CostTrackingCallback diferencia tokens normais de cache_read e cache_creation
```

### AC5: StateGraph Completo com Checkpointer e Semaphore

```gherkin
Given o StateGraph completo (`build_whatsapp_graph()`)
When compilado com checkpointer
Then usa `thread_id = phone_number` para persistência automática de conversa
And concurrency é controlada por `asyncio.Semaphore(50)` (NFR4)
And o grafo inclui: START → identify_user → load_context → orchestrate_llm → END
```

## Tasks / Subtasks

- [x] Task 1: Criar `get_model()` em `workflows/providers/llm.py` (AC: #1)
  - [x] 1.1 Criar `workflows/providers/llm.py`
  - [x] 1.2 Implementar `ChatVertexAI` como primary (`claude-sonnet-4@20250514`, streaming=True, max_retries=2) — Nota: `ChatAnthropicVertex` foi unificado em `ChatVertexAI` no langchain-google-vertexai 3.2.2
  - [x] 1.3 Implementar `ChatAnthropic` como fallback (`claude-sonnet-4-20250514`, streaming=True, max_retries=2)
  - [x] 1.4 Combinar com `primary.with_fallbacks([fallback])`
  - [x] 1.5 Credenciais Vertex via `service_account.Credentials.from_service_account_info()` carregadas de settings
  - [x] 1.6 Parâmetros configuráveis: `temperature` (default 0), `max_tokens` (default 2048)

- [x] Task 2: Criar `get_checkpointer()` em `workflows/providers/checkpointer.py` (AC: #2)
  - [x] 2.1 Criar `workflows/providers/checkpointer.py`
  - [x] 2.2 Implementar `AsyncConnectionPool` singleton (conninfo de settings, min_size=5, max_size=20)
  - [x] 2.3 Configurar kwargs: `autocommit=True`, `row_factory=dict_row`, `options="-c search_path=langgraph,public"`
  - [x] 2.4 Chamar `await pool.open()` na primeira inicialização
  - [x] 2.5 Retornar `AsyncPostgresSaver(conn=pool)`
  - [x] 2.6 Implementar `setup_checkpointer()` para criar tabelas (chamado no startup)

- [x] Task 3: Criar system prompt em `workflows/whatsapp/prompts/system.py` (AC: #4)
  - [x] 3.1 Criar `workflows/whatsapp/prompts/system.py`
  - [x] 3.2 Implementar `get_system_prompt()` que retorna conteúdo do system prompt como string
  - [x] 3.3 System prompt em português com persona "Medbrain, tutor médico da Medway"
  - [x] 3.4 Incluir regras de citação: `[N]` para RAG, `[W-N]` para web (placeholder para Story 2.x)
  - [x] 3.5 Incluir regra: nunca citar da memória/treinamento
  - [x] 3.6 Incluir regra: nunca recomendar concorrentes
  - [x] 3.7 Incluir disclaimer médico obrigatório
  - [x] 3.8 Implementar `build_system_message()` que retorna SystemMessage com `cache_control` para Prompt Caching

- [x] Task 4: Criar `CostTrackingCallback` em `workflows/services/cost_tracker.py` (AC: #3)
  - [x] 4.1 Criar `workflows/services/cost_tracker.py`
  - [x] 4.2 Implementar `CostTrackingCallback(AsyncCallbackHandler)` com `on_llm_end()`
  - [x] 4.3 Extrair `usage_metadata` de `response.generations[0][0].message.usage_metadata`
  - [x] 4.4 Acumular: `input_tokens`, `output_tokens`, `cache_read`, `cache_creation`
  - [x] 4.5 Calcular custo com pricing Vertex AI: input $3.00/MTok, cache_read $0.30/MTok, cache_creation $3.75/MTok, output $15.00/MTok
  - [x] 4.6 Logar via structlog: `cost_tracked` com todos os campos de custo (JSON)
  - [x] 4.7 Expor método `get_cost_summary()` para uso no estado do grafo
  - [x] 4.8 NÃO persistir no banco nesta story (CostLog persistência = Story 7.1)

- [x] Task 5: Criar nó `orchestrate_llm` (AC: #3, #4)
  - [x] 5.1 Criar `workflows/whatsapp/nodes/orchestrate_llm.py`
  - [x] 5.2 Implementar `async def orchestrate_llm(state: WhatsAppState) -> dict`
  - [x] 5.3 Chamar `get_model()` para obter LLM com fallback
  - [x] 5.4 Construir mensagens: `build_system_message()` + `state["messages"]` + `HumanMessage(state["user_message"])`
  - [x] 5.5 Criar `CostTrackingCallback` e passar via `config={"callbacks": [cost_tracker]}`
  - [x] 5.6 Invocar `await model.ainvoke(messages, config=config)`
  - [x] 5.7 Extrair `response.content` como texto da resposta
  - [x] 5.8 Logar custo via `cost_tracker.get_cost_summary()` + structlog
  - [x] 5.9 Retornar dict parcial: `{"messages": [response], "cost_usd": cost_summary["cost_usd"]}`

- [x] Task 6: Atualizar `build_whatsapp_graph()` com checkpointer e orchestrate_llm (AC: #5)
  - [x] 6.1 Adicionar nó `orchestrate_llm` ao StateGraph
  - [x] 6.2 Atualizar edges: `START → identify_user → load_context → orchestrate_llm → END`
  - [x] 6.3 Atualizar `get_graph()` para aceitar checkpointer: `builder.compile(checkpointer=checkpointer)`
  - [x] 6.4 Implementar `asyncio.Semaphore(50)` no dispatch (`_process_message()` em views.py)
  - [x] 6.5 Atualizar `_process_message()` para chamar `get_checkpointer()` e passar ao grafo

- [x] Task 7: Configurar settings para novos providers (AC: #1, #2)
  - [x] 7.1 Adicionar em `config/settings/base.py`: `VERTEX_PROJECT_ID`, `VERTEX_LOCATION`, `GCP_CREDENTIALS`
  - [x] 7.2 Adicionar: `ANTHROPIC_API_KEY`
  - [x] 7.3 Atualizar `.env.example` com novas variáveis
  - [x] 7.4 Atualizar `config/settings/test.py` overrides para testes (mock credentials)

- [x] Task 8: Testes (TODOS os ACs)
  - [x] 8.1 Criar `tests/test_providers/test_llm.py`
  - [x] 8.2 Teste: `get_model()` retorna RunnableWithFallbacks (AC1)
  - [x] 8.3 Teste: primary é ChatVertexAI com params corretos (AC1)
  - [x] 8.4 Teste: fallback é ChatAnthropic com params corretos (AC1)
  - [x] 8.5 Criar `tests/test_providers/test_checkpointer.py`
  - [x] 8.6 Teste: `get_checkpointer()` retorna AsyncPostgresSaver (AC2)
  - [x] 8.7 Teste: singleton — segunda chamada retorna mesma instância (AC2)
  - [x] 8.8 Teste: pool configurado com autocommit=True e row_factory=dict_row (AC2)
  - [x] 8.9 Criar `tests/test_services/test_cost_tracker.py`
  - [x] 8.10 Teste: `on_llm_end` extrai usage_metadata corretamente (AC3)
  - [x] 8.11 Teste: cálculo de custo com pricing Vertex AI está correto (AC3)
  - [x] 8.12 Teste: cache_read e cache_creation são diferenciados (AC4)
  - [x] 8.13 Teste: loga custo via structlog (AC3)
  - [x] 8.14 Criar `tests/test_whatsapp/test_nodes/test_orchestrate_llm.py`
  - [x] 8.15 Teste: nó invoca modelo com system prompt + histórico (AC3)
  - [x] 8.16 Teste: resposta do LLM é adicionada ao estado como messages (AC3)
  - [x] 8.17 Teste: cost_usd é calculado e retornado no estado (AC3)
  - [x] 8.18 Atualizar `tests/test_graph.py`
  - [x] 8.19 Teste: grafo executa identify_user → load_context → orchestrate_llm → END (AC5)
  - [x] 8.20 Teste: grafo compilado com checkpointer aceita thread_id (AC5)
  - [x] 8.21 Teste: semaphore limita concorrência a 50 (AC5)

## Dev Notes

### Contexto de Negócio
- Story 1.4 é o **coração do pipeline**: conecta a identificação de usuário (1.3) à geração de resposta do LLM
- Esta story implementa o **primeiro contato funcional aluno↔LLM** — após esta story, o sistema gera respostas (sem formatação/envio, que são Story 1.5)
- O `CostTrackingCallback` faz tracking via logs (structlog JSON) nesta fase; persistência no banco (`CostLog` model) e integração Langfuse são adicionadas na Story 7.1
- O system prompt é a **primeira versão** — será enriquecido com regras de tools nas Stories 2.x

### Padrões Obrigatórios (Estabelecidos nas Stories 1.1, 1.2, 1.3)
- **SEMPRE** async/await para I/O (NUNCA bloqueante)
- **Django ORM async**: `aget()`, `acreate()` — `afilter()` NÃO existe, usar `.filter()` com async iteration
- **Type hints** em TODAS as funções
- **structlog** para logging (NUNCA `print()`)
- **AppError hierarchy** para exceções (usar `GraphNodeError` para falhas em nós, `ExternalServiceError` para falhas de provider)
- **Import order**: Standard → Third-party → Local
- **NUNCA** `import *`, sync I/O, commitar secrets, logar PII sem sanitização
- **Nomes**: snake_case (arquivos, funções, variáveis), PascalCase (classes), UPPER_SNAKE_CASE (constantes)
- **LangGraph node contract**: funções async puras → `async def node_name(state: WhatsAppState) -> dict`
- **Retorno parcial**: nós SEMPRE retornam `dict` parcial (apenas campos alterados), NUNCA o estado completo

### Infraestrutura Já Disponível (Stories 1.1, 1.2, 1.3 — NÃO RECRIAR)
- `workflows/models.py` — User, Message, Config, ConfigHistory (NÃO tem CostLog ainda — será Story 7.1)
- `workflows/utils/errors.py` — AppError, ValidationError, AuthenticationError, RateLimitError, ExternalServiceError, GraphNodeError
- `workflows/utils/sanitization.py` — PII redaction processor para structlog
- `workflows/utils/deduplication.py` — Redis singleton `_get_redis_client()` + `is_duplicate_message()`
- `workflows/services/config_service.py` — ConfigService.get() async
- `workflows/services/cache_manager.py` — CacheManager (session cache Redis, TTL 1h)
- `workflows/middleware/webhook_signature.py` — HMAC SHA-256 validation
- `workflows/middleware/trace_id.py` — UUID trace_id + structlog contextvars
- `workflows/views.py` — WhatsAppWebhookView (GET handshake + POST fire-and-forget com `_process_message()`)
- `workflows/serializers.py` — WhatsAppMessageSerializer
- `workflows/whatsapp/state.py` — WhatsAppState TypedDict (15 campos, `add_messages` reducer)
- `workflows/whatsapp/graph.py` — `build_whatsapp_graph()` (START → identify_user → load_context → END) + `get_graph()` singleton
- `workflows/whatsapp/nodes/identify_user.py` — Nó identify_user (busca/cria User, cache)
- `workflows/whatsapp/nodes/load_context.py` — Nó load_context (últimas 20 msgs, LangChain conversion)
- `workflows/whatsapp/prompts/__init__.py` — Existe mas VAZIO
- `workflows/whatsapp/tools/__init__.py` — Existe mas VAZIO
- `workflows/providers/__init__.py` — Existe mas VAZIO
- `config/settings/base.py` — REDIS_URL, WHATSAPP_WEBHOOK_SECRET, middlewares, structlog
- 84 testes passando (Stories 1.1, 1.2, 1.3)

### Inteligência da Story Anterior (1-3)

**Lições aprendidas:**
- Django `AsyncClient` em testes: usar `headers={}` dict (Django 5.2+) em vez de `HTTP_*` kwargs
- Redis precisa de connection pooling (singleton) — NÃO criar conexão nova por request
- Cache key consistency é CRITICAL — Story 1.3 teve bug de cache key mismatch (phone vs user_id) que passou despercebido por over-mocking. Testar com assertions de consistência
- Event filtering: processar TODOS os elementos dos arrays
- `@pytest.mark.django_db` requer `transaction=True` para isolamento quando há campos unique
- `afilter()` NÃO existe no Django ORM — usar `.filter()` com `async for`
- LangChain messages import de `langchain_core.messages`: HumanMessage, AIMessage, AnyMessage

**Padrões de código estabelecidos:**
- Middleware: async-capable dual-mode
- Views: `adrf.views.APIView` com `async def post()/get()`
- Nós LangGraph: `async def node_name(state: WhatsAppState) -> dict` retornando dict parcial
- Testes: `@pytest.mark.django_db(transaction=True)` + mocks com `AsyncMock`
- Singleton Redis: reusar `_get_redis_client()` de `deduplication.py`
- Graph: `get_graph()` singleton via `build_whatsapp_graph().compile()`

**Arquivos criados na Story 1.3 que impactam Story 1.4:**
- `workflows/whatsapp/graph.py` — Contém `build_whatsapp_graph()` e `get_graph()` que DEVEM ser estendidos (adicionar orchestrate_llm, checkpointer)
- `workflows/whatsapp/state.py` — WhatsAppState com `messages: Annotated[list[AnyMessage], add_messages]` já definido
- `workflows/views.py` — `_process_message()` invoca o grafo com `thread_id=phone` — DEVE ser atualizado para usar checkpointer e semaphore

### Project Structure Notes

#### Arquivos a Criar
```
workflows/
├── providers/
│   ├── llm.py                        # CRIAR — get_model() com ChatAnthropicVertex + fallback
│   └── checkpointer.py               # CRIAR — get_checkpointer() com AsyncPostgresSaver singleton
├── services/
│   └── cost_tracker.py               # CRIAR — CostTrackingCallback (AsyncCallbackHandler)
└── whatsapp/
    ├── nodes/
    │   └── orchestrate_llm.py        # CRIAR — nó orchestrate_llm
    └── prompts/
        └── system.py                 # CRIAR — get_system_prompt() + build_system_message()

tests/
├── test_providers/
│   ├── test_llm.py                   # CRIAR — Testes do LLM provider
│   └── test_checkpointer.py          # CRIAR — Testes do checkpointer
├── test_services/
│   └── test_cost_tracker.py          # CRIAR — Testes do CostTrackingCallback
└── test_whatsapp/
    └── test_nodes/
        └── test_orchestrate_llm.py   # CRIAR — Testes do nó orchestrate_llm
```

#### Arquivos a Modificar
```
workflows/
├── whatsapp/
│   ├── graph.py                      # MODIFICAR — Adicionar orchestrate_llm, checkpointer
│   └── nodes/
│       └── __init__.py               # MODIFICAR — Exportar orchestrate_llm
├── views.py                          # MODIFICAR — Adicionar semaphore + checkpointer no dispatch
config/
├── settings/
│   └── base.py                       # MODIFICAR — Adicionar variáveis de Vertex AI, Anthropic
.env.example                          # MODIFICAR — Adicionar novas variáveis

tests/
└── test_graph.py                     # MODIFICAR — Atualizar testes para novo flow com orchestrate_llm
```

### Guardrails de Arquitetura

#### ADRs Aplicáveis
| ADR | Decisão | Impacto nesta Story |
|-----|---------|---------------------|
| ADR-003 | Django ORM (não supabase-py) | CostLog NÃO é criado nesta story (Story 7.1) |
| ADR-005 | GCP Cloud Run | Credenciais via service_account + GCP Secret Manager |
| ADR-006 | Vertex AI Primary + Anthropic Direct Fallback | `get_model()` com `with_fallbacks()` |
| ADR-007 | Redis 4 camadas | Session cache já implementado (Story 1.3) |
| ADR-009 | App `workflows/` | Providers em `workflows/providers/`, nodes em `workflows/whatsapp/nodes/` |
| ADR-010 | LangGraph + LangChain 1.0 | StateGraph, AsyncPostgresSaver, CostTrackingCallback |

#### Requisitos Não-Funcionais (NFR)
| NFR | Requisito | Como Implementar |
|-----|-----------|------------------|
| NFR1 | Latência P95 < 8s (texto) | Prompt Caching (cache_control), streaming=True, retry com backoff |
| NFR4 | 50 conversas concorrentes | `asyncio.Semaphore(50)` no `_process_message()` |
| NFR6 | Custo/conversa < $0.03 | Prompt Caching reduz ~90% custo de input; CostTrackingCallback monitora |
| NFR7 | Cache hit rate > 70% (M1) | cache_control ephemeral no system prompt (TTL 5min) |
| NFR8 | Cost tracking ±5% precisão | CostTrackingCallback com pricing atualizado Vertex AI |
| NFR13 | Nenhuma mensagem perdida | Exception handling no orchestrate_llm, fallback para mensagem de erro |
| NFR17 | Credenciais em env vars | `VERTEX_PROJECT_ID`, `VERTEX_LOCATION`, `ANTHROPIC_API_KEY` via django-environ |

### Libraries/Frameworks — Versões e Padrões Atualizados

| Lib | Versão | Uso nesta Story | Notas Importantes |
|-----|--------|----------------|-------------------|
| langchain-anthropic | 1.3.4 | ChatAnthropic fallback | Import: `from langchain_anthropic import ChatAnthropic` |
| langchain-google-vertexai | 3.2.2 | ChatAnthropicVertex primary | Import: `from langchain_google_vertexai import ChatAnthropicVertex` |
| langgraph | 1.0.10 | StateGraph, RetryPolicy | Import RetryPolicy: `from langgraph.types import RetryPolicy` |
| langgraph-checkpoint-postgres | 3.0.4 | AsyncPostgresSaver | Import: `from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver` |
| psycopg-pool | 3.3.0 | AsyncConnectionPool | Import: `from psycopg_pool import AsyncConnectionPool` |
| psycopg | 3.x | Row factory | Import: `from psycopg.rows import dict_row` |
| langchain-core | 1.2.17 | AsyncCallbackHandler, messages | Import: `from langchain_core.callbacks.base import AsyncCallbackHandler` |
| google-auth | latest | service_account.Credentials | Import: `from google.oauth2 import service_account` |

### Informações Técnicas Atualizadas (Pesquisa Web — Mar 2026)

#### ChatAnthropicVertex — Parâmetros Corretos
```python
from langchain_google_vertexai import ChatAnthropicVertex

primary = ChatAnthropicVertex(
    model_name="claude-sonnet-4@20250514",   # Vertex usa @ como separador
    project=settings.VERTEX_PROJECT_ID,
    location=settings.VERTEX_LOCATION,       # ex: "us-east5"
    max_output_tokens=2048,
    temperature=0,
    streaming=True,
    max_retries=2,
    # credentials= opcionalmente, senão usa Application Default Credentials
)
```

#### ChatAnthropic — Parâmetros Corretos
```python
from langchain_anthropic import ChatAnthropic

fallback = ChatAnthropic(
    model="claude-sonnet-4-20250514",        # Anthropic Direct usa - como separador
    api_key=settings.ANTHROPIC_API_KEY,
    max_tokens=2048,
    temperature=0,
    streaming=True,
    max_retries=2,
    stream_usage=True,                       # Inclui usage_metadata no streaming
)
```

#### AsyncPostgresSaver — Configuração CRITICAL
```python
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

pool = AsyncConnectionPool(
    conninfo=settings.DATABASE_URL,
    min_size=5,
    max_size=20,
    kwargs={
        "autocommit": True,        # OBRIGATÓRIO — sem isso, setup() falha silenciosamente
        "row_factory": dict_row,   # OBRIGATÓRIO — checkpointer acessa rows como dicts
        "options": "-c search_path=langgraph,public",  # Schema separado
    },
    open=False,  # Abrir manualmente com await pool.open()
)
await pool.open()

checkpointer = AsyncPostgresSaver(conn=pool)
await checkpointer.setup()  # Cria tabelas de checkpoint
```

#### CostTrackingCallback — Acesso a usage_metadata
```python
from langchain_core.callbacks.base import AsyncCallbackHandler
from langchain_core.outputs import LLMResult
import structlog

logger = structlog.get_logger()

class CostTrackingCallback(AsyncCallbackHandler):
    """Rastreia custo de cada chamada LLM via usage_metadata."""

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        self.total_input = 0
        self.total_output = 0
        self.cache_read = 0
        self.cache_creation = 0

    async def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        for gen_list in response.generations:
            for gen in gen_list:
                msg = getattr(gen, "message", None)
                if msg and hasattr(msg, "usage_metadata") and msg.usage_metadata:
                    meta = msg.usage_metadata
                    self.total_input += meta.get("input_tokens", 0)
                    self.total_output += meta.get("output_tokens", 0)
                    details = meta.get("input_token_details", {})
                    self.cache_read += details.get("cache_read", 0)
                    self.cache_creation += details.get("cache_creation", 0)

    def get_cost_summary(self) -> dict:
        """Calcula custo com pricing Vertex AI."""
        base_input = self.total_input - self.cache_read - self.cache_creation
        cost_usd = (
            base_input * 3.00 / 1_000_000
            + self.cache_read * 0.30 / 1_000_000
            + self.cache_creation * 3.75 / 1_000_000
            + self.total_output * 15.00 / 1_000_000
        )
        return {
            "input_tokens": self.total_input,
            "output_tokens": self.total_output,
            "cache_read_tokens": self.cache_read,
            "cache_creation_tokens": self.cache_creation,
            "cost_usd": round(cost_usd, 6),
        }
```

#### Prompt Caching Manual (NÃO usar AnthropicPromptCachingMiddleware)
```python
# ATENÇÃO: AnthropicPromptCachingMiddleware requer create_agent() e NÃO funciona
# com StateGraph manual. Usar cache_control diretamente nas mensagens.

from langchain_core.messages import SystemMessage

def build_system_message() -> SystemMessage:
    """Constrói SystemMessage com cache_control para Prompt Caching."""
    return SystemMessage(
        content=[
            {
                "type": "text",
                "text": get_system_prompt(),  # System prompt longo
                "cache_control": {"type": "ephemeral"},  # TTL 5min
            }
        ]
    )
```

#### RetryPolicy no LangGraph — Import Correto
```python
from langgraph.types import RetryPolicy  # Canonical import

# Usage no graph builder
builder.add_node(
    "orchestrate_llm",
    orchestrate_llm,
    retry=RetryPolicy(max_attempts=3, backoff_factor=2.0),
)
```

#### usage_metadata — Estrutura Completa
```python
# AIMessage.usage_metadata retornado pelo ChatAnthropic / ChatAnthropicVertex
{
    "input_tokens": 1500,           # Total tokens de input
    "output_tokens": 350,           # Total tokens de output
    "total_tokens": 1850,           # Soma
    "input_token_details": {
        "cache_creation": 0,        # Tokens usados para criar cache (cache miss)
        "cache_read": 1458,         # Tokens lidos do cache (cache hit — 10% do custo)
    },
    "output_token_details": {
        "reasoning": 0,             # Tokens de raciocínio/thinking
    },
}
```

#### Pitfalls Conhecidos (Pesquisa Web Mar 2026)
1. **AsyncPostgresSaver requer `autocommit=True` E `row_factory=dict_row`** nos kwargs do pool — sem isso, `setup()` falha silenciosamente e não cria tabelas
2. **`AnthropicPromptCachingMiddleware` NÃO funciona com StateGraph manual** — requer `create_agent()`. Para mb-wpp, usar `cache_control` diretamente nas mensagens
3. **`usage_metadata` vive no `AIMessage`**, não no `LLMResult` — acessar via `response.generations[0][0].message.usage_metadata`
4. **Streaming com cache pode double-count tokens** — verificar que `cache_read` e `cache_creation` não estão inflados no modo streaming
5. **`with_fallbacks()` + cache_control**: funciona SEM problemas quando ambos providers são Anthropic (ChatAnthropicVertex + ChatAnthropic)
6. **Model name format**: Vertex usa `@` (`claude-sonnet-4@20250514`), Anthropic Direct usa `-` (`claude-sonnet-4-20250514`)
7. **psycopg_pool 3.3**: `conninfo` e `kwargs` podem ser callables — útil para rotação de credenciais em Cloud Run

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 1, Story 1.4]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-006 (Multi-Provider LLM Strategy)]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-010 (LangGraph + LangChain)]
- [Source: _bmad-output/planning-artifacts/architecture.md — AsyncPostgresSaver checkpointing]
- [Source: _bmad-output/planning-artifacts/architecture.md — CostTrackingCallback pattern]
- [Source: _bmad-output/planning-artifacts/architecture.md — get_model() factory function]
- [Source: _bmad-output/planning-artifacts/architecture.md — AnthropicPromptCachingMiddleware]
- [Source: _bmad-output/planning-artifacts/architecture.md — WhatsAppState TypedDict]
- [Source: _bmad-output/planning-artifacts/architecture.md — asyncio.Semaphore(50) concurrency]
- [Source: _bmad-output/planning-artifacts/prd.md — FR1, FR27, FR28 (Q&A, Contexto, Histórico)]
- [Source: _bmad-output/planning-artifacts/prd.md — NFR1 (Latência P95 < 8s)]
- [Source: _bmad-output/planning-artifacts/prd.md — NFR4 (50 conversas concorrentes)]
- [Source: _bmad-output/planning-artifacts/prd.md — NFR6-NFR8 (Custo e Prompt Caching)]
- [Source: _bmad-output/implementation-artifacts/1-3-identificacao-usuario-carregamento-contexto.md — Dev Notes, Code Review, Lessons Learned]
- [Source: langchain-anthropic 1.3.4 — ChatAnthropic, with_fallbacks(), usage_metadata]
- [Source: langchain-google-vertexai 3.2.2 — ChatAnthropicVertex constructor, prompt caching support]
- [Source: langgraph 1.0.10 — StateGraph API, RetryPolicy, compile()]
- [Source: langgraph-checkpoint-postgres 3.0.4 — AsyncPostgresSaver, setup(), pool requirements]
- [Source: psycopg-pool 3.3.0 — AsyncConnectionPool, autocommit, row_factory, search_path]
- [Source: langchain-core 1.2.17 — AsyncCallbackHandler, LLMResult, UsageMetadata]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

N/A — Implementação direta sem erros bloqueantes persistentes.

### Completion Notes List

1. **ChatAnthropicVertex → ChatVertexAI**: A classe `ChatAnthropicVertex` NÃO existe no `langchain-google-vertexai` 3.2.2. Foi unificada em `ChatVertexAI`, que suporta modelos Claude no Vertex AI via google.genai SDK. Implementação usa `ChatVertexAI(model_name="claude-sonnet-4@20250514", ...)`.
2. **RetryPolicy `retry` → `retry_policy`**: No LangGraph 1.0.10, o parâmetro `retry=` está deprecado em `add_node()`. Usar `retry_policy=RetryPolicy(...)`.
3. **LLMResult Pydantic validation**: Em testes, `LLMResult(generations=[[MagicMock()]])` falha com Pydantic v2. Usar `ChatGeneration(message=AIMessage(...))` em vez de MagicMock.
4. **LangGraph checkpointer validation**: `MagicMock()` como checkpointer falha `isinstance(checkpointer, BaseCheckpointSaver)`. Testes usam `InMemorySaver()`.
5. **109 testes passando** (25 novos + 84 existentes), zero regressões.
6. **Ruff linter clean** — todos os issues de import ordering e variáveis não usadas corrigidos.

### File List

**Arquivos Criados:**
- `workflows/providers/llm.py` — get_model() factory com ChatVertexAI + ChatAnthropic fallback
- `workflows/providers/checkpointer.py` — get_checkpointer() singleton com AsyncPostgresSaver
- `workflows/whatsapp/prompts/system.py` — get_system_prompt() + build_system_message() com cache_control
- `workflows/services/cost_tracker.py` — CostTrackingCallback (AsyncCallbackHandler) com pricing Vertex AI
- `workflows/whatsapp/nodes/orchestrate_llm.py` — Nó orchestrate_llm do StateGraph
- `tests/test_providers/test_llm.py` — 6 testes para get_model()
- `tests/test_providers/test_checkpointer.py` — 5 testes para get_checkpointer()
- `tests/test_services/test_cost_tracker.py` — 6 testes para CostTrackingCallback
- `tests/test_whatsapp/test_nodes/__init__.py` — Package init
- `tests/test_whatsapp/test_nodes/test_orchestrate_llm.py` — 5 testes para orchestrate_llm

**Arquivos Modificados:**
- `workflows/whatsapp/graph.py` — Adicionado orchestrate_llm node, RetryPolicy, checkpointer param, get_graph() async
- `workflows/whatsapp/nodes/__init__.py` — Export orchestrate_llm
- `workflows/views.py` — asyncio.Semaphore(50), await get_graph()
- `config/settings/base.py` — VERTEX_PROJECT_ID, VERTEX_LOCATION, GCP_CREDENTIALS, ANTHROPIC_API_KEY
- `config/settings/test.py` — Mock credentials para testes
- `.env.example` — Novas variáveis GCP_CREDENTIALS, VERTEX_LOCATION
- `tests/test_graph.py` — Atualizado para 7 testes: mocks orchestrate_llm, async get_graph, checkpointer, semaphore

### Change Log

| Data | Mudança | Motivo |
|------|---------|--------|
| 2026-03-07 | Implementação completa de todos os 8 tasks e 46 subtasks | Story 1.4 — LLM Provider + Checkpointer + Orquestração Base |
| 2026-03-07 | ChatAnthropicVertex substituído por ChatVertexAI | Classe unificada no langchain-google-vertexai 3.2.2 |
| 2026-03-07 | `retry=` substituído por `retry_policy=` em add_node() | Deprecação no LangGraph 1.0.10 |
| 2026-03-07 | **Code Review (AI):** 10 issues encontrados (2C, 3H, 3M, 2L), 8 corrigidos | Review adversarial — todos CRITICAL e HIGH resolvidos |
| 2026-03-07 | Fix C1: `DATABASES["default"]["OPTIONS"]` → `.get("OPTIONS", {})` em checkpointer.py | KeyError impedia inicialização do checkpointer |
| 2026-03-07 | Fix C2: HumanMessage adicionada ao retorno de orchestrate_llm | Histórico de conversação via checkpointer estava perdendo mensagens do usuário |
| 2026-03-07 | Fix H1: `get_model()` agora é singleton para params default | Evita re-instanciação de clients e re-parse de credenciais a cada request |
| 2026-03-07 | Fix H2: `base_input = max(0, ...)` em cost_tracker | Previne custo negativo se cache tokens > total_input |
| 2026-03-07 | Fix H3: Exception handling refinado em orchestrate_llm | Erros de programação não são mais retentados pelo RetryPolicy |
| 2026-03-07 | Fix M1-M3: Testes corrigidos (checkpointer real, race condition, pool cleanup) | Qualidade e confiabilidade dos testes |
