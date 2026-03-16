# Story 1.2: Webhook WhatsApp + Middleware de Segurança

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a sistema,
I want receber mensagens do WhatsApp via webhook com validação de segurança,
So that apenas mensagens legítimas são processadas e a Meta não reenvia por timeout.

## Acceptance Criteria

### AC1: Assinatura HMAC Válida — Processamento de Mensagem

```gherkin
Given uma requisição POST no `/webhook/whatsapp/` com assinatura HMAC válida
When a Meta envia um payload de mensagem de texto
Then o middleware `WebhookSignatureMiddleware` valida a assinatura `X-Hub-Signature-256` via HMAC SHA-256
And o `WhatsAppMessageSerializer` (DRF) valida o payload (regex phone, timestamp ≤ 300s)
And a mensagem é deduplicada via Redis (`msg_processed:{message_id}`, TTL 1h)
And mensagens duplicadas são ignoradas silenciosamente
And o processamento é disparado via `asyncio.create_task` (fire-and-forget)
And o webhook retorna 200 OK em < 3 segundos (NFR14)
And status updates (delivered, read) são filtrados e ignorados
And mensagens do tipo "system" e "unknown" são filtradas e ignoradas
```

### AC2: Assinatura Inválida ou Ausente

```gherkin
Given uma requisição POST sem assinatura ou com assinatura inválida
When a Meta envia o payload
Then o middleware retorna 401 e loga `webhook_signature_invalid`
```

### AC3: Webhook Verification Handshake (GET)

```gherkin
Given uma requisição GET no `/webhook/whatsapp/`
When a Meta envia o handshake de verificação (`hub.mode=subscribe`, `hub.verify_token`)
Then o sistema retorna o `hub.challenge` com 200 OK se o token confere
And retorna 403 se o token não confere
```

### AC4: Trace ID Propagation

```gherkin
Given o trace_id middleware
When qualquer request chega
Then um UUID trace_id é gerado e propagado via structlog contextvars
```

## Tasks / Subtasks

