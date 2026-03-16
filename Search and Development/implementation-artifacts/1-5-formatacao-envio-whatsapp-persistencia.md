# Story 1.5: Formatação, Envio WhatsApp e Persistência

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a aluno,
I want receber respostas bem formatadas no WhatsApp com disclaimer médico,
So that a informação é fácil de ler e eu sei que é ferramenta de apoio.

## Acceptance Criteria

### AC1: Nó format_response — Conversão Markdown → WhatsApp + Validação de Citações

```gherkin
Given o nó `format_response` do StateGraph
When processa uma resposta do Claude (conteúdo do último AIMessage em state["messages"])
Then converte markdown para formato otimizado para WhatsApp (negrito, itálico, listas)
And aplica `validate_citations()` para strip de marcadores `[N]` sem fonte real correspondente (no-op quando não há ferramentas ativas — sem tools = sem citações para validar)
And aplica `strip_competitor_citations()` como última camada de defesa (no-op quando não há ferramentas ativas)
And adiciona disclaimer médico quando relevante (FR17)
And adapta formato ao tipo de conteúdo: explicação, cálculo, lista, comparação (FR19)
And retorna dict parcial com `formatted_response` (string formatada para WhatsApp)
```

### AC2: Split de Mensagens Longas

```gherkin
Given uma resposta que excede 4096 caracteres (limite WhatsApp Cloud API)
When o format_response processa
Then divide em mensagens sequenciais mantendo coerência e formatação (FR8)
And o campo `formatted_response` contém a primeira parte
And um novo campo `additional_responses` contém as partes extras como lista de strings
And cada parte respeita o limite de 4096 caracteres
And a divisão acontece em quebras naturais (parágrafo, lista, frase) — nunca no meio de uma palavra
```

### AC3: Nó send_whatsapp — Envio via WhatsApp Cloud API

```gherkin
Given o nó `send_whatsapp` do StateGraph
When processa a resposta formatada
Then envia typing indicator (mark as read com wamid) antes da resposta (FR9)
And envia `formatted_response` via WhatsApp Cloud API (POST graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages)
And se houver `additional_responses`, envia cada parte sequencialmente
And usa httpx AsyncClient com timeout de 10 segundos
And loga delivery status via structlog
And retorna dict parcial com `response_sent: True`
```

### AC4: Nó send_whatsapp — Retry via RetryPolicy

```gherkin
Given o nó send_whatsapp registrado no StateGraph com RetryPolicy
When a WhatsApp Cloud API retorna erro 429 (rate limit) ou 5xx (server error)
Then o RetryPolicy do LangGraph faz retry com backoff exponencial (max_attempts=3, backoff_factor=2.0)
And erros são logados com contexto: phone, message_id, status_code, trace_id
```

### AC5: Nó persist — Persistência de Mensagens via Django ORM

```gherkin
Given o nó `persist` do StateGraph
When processa após o envio
Then salva mensagem do usuário via `Message.objects.acreate(user=user, content=user_message, role="user", message_type=...)`
And salva resposta do assistente via `Message.objects.acreate(user=user, content=formatted_response, role="assistant", cost_usd=...)`
And loga `data_persisted` com user_id via structlog
And retorna dict parcial (sem alterações de estado necessárias)
```

### AC6: WhatsApp Cloud API Client

```gherkin
Given `workflows/providers/whatsapp.py` com WhatsApp client
When inicializado
Then usa httpx.AsyncClient com base_url `https://graph.facebook.com/v21.0`
And usa Bearer token de settings.WHATSAPP_ACCESS_TOKEN para autenticação
And PHONE_NUMBER_ID vem de settings.WHATSAPP_PHONE_NUMBER_ID
And expõe métodos: `send_text_message(phone, text)`, `mark_as_read(wamid)`
```

### AC7: Disclaimer Médico

```gherkin
Given uma resposta que contém informações médicas
When o format_response processa
Then adiciona ao final: "⚕️ _Sou uma ferramenta de apoio ao estudo. Sempre consulte um profissional de saúde para decisões clínicas._"
And o disclaimer NÃO é adicionado quando a resposta é apenas uma saudação ou conversa casual
```

## Tasks / Subtasks

- [x] Task 1: Criar `workflows/providers/whatsapp.py` — WhatsApp Cloud API client (AC: #3, #6)
  - [x] 1.1 Criar `workflows/providers/whatsapp.py`
  - [x] 1.2 Implementar `_get_whatsapp_client()` singleton com httpx.AsyncClient (base_url, headers Bearer token)
  - [x] 1.3 Implementar `send_text_message(phone: str, text: str) -> dict` — POST para /{PHONE_NUMBER_ID}/messages
  - [x] 1.4 Implementar `mark_as_read(wamid: str) -> bool` — POST com `status: "read"` para typing indicator
  - [x] 1.5 Configurar timeout de 10s (NFR: WhatsApp Cloud API timeout)
  - [x] 1.6 Tratar erros: httpx.HTTPStatusError, httpx.TimeoutException → ExternalServiceError
  - [x] 1.7 Logar envio via structlog: `whatsapp_message_sent` e `whatsapp_message_read_marked`

- [x] Task 2: Criar `workflows/utils/formatters.py` — Markdown → WhatsApp (AC: #1, #7)
  - [x] 2.1 Criar `workflows/utils/formatters.py`
  - [x] 2.2 Implementar `markdown_to_whatsapp(text: str) -> str` — converter markdown para formato WhatsApp
    - `**bold**` → `*bold*` (WhatsApp usa asterisco simples)
    - `*italic*` ou `_italic_` → `_italic_`
    - `~~strike~~` → `~strike~`
    - `` `code` `` → `` `code` `` (mantém)
    - ` ```code block``` ` → `` ```code block``` `` (mantém)
    - `# Header` → `*Header*` (bold, sem heading nativo)
    - `- item` → `• item` (bullet point Unicode)
    - `1. item` → `1. item` (mantém)
    - Links `[text](url)` → `text (url)` (WhatsApp não suporta links inline)
  - [x] 2.3 Implementar `should_add_disclaimer(text: str) -> bool` — heurística para detectar conteúdo médico
  - [x] 2.4 Implementar `add_medical_disclaimer(text: str) -> str` — adiciona disclaimer ao final
  - [x] 2.5 Implementar `detect_content_type(text: str) -> str` — detecta tipo: "explanation", "calculation", "list", "comparison", "greeting"

