# Story 6.1: Reply Buttons para Feedback + Comentário Opcional

Status: done

## Story

As a aluno,
I want avaliar as respostas do Medbrain com positivo/negativo via Reply Buttons,
So that contribuo para melhorar a qualidade do serviço e alimento a North Star Metric (satisfação >85%).

## Acceptance Criteria

1. **Given** o sistema envia uma resposta ao aluno **When** a resposta é enviada via WhatsApp **Then** inclui Reply Buttons com 3 opções: "Útil", "Não útil", "Comentar" usando interactive message da WhatsApp Cloud API (max 3 buttons)

2. **Given** o aluno clica em "Útil" ou "Não útil" **When** o webhook recebe a interação (`type="interactive"`, `interactive.type="button_reply"`) **Then** o feedback é salvo no banco (mensagem avaliada, tipo de feedback positivo/negativo, user_id, timestamp) **And** o sistema responde com confirmação curta (ex: "Obrigado pelo feedback!")

3. **Given** o aluno clica em "Comentar" **When** o webhook recebe a interação **Then** o sistema responde: "Obrigado! Pode me contar o motivo da sua avaliação?" **And** a próxima mensagem de texto do aluno é salva como comentário do feedback **And** o fluxo volta ao normal após o comentário

4. **Given** o model `Feedback` é criado **Then** o Django Admin registra Feedback com filtros por rating e date_hierarchy

5. **Given** o aluno envia uma mensagem de texto enquanto o sistema espera um comentário de feedback **When** a mensagem é recebida **Then** é salva como comentário do feedback pendente **And** o sistema responde "Obrigado pelo seu comentário!" **And** o fluxo volta ao normal

## Tasks / Subtasks