- [x] Task 1: Criar `WebhookSignatureMiddleware` (AC: #1, #2)
  - [x] 1.1 Criar arquivo `workflows/middleware/webhook_signature.py`
  - [x] 1.2 Implementar validação HMAC SHA-256 contra body RAW (antes de JSON parsing)
  - [x] 1.3 Usar `hmac.compare_digest()` para comparação timing-safe
  - [x] 1.4 Retornar 401 com log `webhook_signature_invalid` para assinaturas inválidas
  - [x] 1.5 Aplicar middleware APENAS em rotas `/webhook/` (não em admin ou outras rotas)
  - [x] 1.6 Implementar como async middleware (evitar penalidade sync-to-async)
- [x] Task 2: Criar `TraceIDMiddleware` (AC: #4)
  - [x] 2.1 Criar arquivo `workflows/middleware/trace_id.py`
  - [x] 2.2 Gerar UUID e bind via `structlog.contextvars.bind_contextvars(trace_id=...)`
  - [x] 2.3 Adicionar header `X-Trace-ID` na resposta
  - [x] 2.4 Implementar como async middleware
- [x] Task 3: Registrar middlewares em `config/settings/base.py` (AC: #1, #2, #4)
  - [x] 3.1 Adicionar `WebhookSignatureMiddleware` ANTES do `TraceIDMiddleware`
  - [x] 3.2 Adicionar `TraceIDMiddleware` ANTES do `CsrfViewMiddleware`
  - [x] 3.3 Garantir que CSRF está desabilitado para webhook (via `csrf_exempt` ou posição do middleware)
- [x] Task 4: Criar `WhatsAppWebhookView` (AC: #1, #3)
  - [x] 4.1 Criar/atualizar `workflows/views.py` com `WhatsAppWebhookView(adrf.views.APIView)`
  - [x] 4.2 Implementar `async def post()` — fire-and-forget via `asyncio.create_task()`
  - [x] 4.3 Implementar `async def get()` — webhook verification handshake
  - [x] 4.4 Processar TODOS os elementos dos arrays `entry` e `changes` (não apenas o primeiro)
  - [x] 4.5 Filtrar status updates (delivered, read, failed) e mensagens system/unknown
- [x] Task 5: Criar `WhatsAppMessageSerializer` (AC: #1)
  - [x] 5.1 Criar/atualizar `workflows/serializers.py`
  - [x] 5.2 Validar phone via regex pattern
  - [x] 5.3 Validar timestamp ≤ 300s (anti-replay)
  - [x] 5.4 Validar message_type (filtrar system/unknown)
- [x] Task 6: Implementar deduplicação via Redis (AC: #1)
  - [x] 6.1 Criar `workflows/utils/deduplication.py`
  - [x] 6.2 Implementar `is_duplicate_message()` com key `msg_processed:{message_id}`, TTL 1h
  - [x] 6.3 Usar `redis.setex()` para marcar como processado
- [x] Task 7: Configurar URL routing (AC: #1, #3)
  - [x] 7.1 Criar/atualizar `workflows/urls.py` com path `webhook/whatsapp/`
  - [x] 7.2 Atualizar `config/urls.py` com include de `workflows.urls`
- [x] Task 8: Adicionar variáveis de ambiente (AC: #1, #2, #3)
  - [x] 8.1 Adicionar `WHATSAPP_WEBHOOK_SECRET` e `WHATSAPP_VERIFY_TOKEN` em `base.py`
  - [x] 8.2 Atualizar `.env.example` com as novas variáveis
- [x] Task 9: Implementar event filtering (AC: #1)
  - [x] 9.1 Criar função `should_process_event()` para filtrar apenas mensagens de texto
  - [x] 9.2 Ignorar silenciosamente: statuses, system messages, unknown types
- [x] Task 10: Testes (TODOS os ACs)
  - [x] 10.1 Teste: HMAC válido → 200 OK
  - [x] 10.2 Teste: HMAC inválido → 401
  - [x] 10.3 Teste: HMAC ausente → 401
  - [x] 10.4 Teste: Handshake GET válido → 200 + challenge echo
  - [x] 10.5 Teste: Handshake GET token errado → 403
  - [x] 10.6 Teste: Deduplicação → segunda mensagem com mesmo ID ignorada
  - [x] 10.7 Teste: Status updates ignorados
  - [x] 10.8 Teste: Mensagens system/unknown ignoradas
  - [x] 10.9 Teste: Timestamp expirado (>300s) → rejeitado
  - [x] 10.10 Teste: Trace ID gerado e propagado
  - [x] 10.11 Teste: Múltiplos entries/changes processados (array handling)

## Dev Notes

### Contexto de Negócio
- Este webhook é o **ponto de entrada** de todo o sistema Medbrain WhatsApp
- A Meta **reenvia** webhooks se não receber 200 OK em < 3 segundos → CRITICAL usar fire-and-forget
- Produto atual roda em n8n (116 nós), sendo migrado via estratégia Strangler Fig
- Story 1.2 é bloqueante para TODAS as stories subsequentes (1.3-1.6 e Epics 2-10)

### Padrões Obrigatórios (da Story 1.1)
- **SEMPRE** async/await para I/O (NUNCA bloqueante)
- **Django ORM async**: `aget`, `acreate`, `afilter` (NUNCA sync `get`, `create`, `filter`)
- **Type hints** em TODAS as funções
- **structlog** para logging (NUNCA `print()`)
- **AppError hierarchy** para exceções (usar `AuthenticationError` para falhas de webhook)
- **Import order**: Standard → Third-party → Local
- **NUNCA** `import *`, sync I/O, commitar secrets, logar PII sem sanitização
- **Nomes**: snake_case (arquivos, funções, variáveis), PascalCase (classes), UPPER_SNAKE_CASE (constantes)

### Infraestrutura Já Disponível (Story 1.1 — NÃO RECRIAR)
- `workflows/utils/errors.py` — AppError, ValidationError, AuthenticationError, RateLimitError, ExternalServiceError, GraphNodeError
- `workflows/utils/sanitization.py` — PII redaction processor para structlog
- `workflows/services/config_service.py` — ConfigService.get() async
- `workflows/models.py` — User, Message, Config, CostLog, ToolExecution
- `config/settings/base.py` — structlog configurado com sanitize_pii
- `tests/conftest.py` — Fixtures pytest-django + pytest-asyncio
- Docker: PostgreSQL 16 + Redis 7 (docker-compose.yml)
- 32 testes passando

### Correções Críticas da Story 1.1 (Manter Compatibilidade)
- structlog config movido para `WorkflowsConfig.ready()` (não em base.py)
- SECRET_KEY validation em production.py
- PII sanitization recursiva para dicts/listas aninhados
- ConfigService lança `ValidationError` em vez de `DoesNotExist`

### Project Structure Notes

#### Arquivos a Criar/Modificar
```
workflows/
├── middleware/
│   ├── __init__.py              # CRIAR (se não existir)
│   ├── webhook_signature.py     # CRIAR — WebhookSignatureMiddleware
│   └── trace_id.py              # CRIAR — TraceIDMiddleware
├── views.py                     # CRIAR/MODIFICAR — WhatsAppWebhookView
├── serializers.py               # CRIAR — WhatsAppMessageSerializer
├── urls.py                      # CRIAR — URL routing da app
└── utils/
    └── deduplication.py         # CRIAR — is_duplicate_message()

config/
├── settings/
│   └── base.py                  # MODIFICAR — adicionar middleware + env vars
└── urls.py                      # MODIFICAR — include workflows.urls

tests/
├── test_webhook.py              # CRIAR — Testes de webhook (middleware + views)
└── test_middleware.py            # CRIAR — Testes isolados de middleware
```

#### Alignment com Estrutura Existente
- Middleware em `workflows/middleware/` (conforme architecture.md ADR-009)
- Views async via `adrf.views.APIView` (conforme ADR-002)
- Serializers DRF em `workflows/serializers.py` (conforme ADR-002)
- Testes em `tests/` na raiz do projeto (padrão da Story 1.1)

### Guardrails de Arquitetura

#### ADRs Aplicáveis
| ADR | Decisão | Impacto nesta Story |
|-----|---------|---------------------|
| ADR-002 | Django 5.2 LTS + DRF + adrf | Views async, serializers DRF |
| ADR-004 | uv + pytest-django + Ruff + mypy strict | Toolchain, testes |
| ADR-008 | 6 camadas de segurança | Layer 1 (HMAC) + Layer 2 (DRF serializers) + Layer 6 (PII sanitization) |
| ADR-009 | App `workflows/` | Localização de middleware, views, serializers |

#### Requisitos Não-Funcionais (NFR)
| NFR | Requisito | Como Implementar |
|-----|-----------|------------------|
| NFR14 | Webhook responde 200 OK em < 3s | `asyncio.create_task()` fire-and-forget |
| NFR16 | Validação de assinatura em todos webhooks | `WebhookSignatureMiddleware` HMAC SHA-256 |

#### Libraries/Frameworks — Versões Confirmadas
| Lib | Versão | Uso nesta Story |
|-----|--------|----------------|
| Django | 5.2 LTS | Framework principal, middleware |
| DRF | 3.15+ | `WhatsAppMessageSerializer` |
| adrf | 0.1+ | `APIView` async para webhook |
| structlog | 24.4+ | Logging com PII sanitization |
| redis (async) | 5.0+ | Deduplicação `msg_processed:{id}` |
| httpx | 0.28+ | (NÃO nesta story, mas disponível para futuras) |

### Informações Técnicas Atualizadas (Pesquisa Web — Mar 2026)

#### CRÍTICO: HMAC Validation — Body RAW
A Meta assina o payload usando o **body RAW** (antes de JSON parsing). O middleware Django DEVE usar `request.body` (bytes) para calcular o HMAC, NUNCA `request.data` (parsed). Caracteres Unicode escapados afetam a assinatura.

**Implementação correta:**
```python
expected = "sha256=" + hmac.new(
    settings.WHATSAPP_WEBHOOK_SECRET.encode(),
    request.body,  # ← RAW bytes, NÃO request.data
    hashlib.sha256,
).hexdigest()
```

#### CRÍTICO: Django Async Middleware
Todos os middlewares devem ser async para evitar penalidade de sync-to-async switching. Se houver UM middleware sync entre o ASGI server e uma view async, o Django abre uma thread por request, eliminando vantagem async.

#### ATENÇÃO: WhatsApp BSUID (Business-Scoped User ID)
A partir de junho 2026, usernames podem esconder phone numbers. Webhooks passarão a incluir BSUID. **Para esta story**: implementar normalmente com phone. Na Story 1.3 (Identificação de Usuário), considerar campo para BSUID.

#### ATENÇÃO: Certificate Authority Update
A Meta está trocando o CA para mTLS em **31/03/2026**. Se o servidor usa mTLS para receber webhooks, precisa atualizar trust store com `meta-outbound-api-ca-2025-12.pem`. **Para Cloud Run**: provavelmente não afeta (HTTPS padrão), mas verificar.

#### ATENÇÃO: Array Handling no Payload
Payloads contêm arrays (`entry`, `changes`, `messages`). Processar TODOS os elementos, não apenas `[0]`. Implementar loops para cada array.

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 1, Story 1.2]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-002, ADR-008, ADR-009]
- [Source: _bmad-output/planning-artifacts/architecture.md — Seção "6 Camadas de Segurança"]
- [Source: _bmad-output/planning-artifacts/architecture.md — Seção "Webhook Endpoint Pattern"]
- [Source: _bmad-output/planning-artifacts/architecture.md — Seção "Middleware Registration"]
- [Source: _bmad-output/planning-artifacts/architecture.md — Seção "Testing Standards"]
- [Source: _bmad-output/implementation-artifacts/1-1-setup-projeto-django-estrutura-base.md — Dev Notes, File List]
- [Source: Meta WhatsApp Cloud API Webhooks Documentation — https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/]
- [Source: Django Async Documentation — https://docs.djangoproject.com/en/6.0/topics/async/]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

- Primeira execução de testes: 7 falhas em test_webhook.py (middleware bloqueando GET + headers não passando via AsyncClient)
- Fix 1: Middleware atualizado para validar HMAC apenas em POST requests (GET handshake não usa HMAC)
- Fix 2: Testes atualizados para usar `headers={}` dict (Django 5.2+ AsyncClient) em vez de `HTTP_*` kwargs
- Fix 3: Adicionado WHATSAPP_WEBHOOK_SECRET e WHATSAPP_VERIFY_TOKEN em test.py settings
- Fix 4: Removido import `pytest` não utilizado em test_middleware.py (ruff F401)
- Fix 5: Quebra de linhas longas em test_webhook.py (ruff E501, max 100 chars)
- Segunda execução: 59 testes passando, 0 falhas, ruff limpo

### Completion Notes List

- **WebhookSignatureMiddleware**: Async-capable dual-mode middleware validando HMAC SHA-256 contra body RAW. Aplica apenas em POST /webhook/. Usa `hmac.compare_digest()` timing-safe. Loga `webhook_signature_invalid` via structlog.
- **TraceIDMiddleware**: Gera UUID trace_id por request, bind via `structlog.contextvars`, adiciona header `X-Trace-ID` na resposta. Unbinds no final do request para evitar leak entre requests.
- **WhatsAppWebhookView**: `adrf.views.APIView` com `async get()` (handshake) e `async post()` (fire-and-forget via `asyncio.create_task`). Processa TODOS os entries/changes via loops. CSRF exempt via decorator.
- **WhatsAppMessageSerializer**: DRF Serializer com validação regex de phone (10-15 dígitos), anti-replay de timestamp (≤300s), e bloqueio de message_type system/unknown.
- **Deduplicação**: `is_duplicate_message()` usando Redis SETNX com key `msg_processed:{id}` e TTL 1h. Async via `redis.asyncio`.
- **Event filtering**: `should_process_event()` extrai mensagens processáveis (text, image, audio, etc.) e ignora silenciosamente status updates, system messages e unknown types.
- **URL routing**: `/webhook/whatsapp/` registrado em `workflows/urls.py` e incluído via `config/urls.py`.
- **Variáveis de ambiente**: `WHATSAPP_WEBHOOK_SECRET`, `WHATSAPP_VERIFY_TOKEN` e `REDIS_URL` adicionados em `base.py`. Já existiam em `.env.example`.
- **Testes**: 29 novos testes (9 middleware isolados + 20 webhook integration/unit) cobrindo todos os 11 cenários da story + edge cases. Total: 63 testes, 0 regressões.

### File List

**Novos:**
- `workflows/middleware/webhook_signature.py` — WebhookSignatureMiddleware (HMAC SHA-256)
- `workflows/middleware/trace_id.py` — TraceIDMiddleware (UUID + structlog contextvars)
- `workflows/views.py` — WhatsAppWebhookView (GET handshake + POST fire-and-forget)
- `workflows/serializers.py` — WhatsAppMessageSerializer (phone regex, timestamp, type)
- `workflows/urls.py` — URL routing (`webhook/whatsapp/`)
- `workflows/utils/deduplication.py` — is_duplicate_message() (Redis SETNX)
- `tests/test_middleware.py` — Testes isolados dos middlewares (9 testes)
- `tests/test_webhook.py` — Testes integração webhook + serializer + filtering (20 testes)

**Modificados:**
- `config/settings/base.py` — Adicionado middlewares + env vars (WHATSAPP_WEBHOOK_SECRET, WHATSAPP_VERIFY_TOKEN, REDIS_URL)
- `config/settings/test.py` — Adicionado WHATSAPP_WEBHOOK_SECRET e WHATSAPP_VERIFY_TOKEN para testes
- `config/urls.py` — Adicionado include de workflows.urls
- `config/settings/production.py` — Adicionado validação obrigatória de WHATSAPP_WEBHOOK_SECRET e WHATSAPP_VERIFY_TOKEN (review fix)
- `workflows/apps.py` — Adicionado merge_contextvars ao structlog configure (review fix)

## Senior Developer Review (AI)

**Reviewer:** Claude Opus 4.6 | **Data:** 2026-03-06 | **Resultado:** Approved (com fixes aplicados)

**Issues encontrados e corrigidos (10):**

| # | Severidade | Issue | Arquivo | Fix |
|---|-----------|-------|---------|-----|
| H1 | HIGH | structlog sem `merge_contextvars` — trace_id não aparecia em logs | `workflows/apps.py` | Adicionado processor |
| H2 | HIGH | `WHATSAPP_WEBHOOK_SECRET` aceita string vazia em produção | `config/settings/production.py` | Adicionado validação |
| H3 | HIGH | `asyncio.create_task()` sem error handler | `workflows/views.py` | Adicionado `_handle_task_exception` callback |
| H4 | HIGH | Redis conexão nova por request (sem pool) | `workflows/utils/deduplication.py` | Singleton com pool interno |
| M1 | MEDIUM | TraceIDMiddleware sem try/finally (leak contextvars) | `workflows/middleware/trace_id.py` | Wrap com try/finally |
| M2 | MEDIUM | Timestamp valida só passado, não futuro | `workflows/serializers.py` | Usado `abs()` conforme ADR-008 |
| M3 | MEDIUM | Teste AC4 não verificava contextvars binding | `tests/test_middleware.py` | 2 novos testes adicionados |
| M4 | MEDIUM | Contagem de testes incorreta (25 vs 27 declarados) | Story file | Corrigido para 29 (com novos testes) |
| L1 | LOW | `_sign_payload` duplicado em 2 test files | — | Mantido (7 linhas, baixo impacto) |
| L2 | LOW | Sem teste para hub.mode ausente | `tests/test_webhook.py` | Teste adicionado |

**Testes pós-review:** 63 passando, 0 falhas, ruff limpo.

## Change Log

| Data | Mudança |
|------|---------|
| 2026-03-06 | Story 1.2 implementada: Webhook WhatsApp + Middleware de Segurança. 10 tasks completadas, 27 novos testes, 59 total passando. |
| 2026-03-06 | Code review adversarial: 10 issues encontrados (4 HIGH, 4 MEDIUM, 2 LOW). 9 corrigidos automaticamente, 4 novos testes adicionados. Total: 63 testes, 0 regressões. Status → done. |