- [x] Task 3: Criar `workflows/utils/message_splitter.py` — Split de mensagens longas (AC: #2)
  - [x] 3.1 Criar `workflows/utils/message_splitter.py`
  - [x] 3.2 Implementar `split_message(text: str, max_length: int = 4096) -> list[str]`
  - [x] 3.3 Dividir em quebras naturais: parágrafo (\\n\\n) > lista (\\n- ou \\n•) > frase (. ) > espaço ( )
  - [x] 3.4 Garantir que NENHUMA parte exceda max_length
  - [x] 3.5 Se a mensagem for ≤ max_length, retornar lista com único elemento

- [x] Task 4: Criar `workflows/whatsapp/nodes/format_response.py` (AC: #1, #2, #7)
  - [x] 4.1 Criar `workflows/whatsapp/nodes/format_response.py`
  - [x] 4.2 Implementar `async def format_response(state: WhatsAppState) -> dict` (LangGraph node contract)
  - [x] 4.3 Extrair texto da resposta do último AIMessage em `state["messages"]`
  - [x] 4.4 Aplicar `validate_citations()` com `state["retrieved_sources"]` (no-op se lista vazia)
  - [x] 4.5 Aplicar `strip_competitor_citations()` (no-op se sem menções)
  - [x] 4.6 Aplicar `markdown_to_whatsapp()` para converter formatação
  - [x] 4.7 Aplicar `add_medical_disclaimer()` se `should_add_disclaimer()` retornar True
  - [x] 4.8 Aplicar `split_message()` se texto > 4096 chars
  - [x] 4.9 Retornar dict parcial: `{"formatted_response": first_part, "additional_responses": extra_parts}`
  - [x] 4.10 Logar `response_formatted` com content_type e char_count via structlog

- [x] Task 5: Criar `workflows/whatsapp/nodes/send_whatsapp.py` (AC: #3, #4)
  - [x] 5.1 Criar `workflows/whatsapp/nodes/send_whatsapp.py`
  - [x] 5.2 Implementar `async def send_whatsapp(state: WhatsAppState) -> dict` (LangGraph node contract)
  - [x] 5.3 Chamar `mark_as_read(state["wamid"])` para typing indicator (fire-and-forget, não falhar se erro)
  - [x] 5.4 Chamar `send_text_message(state["phone_number"], state["formatted_response"])`
  - [x] 5.5 Se houver `additional_responses`: iterar e enviar cada parte sequencialmente
  - [x] 5.6 Logar `whatsapp_response_sent` com phone, message_count, total_chars via structlog
  - [x] 5.7 Retornar dict parcial: `{"response_sent": True}`
  - [x] 5.8 Em caso de falha irrecuperável (após retries do RetryPolicy): logar ERROR e retornar `{"response_sent": False}`

- [x] Task 6: Criar `workflows/whatsapp/nodes/persist.py` (AC: #5)
  - [x] 6.1 Criar `workflows/whatsapp/nodes/persist.py`
  - [x] 6.2 Implementar `async def persist(state: WhatsAppState) -> dict` (LangGraph node contract)
  - [x] 6.3 Buscar User via `User.objects.aget(id=int(state["user_id"]))`
  - [x] 6.4 Criar mensagem do usuário: `Message.objects.acreate(user=user, content=state["user_message"], role="user", message_type=state["message_type"])`
  - [x] 6.5 Criar resposta do assistente: `Message.objects.acreate(user=user, content=state["formatted_response"], role="assistant", message_type="text", cost_usd=state.get("cost_usd"))`
  - [x] 6.6 NÃO criar CostLog nem ToolExecution — esses models não existem ainda (Story 7.1)
  - [x] 6.7 Logar `data_persisted` com user_id e cost_usd via structlog
  - [x] 6.8 Retornar dict parcial vazio `{}` (último nó antes de END)

- [x] Task 7: Atualizar `WhatsAppState` com novos campos (AC: #2)
  - [x] 7.1 Adicionar campo `additional_responses: list[str]` ao WhatsAppState em `workflows/whatsapp/state.py`

- [x] Task 8: Atualizar `build_whatsapp_graph()` com novos nós (AC: #1, #3, #5)
  - [x] 8.1 Adicionar import dos 3 novos nós em `workflows/whatsapp/graph.py`
  - [x] 8.2 Adicionar nó `format_response` ao StateGraph
  - [x] 8.3 Adicionar nó `send_whatsapp` com `retry_policy=RetryPolicy(max_attempts=3, backoff_factor=2.0)`
  - [x] 8.4 Adicionar nó `persist` ao StateGraph
  - [x] 8.5 Atualizar edges: `orchestrate_llm → format_response → send_whatsapp → persist → END`
  - [x] 8.6 Atualizar `workflows/whatsapp/nodes/__init__.py` com exports dos novos nós

- [x] Task 9: Atualizar settings e .env para WhatsApp Cloud API (AC: #6)
  - [x] 9.1 Adicionar em `config/settings/base.py`: `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_API_VERSION` (default "v21.0")
  - [x] 9.2 Atualizar `.env.example` com novas variáveis
  - [x] 9.3 Atualizar `config/settings/test.py` com mock values

- [x] Task 10: Atualizar views.py para fallback de erro (AC: #3)
  - [x] 10.1 Nos blocos `except` de `_process_message()`, substituir os TODOs por envio de mensagem amigável de erro via WhatsApp client
  - [x] 10.2 Mensagem de fallback: "Desculpe, tive um problema ao processar sua mensagem. Pode tentar novamente?"

- [x] Task 11: Testes (TODOS os ACs)
  - [x] 11.1 Criar `tests/test_providers/test_whatsapp.py`
  - [x] 11.2 Teste: `send_text_message()` faz POST correto (AC6)
  - [x] 11.3 Teste: `mark_as_read()` envia payload correto (AC6)
  - [x] 11.4 Teste: erro HTTP 500 dispara ExternalServiceError (AC6)
  - [x] 11.5 Teste: timeout dispara ExternalServiceError (AC6)
  - [x] 11.6 Criar `tests/test_utils/test_formatters.py`
  - [x] 11.7 Teste: `markdown_to_whatsapp()` converte bold, italic, headers, listas (AC1)
  - [x] 11.8 Teste: `should_add_disclaimer()` detecta conteúdo médico (AC7)
  - [x] 11.9 Teste: `add_medical_disclaimer()` adiciona disclaimer correto (AC7)
  - [x] 11.10 Criar `tests/test_utils/test_message_splitter.py`
  - [x] 11.11 Teste: mensagem curta retorna lista com 1 elemento (AC2)
  - [x] 11.12 Teste: mensagem longa é dividida corretamente em breaks naturais (AC2)
  - [x] 11.13 Teste: nenhuma parte excede 4096 chars (AC2)
  - [x] 11.14 Criar `tests/test_whatsapp/test_nodes/test_format_response.py`
  - [x] 11.15 Teste: format_response extrai texto do último AIMessage (AC1)
  - [x] 11.16 Teste: validate_citations() remove [N] sem fonte (AC1)
  - [x] 11.17 Teste: validate_citations() é no-op quando retrieved_sources vazio (AC1)
  - [x] 11.18 Teste: strip_competitor_citations() remove menções a concorrentes (AC1)
  - [x] 11.19 Teste: disclaimer adicionado em conteúdo médico (AC7)
  - [x] 11.20 Teste: split funciona para respostas longas (AC2)
  - [x] 11.21 Criar `tests/test_whatsapp/test_nodes/test_send_whatsapp.py`
  - [x] 11.22 Teste: send_whatsapp chama mark_as_read e send_text_message (AC3)
  - [x] 11.23 Teste: multiple responses enviadas sequencialmente (AC3)
  - [x] 11.24 Teste: retorna response_sent=True em sucesso (AC3)
  - [x] 11.25 Criar `tests/test_whatsapp/test_nodes/test_persist.py`
  - [x] 11.26 Teste: persist cria 2 Messages (user + assistant) via Django ORM (AC5)
  - [x] 11.27 Teste: persist NÃO cria CostLog nem ToolExecution (AC5)
  - [x] 11.28 Teste: persist loga data_persisted (AC5)
  - [x] 11.29 Atualizar `tests/test_graph.py`
  - [x] 11.30 Teste: grafo executa flow completo: identify_user → load_context → orchestrate_llm → format_response → send_whatsapp → persist → END

## Dev Notes

### Contexto de Negócio
- Story 1.5 **completa o pipeline end-to-end**: após esta story, o sistema recebe mensagem WhatsApp → processa com LLM → formata → envia resposta → persiste. É o primeiro fluxo **funcional completo** para o aluno.
- As funções `validate_citations()` e `strip_competitor_citations()` são **preparatórias** para Stories 2.x (Tools) — nesta fase são no-ops pois `retrieved_sources` e `web_sources` estarão vazios. MAS o código deve estar pronto e testado para quando as tools forem ativadas.
- O `persist` node **NÃO** cria CostLog nem ToolExecution — esses models serão criados na Story 7.1. Apenas Message é persistida agora.
- O disclaimer médico é obrigatório (FR17) — o sistema é ferramenta de apoio, não substitui avaliação médica.

### Padrões Obrigatórios (Estabelecidos nas Stories 1.1, 1.2, 1.3, 1.4)
- **SEMPRE** async/await para I/O (NUNCA bloqueante)
- **Django ORM async**: `aget()`, `acreate()` — `afilter()` NÃO existe, usar `.filter()` com async iteration
- **Type hints** em TODAS as funções
- **structlog** para logging (NUNCA `print()`)
- **AppError hierarchy** para exceções (usar `GraphNodeError` para falhas em nós, `ExternalServiceError` para falhas de WhatsApp API)
- **Import order**: Standard → Third-party → Local
- **NUNCA** `import *`, sync I/O, commitar secrets, logar PII sem sanitização
- **Nomes**: snake_case (arquivos, funções, variáveis), PascalCase (classes), UPPER_SNAKE_CASE (constantes)
- **LangGraph node contract**: funções async puras → `async def node_name(state: WhatsAppState) -> dict`
- **Retorno parcial**: nós SEMPRE retornam `dict` parcial (apenas campos alterados), NUNCA o estado completo
- **RetryPolicy**: usar `retry_policy=RetryPolicy(...)` (NÃO `retry=` — deprecado no LangGraph 1.0.10)

### Infraestrutura Já Disponível (Stories 1.1-1.4 — NÃO RECRIAR)
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
- `workflows/serializers.py` — WhatsAppMessageSerializer
- `workflows/whatsapp/state.py` — WhatsAppState TypedDict (15 campos, `add_messages` reducer)
- `workflows/whatsapp/graph.py` — `build_whatsapp_graph()` (START → identify_user → load_context → orchestrate_llm → END) + `get_graph()` async singleton
- `workflows/whatsapp/nodes/identify_user.py` — Nó identify_user (busca/cria User, cache)
- `workflows/whatsapp/nodes/load_context.py` — Nó load_context (últimas 20 msgs, LangChain conversion)
- `workflows/whatsapp/prompts/system.py` — get_system_prompt() + build_system_message() com cache_control
- `workflows/providers/llm.py` — get_model() singleton com ChatVertexAI + ChatAnthropic fallback
- `workflows/providers/checkpointer.py` — get_checkpointer() singleton com AsyncPostgresSaver
- `workflows/whatsapp/nodes/orchestrate_llm.py` — Nó orchestrate_llm com cost tracking
- `config/settings/base.py` — REDIS_URL, WHATSAPP_WEBHOOK_SECRET, WHATSAPP_VERIFY_TOKEN, VERTEX_PROJECT_ID, etc.
- 109 testes passando (Stories 1.1-1.4)

### Inteligência da Story Anterior (1-4)

**Lições aprendidas:**
- `ChatAnthropicVertex` foi unificado em `ChatVertexAI` no langchain-google-vertexai 3.2.2
- `retry=` está deprecado em `add_node()` — usar `retry_policy=RetryPolicy(...)`
- `MagicMock()` como checkpointer falha isinstance — usar `InMemorySaver()` em testes
- `LLMResult` com Pydantic v2: usar `ChatGeneration(message=AIMessage(...))` em vez de MagicMock
- Django `AsyncClient` em testes: usar `headers={}` dict em vez de `HTTP_*` kwargs
- Redis precisa de connection pooling (singleton)
- `afilter()` NÃO existe no Django ORM — usar `.filter()` com `async for`
- `@pytest.mark.django_db` requer `transaction=True` para isolamento com campos unique

**Padrões de código estabelecidos:**
- Nós LangGraph: `async def node_name(state: WhatsAppState) -> dict` retornando dict parcial
- Testes: `@pytest.mark.django_db(transaction=True)` + mocks com `AsyncMock`
- Singleton: `_compiled_graph`, `_model_cache`, `_checkpointer`
- Graph: `get_graph()` async singleton via `build_whatsapp_graph().compile()`

**Arquivos criados na Story 1.4 que impactam Story 1.5:**
- `workflows/whatsapp/graph.py` — DEVE ser estendido: adicionar format_response, send_whatsapp, persist
- `workflows/whatsapp/nodes/orchestrate_llm.py` — Retorna `{"messages": [user_msg, response], "cost_usd": ...}` — o nó format_response deve extrair o último AIMessage
- `workflows/whatsapp/state.py` — DEVE ser estendido: adicionar `additional_responses`
- `workflows/views.py` — DEVE ser atualizado: substituir TODOs de fallback por envio de mensagem de erro

### Project Structure Notes

#### Arquivos a Criar
```
workflows/
├── providers/
│   └── whatsapp.py              # CRIAR — WhatsApp Cloud API client (httpx async)
├── utils/
│   ├── formatters.py            # CRIAR — Markdown → WhatsApp formatting
│   └── message_splitter.py      # CRIAR — Split mensagens > 4096 chars
└── whatsapp/
    └── nodes/
        ├── format_response.py   # CRIAR — Nó format_response (validate, strip, format, split)
        ├── send_whatsapp.py     # CRIAR — Nó send_whatsapp (Cloud API + typing)
        └── persist.py           # CRIAR — Nó persist (Django ORM Message)

tests/
├── test_providers/
│   └── test_whatsapp.py         # CRIAR — Testes do WhatsApp client
├── test_utils/
│   ├── test_formatters.py       # CRIAR — Testes do formatador
│   └── test_message_splitter.py # CRIAR — Testes do splitter
└── test_whatsapp/
    └── test_nodes/
        ├── test_format_response.py   # CRIAR — Testes do nó format_response
        ├── test_send_whatsapp.py     # CRIAR — Testes do nó send_whatsapp
        └── test_persist.py           # CRIAR — Testes do nó persist
```

#### Arquivos a Modificar
```
workflows/
├── whatsapp/
│   ├── graph.py                 # MODIFICAR — Adicionar 3 novos nós + edges
│   ├── state.py                 # MODIFICAR — Adicionar additional_responses
│   └── nodes/
│       └── __init__.py          # MODIFICAR — Exportar 3 novos nós
├── views.py                     # MODIFICAR — Substituir TODOs de fallback
config/
├── settings/
│   ├── base.py                  # MODIFICAR — Adicionar WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID
│   └── test.py                  # MODIFICAR — Mock values para WhatsApp
.env.example                     # MODIFICAR — Adicionar novas variáveis

tests/
└── test_graph.py                # MODIFICAR — Testar flow completo com novos nós
```

### Guardrails de Arquitetura

#### ADRs Aplicáveis
| ADR | Decisão | Impacto nesta Story |
|-----|---------|---------------------|
| ADR-002 | Django + DRF + adrf | Async views, Django ORM async para persist |
| ADR-003 | Django ORM (não supabase-py) | Message.objects.acreate() para persistência |
| ADR-009 | App `workflows/` | Nodes em `workflows/whatsapp/nodes/`, utils em `workflows/utils/` |
| ADR-010 | LangGraph + LangChain 1.0 | StateGraph nodes com RetryPolicy para send_whatsapp |

#### Requisitos Não-Funcionais (NFR)
| NFR | Requisito | Como Implementar |
|-----|-----------|------------------|
| NFR1 | Latência P95 < 8s (texto) | send_whatsapp com timeout 10s, typing indicator imediato |
| NFR8 | Split de respostas | max_length=4096 chars por mensagem |
| NFR13 | Nenhuma mensagem perdida | Fallback de erro no views.py, persist antes de END |
| NFR14 | Webhook 200 OK < 3s | Já implementado (fire-and-forget), send_whatsapp é async |
| NFR17 | Credenciais em env vars | WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID via django-environ |
| NFR19 | Logs sem PII | Phone já redacted pelo sanitize_pii processor |

### Libraries/Frameworks — Versões e Padrões Atualizados

| Lib | Versão | Uso nesta Story | Notas Importantes |
|-----|--------|----------------|-------------------|
| httpx | 0.28+ | WhatsApp Cloud API client | Import: `import httpx`. Async via `httpx.AsyncClient()` |
| langgraph | 1.0.10 | StateGraph, RetryPolicy | `retry_policy=RetryPolicy(max_attempts=3, backoff_factor=2.0)` |
| langchain-core | 1.2.17 | AIMessage (extrair content) | Import: `from langchain_core.messages import AIMessage` |
| structlog | 24.4+ | Logging em todos os nós | Import: `import structlog; logger = structlog.get_logger(__name__)` |
| django | 5.1+ | ORM async (aget, acreate) | `Message.objects.acreate(...)` |

### Informações Técnicas Atualizadas (Pesquisa Web — Mar 2026)

#### WhatsApp Cloud API v21.0 — Envio de Mensagens

```python
# Endpoint
POST https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages

# Headers
Authorization: Bearer {ACCESS_TOKEN}
Content-Type: application/json

# Payload para enviar texto
{
    "messaging_product": "whatsapp",
    "recipient_type": "individual",
    "to": "5511999999999",
    "type": "text",
    "text": {
        "body": "Sua resposta aqui (max 4096 chars)"
    }
}

# Resposta de sucesso
{
    "messaging_product": "whatsapp",
    "contacts": [{"input": "5511999999999", "wa_id": "5511999999999"}],
    "messages": [{"id": "wamid.HBg...", "message_status": "accepted"}]
}
```

#### WhatsApp Cloud API v21.0 — Typing Indicator

```python
# Mark as read (mostra typing indicator por até 25 segundos)
POST https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages

{
    "messaging_product": "whatsapp",
    "status": "read",
    "message_id": "wamid.HBg..."  # wamid da mensagem recebida
}
```

#### WhatsApp Cloud API Client — Padrão Recomendado

```python
# workflows/providers/whatsapp.py
import httpx
import structlog
from django.conf import settings
from workflows.utils.errors import ExternalServiceError

logger = structlog.get_logger(__name__)

_client: httpx.AsyncClient | None = None

WHATSAPP_API_BASE = "https://graph.facebook.com"

def _get_client() -> httpx.AsyncClient:
    """Singleton httpx.AsyncClient para WhatsApp Cloud API."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=f"{WHATSAPP_API_BASE}/{settings.WHATSAPP_API_VERSION}",
            headers={
                "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            },
            timeout=10.0,
        )
    return _client

async def send_text_message(phone: str, text: str) -> dict:
    """Envia mensagem de texto via WhatsApp Cloud API."""
    client = _get_client()
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "text",
        "text": {"body": text},
    }
    try:
        response = await client.post(
            f"/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        logger.info(
            "whatsapp_message_sent",
            phone=phone,
            wamid=data["messages"][0]["id"],
        )
        return data
    except httpx.HTTPStatusError as exc:
        raise ExternalServiceError(
            service="whatsapp",
            message=f"HTTP {exc.response.status_code}: {exc.response.text}",
        ) from exc
    except httpx.TimeoutException as exc:
        raise ExternalServiceError(
            service="whatsapp",
            message="Timeout sending message",
        ) from exc

async def mark_as_read(wamid: str) -> bool:
    """Marca mensagem como lida (mostra typing indicator)."""
    client = _get_client()
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": wamid,
    }
    try:
        response = await client.post(
            f"/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages",
            json=payload,
        )
        response.raise_for_status()
        return True
    except Exception:
        logger.warning("whatsapp_mark_read_failed", wamid=wamid)
        return False  # Non-critical, don't block pipeline
```

#### Markdown → WhatsApp Formatting — Padrão

```python
# workflows/utils/formatters.py
import re

def markdown_to_whatsapp(text: str) -> str:
    """Converte markdown para formato WhatsApp."""
    # Headers → bold
    text = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)
    # Bold **text** → *text*
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    # Italic _text_ mantém (WhatsApp suporta)
    # Strikethrough ~~text~~ → ~text~
    text = re.sub(r"~~(.+?)~~", r"~\1~", text)
    # Unordered lists - item → • item
    text = re.sub(r"^[-*]\s+", "• ", text, flags=re.MULTILINE)
    # Links [text](url) → text (url)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
    return text
```

#### Message Splitter — Padrão

```python
# workflows/utils/message_splitter.py

def split_message(text: str, max_length: int = 4096) -> list[str]:
    """Divide texto em partes ≤ max_length em quebras naturais."""
    if len(text) <= max_length:
        return [text]

    parts: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_length:
            parts.append(remaining)
            break

        # Tentar dividir em parágrafo
        cut = remaining[:max_length].rfind("\n\n")
        if cut == -1 or cut < max_length // 4:
            # Tentar dividir em newline
            cut = remaining[:max_length].rfind("\n")
        if cut == -1 or cut < max_length // 4:
            # Tentar dividir em frase
            cut = remaining[:max_length].rfind(". ")
        if cut == -1 or cut < max_length // 4:
            # Última opção: dividir em espaço
            cut = remaining[:max_length].rfind(" ")
        if cut == -1:
            # Forçar divisão no max_length (caso extremo)
            cut = max_length - 1

        parts.append(remaining[:cut + 1].rstrip())
        remaining = remaining[cut + 1:].lstrip()

    return parts
```

#### validate_citations e strip_competitor_citations — Padrão

```python
# workflows/whatsapp/nodes/format_response.py (funções internas)
import re

COMPETITOR_NAMES = [
    "medcurso", "medgrupo", "medcof", "estratégia med", "estrategia med",
    "medcel", "afya", "sanar", "sanarflix", "aristo", "jj medicina",
    "eu médico residente", "eu medico residente", "revisamed",
    "mediccurso", "medprovas", "vr med", "vrmed", "medmentoria",
    "o residente", "oresidente", "yellowbook",
]

def validate_citations(text: str, available_sources: list[dict]) -> str:
    """Remove marcadores [N] que não correspondem a fontes reais."""
    if not available_sources:
        # No-op: sem fontes = sem citações para validar
        # Strip ALL citation markers [N] and [W-N] since none are valid
        text = re.sub(r"\[\d+\]", "", text)
        text = re.sub(r"\[W-\d+\]", "", text)
        return text

    max_rag = len([s for s in available_sources if s.get("type") == "rag"])
    max_web = len([s for s in available_sources if s.get("type") == "web"])

    def check_rag(match: re.Match) -> str:
        n = int(match.group(1))
        return match.group(0) if n <= max_rag else ""

    def check_web(match: re.Match) -> str:
        n = int(match.group(1))
        return match.group(0) if n <= max_web else ""

    text = re.sub(r"\[(\d+)\]", check_rag, text)
    text = re.sub(r"\[W-(\d+)\]", check_web, text)
    return text

def strip_competitor_citations(text: str) -> str:
    """Remove menções a concorrentes da resposta final."""
    for name in COMPETITOR_NAMES:
        pattern = re.compile(re.escape(name), re.IGNORECASE)
        if pattern.search(text):
            logger.warning("competitor_citation_blocked", competitor=name)
            text = pattern.sub("[fonte removida]", text)
    return text
```

#### Pitfalls Conhecidos (Story 1.5)

1. **httpx.AsyncClient deve ser singleton** — NÃO criar novo client por request (connection pooling). Usar padrão singleton como Redis client em `deduplication.py`.
2. **WhatsApp typing indicator é best-effort** — Se falhar, NÃO bloquear o pipeline. Usar try/except e retornar False silenciosamente.
3. **Message split deve preservar formatação** — Ao dividir, verificar que marcadores WhatsApp (*, _, ~, ```) não ficam "abertos" (sem par).
4. **validate_citations() com sources vazio** — Quando `retrieved_sources=[]` (sem tools ativas), TODOS os marcadores `[N]` e `[W-N]` devem ser removidos — pois são alucinações do LLM.
5. **persist node NÃO deve falhar o pipeline** — Se Django ORM falhar, logar ERROR mas NÃO re-raise (o aluno já recebeu a resposta).
6. **graph singleton reset** — Ao adicionar novos nós, o singleton `_compiled_graph` em `graph.py` precisa ser `None` para recompilar. Em testes, sempre usar `build_whatsapp_graph()` diretamente.
7. **additional_responses no WhatsAppState** — Precisa default (lista vazia) no initial_state em `views.py` — caso contrário KeyError.
8. **AIMessage content extraction** — O último AIMessage em `state["messages"]` contém a resposta. Usar `state["messages"][-1].content` — verificar que é string (pode ser list se Vision).
9. **Phone number format** — WhatsApp espera número sem `+` no payload de envio (ex: `5511999999999`). Remover `+` se presente.

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 1, Story 1.5]
- [Source: _bmad-output/planning-artifacts/architecture.md — StateGraph pattern (graph.py)]
- [Source: _bmad-output/planning-artifacts/architecture.md — format_response node (validate_citations, strip_competitor_citations)]
- [Source: _bmad-output/planning-artifacts/architecture.md — persist node (Django ORM)]
- [Source: _bmad-output/planning-artifacts/architecture.md — WhatsApp Cloud API client (providers/whatsapp.py)]
- [Source: _bmad-output/planning-artifacts/architecture.md — formatters.py (Markdown → WhatsApp)]
- [Source: _bmad-output/planning-artifacts/architecture.md — message_splitter.py (split mensagens)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Enforcement Rules (MUST/MUST NOT)]
- [Source: _bmad-output/planning-artifacts/architecture.md — RetryPolicy para send_whatsapp (3 attempts)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Competitor blocking (3 layers)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Citation validation pattern]
- [Source: _bmad-output/planning-artifacts/prd.md — FR1 (texto → resposta), FR8 (split), FR9 (typing), FR17 (disclaimer), FR18 (formatação), FR19 (formato adaptativo)]
- [Source: _bmad-output/planning-artifacts/prd.md — NFR13 (zero mensagens perdidas), NFR14 (webhook 200 < 3s)]
- [Source: _bmad-output/implementation-artifacts/1-4-llm-provider-checkpointer-orquestracao-base.md — Dev Notes, Lessons Learned, Code Review Fixes]
- [Source: WhatsApp Cloud API v21.0 — Message sending endpoint, typing indicators, character limits]
- [Source: httpx 0.28+ — AsyncClient, timeout, raise_for_status()]

## Change Log

- 2026-03-07: Story 1.5 implementada — pipeline E2E completo: format_response → send_whatsapp → persist. 183 testes passando (74 novos).
- 2026-03-07: Code Review adversarial — 9 issues encontrados (1 HIGH, 5 MEDIUM, 3 LOW), todos corrigidos:
  - H1: RetryPolicy do send_whatsapp era ineficaz (except Exception capturava tudo) — reestruturado para propagar ExternalServiceError
  - M1: Code blocks não protegidos de transformações — adicionada proteção com placeholders
  - M3: Regex de concorrentes recompilados a cada chamada — pré-compilados como constantes de módulo
  - M4: persist capturava todos os erros silenciosamente — agora só captura DatabaseError/DoesNotExist
  - M5: Sem teste de falha parcial no envio — adicionado teste
  - L1: Keywords curtas (mg, ml) causavam falsos positivos — agora requerem número precedente
  - L3: detect_content_type rodava no texto transformado — movido para antes das transformações
  - 188 testes passando após correções (5 novos testes).

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

- httpx.Response mock: `MagicMock(spec=httpx.Response)` em vez de `AsyncMock` para métodos síncronos `.json()` / `.raise_for_status()`
- Test data size: ajuste no `test_splits_long_message_correctly` para gerar texto realmente >12k chars

### Completion Notes List

- **Task 1 (WhatsApp Client):** Singleton httpx.AsyncClient com base_url, Bearer token, timeout 10s. `send_text_message()` com strip de `+` no phone. `mark_as_read()` best-effort (retorna False em erro). Erros mapeados para `ExternalServiceError`. 10 testes.
- **Task 2 (Formatters):** `markdown_to_whatsapp()` converte bold, headers, listas, links. `should_add_disclaimer()` com heurística de keywords médicas + exclusão de saudações. `detect_content_type()` classifica resposta. 26 testes.
- **Task 3 (Message Splitter):** `split_message()` com divisão em quebras naturais (parágrafo > newline > frase > espaço). Garantia que nenhuma parte excede max_length. 11 testes.
- **Task 4 (format_response node):** Pipeline completo: extract AIMessage → validate_citations → strip_competitor → markdown_to_whatsapp → disclaimer → split. `validate_citations()` e `strip_competitor_citations()` como funções do módulo. 18 testes.
- **Task 5 (send_whatsapp node):** mark_as_read (fire-and-forget) → send formatted_response → send additional_responses sequencialmente. Retorna `response_sent: True/False`. 5 testes.
- **Task 6 (persist node):** Cria 2 Messages via Django ORM async (user + assistant). cost_usd como Decimal. Não re-raises em erro (aluno já recebeu resposta). 4 testes.
- **Task 7 (State):** Adicionado `additional_responses: list[str]` ao WhatsAppState.
- **Task 8 (Graph):** 3 novos nós adicionados ao StateGraph. send_whatsapp com RetryPolicy(max_attempts=3, backoff_factor=2.0). Flow: orchestrate_llm → format_response → send_whatsapp → persist → END.
- **Task 9 (Settings):** WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_API_VERSION adicionados a base.py, test.py e .env.example.
- **Task 10 (Fallback):** `_send_fallback()` helper no views.py. TODOs substituídos por envio de mensagem amigável via WhatsApp client.
- **Task 11 (Testes):** 74 novos testes (183 total). Testes de integração do grafo atualizados para flow completo de 6 nós. Zero regressões.

### File List

**Arquivos Criados:**
- `workflows/providers/whatsapp.py` — WhatsApp Cloud API client (httpx async singleton)
- `workflows/utils/formatters.py` — Markdown → WhatsApp formatting + disclaimer + content type detection
- `workflows/utils/message_splitter.py` — Split mensagens longas (max 4096 chars)
- `workflows/whatsapp/nodes/format_response.py` — Nó format_response (validate, strip, format, split)
- `workflows/whatsapp/nodes/send_whatsapp.py` — Nó send_whatsapp (Cloud API + typing indicator)
- `workflows/whatsapp/nodes/persist.py` — Nó persist (Django ORM Message)
- `tests/test_providers/test_whatsapp.py` — 10 testes do WhatsApp client
- `tests/test_utils/__init__.py` — Package init
- `tests/test_utils/test_formatters.py` — 26 testes do formatador
- `tests/test_utils/test_message_splitter.py` — 11 testes do splitter
- `tests/test_whatsapp/test_nodes/test_format_response.py` — 18 testes do nó format_response
- `tests/test_whatsapp/test_nodes/test_send_whatsapp.py` — 5 testes do nó send_whatsapp
- `tests/test_whatsapp/test_nodes/test_persist.py` — 4 testes do nó persist

**Arquivos Modificados:**
- `workflows/whatsapp/state.py` — Adicionado campo `additional_responses: list[str]`
- `workflows/whatsapp/graph.py` — 3 novos nós + edges atualizados (flow completo)
- `workflows/whatsapp/nodes/__init__.py` — Exports dos 3 novos nós
- `workflows/views.py` — Fallback de erro via WhatsApp + `additional_responses` no initial_state
- `config/settings/base.py` — WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_API_VERSION
- `config/settings/test.py` — Mock values para WhatsApp Cloud API
- `.env.example` — WHATSAPP_API_VERSION adicionado
- `tests/test_graph.py` — Testes de integração atualizados para flow completo de 6 nós