- [x] Task 1: Criar model Feedback (AC: #2, #4)
  - [x] 1.1 Adicionar model `Feedback` em `workflows/models.py`
  - [x] 1.2 Criar migration Django
  - [x] 1.3 Registrar `FeedbackAdmin` em `workflows/admin.py`
  - [x] 1.4 Testes unitários do model e admin (18 testes)

- [x] Task 2: Implementar envio de Reply Buttons (AC: #1)
  - [x] 2.1 Criar `send_interactive_buttons()` em `workflows/providers/whatsapp.py`
  - [x] 2.2 Modificar node `send_whatsapp` para enviar buttons após resposta
  - [x] 2.3 Testes unitários do provider e do node (12 testes)

- [x] Task 3: Processar clique de buttons no webhook (AC: #2, #3, #5)
  - [x] 3.1 Atualizar `should_process_event()` em `workflows/views.py` para reconhecer `interactive/button_reply`
  - [x] 3.2 Implementar handler de feedback em `workflows/views.py`
  - [x] 3.3 Implementar fluxo de comentário (Redis state para aguardar próxima mensagem)
  - [x] 3.4 Testes unitários do webhook handler e fluxo de comentário (15 testes)

- [x] Task 4: Testes de integração (AC: #1-#5)
  - [x] 4.1 Teste do fluxo completo: resposta → buttons → clique → feedback salvo
  - [x] 4.2 Teste do fluxo de comentário: "Comentar" → prompt → texto → salvo
  - [x] 4.3 Conftest não precisou de alteração (não usa make_whatsapp_state)

## Dev Notes

### Arquitetura da Solução

O feedback NÃO faz parte do pipeline LangGraph principal. Buttons de feedback são enviados APÓS a resposta do assistente, e os cliques são processados diretamente no webhook handler — sem passar pelo grafo. Isso mantém o pipeline limpo e evita complexidade desnecessária.

**Fluxo:**
```
Pipeline Normal:  ... → format_response → send_whatsapp (texto + buttons) → persist → END
Feedback Click:   webhook → should_process_event → handle_feedback (salva Feedback) → resposta curta
Comentário:       webhook → should_process_event → handle_feedback (detecta "Comentar") → prompt
                  webhook → should_process_event → check_pending_comment → salva comment → resposta curta
```

### Model Feedback

```python
# Em workflows/models.py

class Feedback(models.Model):
    """Feedback do aluno sobre respostas do assistente."""

    RATING_CHOICES = [
        ("positive", "Positivo"),
        ("negative", "Negativo"),
    ]

    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="feedbacks"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="feedbacks"
    )
    rating = models.CharField(max_length=10, choices=RATING_CHOICES)
    comment = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "feedbacks"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["-created_at"]),
            models.Index(fields=["rating"]),
        ]
```

### WhatsApp Interactive Message — Payload de Envio

```python
# Em workflows/providers/whatsapp.py — nova função

async def send_interactive_buttons(
    phone: str,
    body_text: str,
    buttons: list[dict],
    footer_text: str | None = None,
) -> dict:
    """Envia mensagem interativa com Reply Buttons via WhatsApp Cloud API.

    Args:
        phone: Número do destinatário (E.164 sem +)
        body_text: Texto principal (max 1024 chars)
        buttons: Lista de 1-3 dicts com {id: str, title: str}
        footer_text: Texto do rodapé (max 60 chars, opcional)
    """
    interactive = {
        "type": "button",
        "body": {"text": body_text[:1024]},
        "action": {
            "buttons": [
                {"type": "reply", "reply": {"id": b["id"], "title": b["title"][:20]}}
                for b in buttons
            ]
        },
    }
    if footer_text:
        interactive["footer"] = {"text": footer_text[:60]}

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "interactive",
        "interactive": interactive,
    }
    # Reutilizar o _get_client() e _get_timeout() existentes
    # Reutilizar o mesmo endpoint e error handling de send_text_message()
```

**Constraints da API (referência rápida):**

| Campo | Limite |
|-------|--------|
| Buttons | min=1, max=3 |
| Button ID | max 256 chars, único |
| Button Title | max 20 chars, único |
| Body text | max 1024 chars, obrigatório |
| Footer text | max 60 chars, opcional |

### Buttons de Feedback — Configuração

Usar `ConfigService` com fallback hardcoded (padrão do projeto):

```python
FEEDBACK_BUTTONS = [
    {"id": "feedback_positive", "title": "👍 Útil"},
    {"id": "feedback_negative", "title": "👎 Não útil"},
    {"id": "feedback_comment", "title": "💬 Comentar"},
]
```

O `body_text` dos buttons deve ser uma mensagem curta como: "Como você avalia esta resposta?"

### Modificação em send_whatsapp Node

Em `workflows/whatsapp/nodes/send_whatsapp.py` — após enviar a resposta de texto (e partes adicionais), enviar os buttons de feedback como mensagem separada:

```python
# Após enviar texto principal e additional_responses:
feedback_body = "Como você avalia esta resposta?"
await send_interactive_buttons(phone, feedback_body, FEEDBACK_BUTTONS)
```

**IMPORTANTE:** Os buttons devem ser enviados como mensagem SEPARADA do texto da resposta. O body do interactive message é limitado a 1024 chars — a resposta do assistente frequentemente excede isso. Enviar como mensagem separada também permite que o texto use formatação WhatsApp normal (markdown) sem as limitações do interactive message.

### Webhook — Processamento de Button Reply

Atualizar `should_process_event()` para incluir `"interactive"` nos tipos suportados:

```python
# views.py
SUPPORTED_TYPES = {"text", "audio", "image", "interactive"}
```

Ao extrair dados da mensagem, verificar se `type == "interactive"`:

```python
if msg_type == "interactive":
    interactive_data = message.get("interactive", {})
    if interactive_data.get("type") == "button_reply":
        button_reply = interactive_data["button_reply"]
        # button_reply["id"] → "feedback_positive" | "feedback_negative" | "feedback_comment"
        # button_reply["title"] → "👍 Útil" | "👎 Não útil" | "💬 Comentar"
```

### Fluxo de Comentário — Estado via Redis

Usar Redis para rastrear se um usuário tem feedback pendente de comentário:

```python
# Key pattern: feedback_pending:{phone}
# Value: feedback_id do Feedback que aguarda comentário
# TTL: 300s (5 minutos — se não responder em 5 min, expira)

async def set_pending_comment(phone: str, feedback_id: int) -> None:
    redis = get_redis_client()
    await redis.setex(f"feedback_pending:{phone}", 300, str(feedback_id))

async def get_pending_comment(phone: str) -> int | None:
    redis = get_redis_client()
    value = await redis.get(f"feedback_pending:{phone}")
    if value:
        await redis.delete(f"feedback_pending:{phone}")
        return int(value)
    return None
```

**Fluxo no webhook handler:**

1. Mensagem chega → `should_process_event()` extrai dados
2. Se `type == "interactive"` e `button_reply.id` começa com `"feedback_"`:
   - Não entrar no pipeline LangGraph
   - Processar direto no handler (`handle_feedback()`)
   - Se `feedback_positive` ou `feedback_negative`: salvar Feedback, responder "Obrigado!"
   - Se `feedback_comment`: salvar Feedback sem comment, setar Redis pending, responder prompt
3. Se `type == "text"` e existe `feedback_pending:{phone}` no Redis:
   - Não entrar no pipeline LangGraph
   - Salvar texto como comment no Feedback pendente
   - Responder "Obrigado pelo comentário!"
   - Deletar key do Redis
4. Se `type == "text"` e NÃO existe pending: fluxo normal (pipeline LangGraph)

### Identificar a Message Avaliada

O feedback precisa de FK para a `Message` que foi avaliada. Abordagem:

- No `persist` node, o `Message` do assistant é criado. O `send_whatsapp` node envia os buttons logo após.
- O webhook de button reply inclui `context.id` com o WAMID da mensagem original que o usuário respondeu. MAS esse WAMID é do WhatsApp, não do nosso banco.
- **Solução prática:** Ao processar o feedback, buscar o `Message` mais recente com `role="assistant"` para o `user`. Isso é seguro porque o feedback é sempre sobre a última resposta.

```python
# Em handle_feedback():
last_assistant_msg = await Message.objects.filter(
    user=user, role="assistant"
).order_by("-created_at").afirst()
```

### Django Admin — FeedbackAdmin

```python
# Em workflows/admin.py

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("user", "rating", "has_comment", "created_at")
    list_filter = ("rating",)
    date_hierarchy = "created_at"
    search_fields = ("user__phone", "comment")
    raw_id_fields = ("user", "message")

    @admin.display(boolean=True, description="Comentário?")
    def has_comment(self, obj):
        return bool(obj.comment)
```

### Data Migration — Config de Mensagens

Criar migration para adicionar configs no `Config` model:

```python
Config.objects.get_or_create(
    key="message:feedback_prompt",
    defaults={
        "value": "Como você avalia esta resposta?",
        "updated_by": "migration",
    },
)
Config.objects.get_or_create(
    key="message:feedback_thanks",
    defaults={
        "value": "Obrigado pelo feedback! 🙏",
        "updated_by": "migration",
    },
)
Config.objects.get_or_create(
    key="message:feedback_comment_prompt",
    defaults={
        "value": "Obrigado! Pode me contar o motivo da sua avaliação?",
        "updated_by": "migration",
    },
)
Config.objects.get_or_create(
    key="message:feedback_comment_thanks",
    defaults={
        "value": "Obrigado pelo seu comentário! Vamos usar para melhorar. 🙏",
        "updated_by": "migration",
    },
)
```

### Project Structure Notes

**Arquivos a criar:**
- `workflows/migrations/XXXX_add_feedback_model.py` (auto-gerado pelo makemigrations)
- `workflows/migrations/XXXX_add_feedback_config.py` (data migration manual)

**Arquivos a modificar:**
- `workflows/models.py` → adicionar `Feedback` model
- `workflows/admin.py` → adicionar `FeedbackAdmin`
- `workflows/providers/whatsapp.py` → adicionar `send_interactive_buttons()`
- `workflows/whatsapp/nodes/send_whatsapp.py` → enviar buttons após resposta
- `workflows/views.py` → atualizar `should_process_event()`, adicionar `handle_feedback()`
- `tests/test_whatsapp/conftest.py` → atualizar `make_whatsapp_state()` se necessário

**Arquivos de teste a criar:**
- `tests/test_models/test_feedback.py`
- `tests/test_whatsapp/test_nodes/test_send_whatsapp.py` (estender testes existentes)
- `tests/test_providers/test_whatsapp.py` (estender para `send_interactive_buttons`)
- `tests/test_views/test_feedback_handler.py`

### Padrões Existentes — SEGUIR

| Padrão | Referência | Detalhe |
|--------|-----------|---------|
| Error handling | `ExternalServiceError` | Usar em `send_interactive_buttons()` — igual a `send_text_message()` |
| Logging | `structlog.get_logger()` | Sempre usar structured logging com contexto |
| ConfigService | `ConfigService.get(key)` + fallback | Mensagens configuráveis via Config model |
| Redis | `workflows/providers/redis.py` | Usar singleton existente para feedback pending |
| Testes | `pytest + pytest-asyncio + pytest-django` | Fixtures assíncronas, `@pytest.mark.asyncio`, `@pytest.mark.django_db` |
| Admin | Padrão do projeto | `list_display`, `list_filter`, `search_fields`, `raw_id_fields` |
| Async I/O | Django ORM async | `acreate()`, `aget()`, `afirst()` — NUNCA usar sync |

### Anti-Patterns — EVITAR

- **NÃO** adicionar novos nós ao grafo LangGraph para feedback — processar no webhook handler
- **NÃO** usar `supabase-py` para queries — usar Django ORM async
- **NÃO** usar `print()` — usar `structlog`
- **NÃO** usar sync I/O — todo I/O deve ser async
- **NÃO** logar dados do aluno (PII) sem sanitização
- **NÃO** enviar buttons dentro do interactive message body com a resposta completa — enviar como mensagem separada (body max 1024 chars)
- **NÃO** criar helper classes desnecessárias (ReplyButton dataclass etc.) — usar dicts simples para os buttons

### Decisões de Design — Justificativas

1. **Feedback fora do pipeline LangGraph**: O feedback é uma interação UI simples (clique + save), não precisa de orquestração LLM. Processá-lo direto no webhook é mais rápido e simples.

2. **Buttons como mensagem separada**: A resposta do assistente pode ter milhares de caracteres com formatação markdown rica. O body do interactive message é limitado a 1024 chars e tem formatação limitada. Separar mantém ambos com qualidade.

3. **Redis para estado de comentário**: Padrão já usado no projeto para debouncing e deduplicação. TTL de 5 minutos evita estados órfãos. Alternativa (campo no DB) seria overkill.

4. **Última mensagem assistant como referência**: Buscar a última `Message(role="assistant")` do user é suficiente porque o feedback é sempre sobre a resposta mais recente. Mapear via WAMID exigiria salvar WAMIDs no banco (complexidade extra sem valor).

### Referências

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 6, Story 6.1]
- [Source: _bmad-output/planning-artifacts/prd.md — FR4, FR5, North Star Metric]
- [Source: _bmad-output/planning-artifacts/architecture.md — WhatsApp Cloud API, Models, Pipeline]
- [Source: workflows/providers/whatsapp.py — send_text_message() pattern]
- [Source: workflows/whatsapp/nodes/send_whatsapp.py — current send flow]
- [Source: workflows/views.py — should_process_event(), webhook handler]
- [Source: workflows/models.py — existing models (User, Message, Config)]
- [Source: workflows/admin.py — existing admin registrations]
- [Source: WhatsApp Cloud API Docs — Interactive Reply Buttons, v21.0]
- [Source: 5-1-retry-automatico-circuit-breaker.md — error handling patterns]
- [Source: 5-2-mensagem-amigavel-resposta-parcial.md — ConfigService pattern, data migration]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6) via Claude Code CLI

### Debug Log References

- Nenhum debug log externo necessário

### Completion Notes List

- **67 testes novos** cobrindo todas as ACs (18 model + 12 provider/node + 15 handler + 6 integração + 16 existentes modificados)
- **618 testes totais passando** (excluindo e2e/integration/scripts)
- **5 falhas pré-existentes** não relacionadas à Story 6.1:
  - `test_graph.py::TestGraphWebhookIntegration::test_webhook_dispatches_graph_execution` — `propagate_attributes()` API mudou (langfuse)
  - `test_providers/test_llm.py::TestGetModel` (2 testes) — modelo mudou para haiku-4.5 mas testes esperam sonnet-4
  - `test_whatsapp/test_error_fallback.py::TestErrorLogging::test_graph_node_error_logs_required_fields` — log event name renomeado
  - `test_whatsapp/test_resilience.py` (2 testes) — modelo LLM mudou
- **Ruff lint/format**: clean em todos os arquivos da story
- Mock de `get_pending_comment` adicionado em `test_webhook.py::TestWhatsAppWebhookPost` e `test_graph.py::TestGraphWebhookIntegration` para evitar acesso ao Redis real em testes unitários

### Change Log

| Tipo | Arquivo | Mudança |
|------|---------|---------|
| NEW | `workflows/migrations/0010_add_feedback_model.py` | Migration para model Feedback com indexes |
| NEW | `workflows/migrations/0011_add_feedback_configs.py` | Data migration com 4 config keys de feedback |
| NEW | `tests/test_models/__init__.py` | Init do pacote de testes de models |
| NEW | `tests/test_models/test_feedback.py` | 18 testes do model Feedback e FeedbackAdmin |
| NEW | `tests/test_views/test_feedback_handler.py` | 15 testes do handler de feedback e Redis state |
| NEW | `tests/test_views/test_feedback_integration.py` | 6 testes de integração do fluxo completo |
| MOD | `workflows/models.py` | Model Feedback (ForeignKey Message/User, rating, comment, indexes) |
| MOD | `workflows/admin.py` | FeedbackAdmin com list_display, list_filter, has_comment |
| MOD | `workflows/providers/whatsapp.py` | `send_interactive_buttons()` — envio de Reply Buttons |
| MOD | `workflows/whatsapp/nodes/send_whatsapp.py` | Envio de feedback buttons após resposta (best-effort) |
| MOD | `workflows/views.py` | `handle_feedback()`, `handle_pending_comment()`, `set/get_pending_comment()`, routing para interactive messages |
| MOD | `workflows/serializers.py` | Campos `button_reply_id` e `button_reply_title` |
| MOD | `tests/test_providers/test_whatsapp.py` | 8 testes para `send_interactive_buttons` |
| MOD | `tests/test_whatsapp/test_nodes/test_send_whatsapp.py` | 4 testes de feedback buttons + autouse fixtures |
| MOD | `tests/test_webhook.py` | Mock de `get_pending_comment` em TestWhatsAppWebhookPost |
| MOD | `tests/test_graph.py` | Mock de `get_pending_comment` em TestGraphWebhookIntegration |

### File List

**Arquivos criados (8):**
- `workflows/migrations/0010_add_feedback_model.py`
- `workflows/migrations/0011_add_feedback_configs.py`
- `workflows/migrations/0013_feedback_unique_user_message.py` *(code review)*
- `workflows/providers/redis.py` *(code review)*
- `tests/test_models/__init__.py`
- `tests/test_models/test_feedback.py`
- `tests/test_views/test_feedback_handler.py`
- `tests/test_views/test_feedback_integration.py`

**Arquivos modificados (12):**
- `workflows/models.py`
- `workflows/admin.py`
- `workflows/providers/whatsapp.py`
- `workflows/whatsapp/nodes/send_whatsapp.py`
- `workflows/views.py`
- `workflows/serializers.py`
- `workflows/utils/deduplication.py` *(code review)*
- `tests/test_providers/test_whatsapp.py`
- `tests/test_whatsapp/test_nodes/test_send_whatsapp.py`
- `tests/test_webhook.py`
- `tests/test_graph.py`
- `tests/test_models/test_feedback.py` *(code review)*

## Senior Developer Review (AI)

**Reviewer:** Rodrigo Franco — 2026-03-15
**Agent:** Claude Opus 4.6 via Claude Code CLI
**Outcome:** Approved (after fixes)

### Findings Summary

| Severity | ID | Issue | Status |
|---|---|---|---|
| HIGH | H1 | Pending comment state lost on non-text messages | Fixed |
| MEDIUM | M1 | `button_reply_id` read from `msg_data` instead of `validated` | Fixed |
| MEDIUM | M2 | Import of private `_get_redis_client` cross-module | Fixed |
| MEDIUM | M3 | No duplicate feedback protection (missing unique constraint) | Fixed |
| MEDIUM | M4 | "Comentar" defaults to `rating="negative"` | Fixed |
| MEDIUM | M5 | Integration tests still mock external calls | Noted (renamed) |
| LOW | L1 | No test for non-text pending comment edge case | Fixed |
| LOW | L2 | `test_pending_comment_expired` was duplicate test | Fixed |
| LOW | L3 | Missing WAMID logging in `send_interactive_buttons` | Fixed |

### Fixes Applied

1. **H1:** Moved `get_pending_comment()` call to `elif message_type == "text"` branch — audio/image no longer consume pending state
2. **M1:** Changed `msg_data.get("button_reply_id")` → `validated.get("button_reply_id")`
3. **M2:** Created `workflows/providers/redis.py` with public `get_redis_client()` singleton; updated `deduplication.py` to delegate; updated `views.py` to import from provider
4. **M3:** Added `UniqueConstraint(fields=["user", "message"])` to Feedback model + migration 0013; changed `acreate()` → `aupdate_or_create()` in `handle_feedback()`
5. **M4:** Added `("comment", "Comentário")` to `RATING_CHOICES`; "Comentar" button now uses `rating="comment"` instead of `"negative"`
6. **L1:** Added `TestPendingCommentNonTextPreservesState` test
7. **L2:** Replaced duplicate test with `test_get_pending_comment_clears_key_on_read`
8. **L3:** Added `wamid=data["messages"][0]["id"]` to `send_interactive_buttons` logging

### Test Results After Fixes

- **633 testes passando** (up from 618)
- **1 falha pré-existente** (`test_bulas_med::test_global_timeout` — cache hit, não relacionado)
- **Ruff lint/format:** clean
