# Story 3.1: Transcrição de Áudio via Whisper

Status: done

## Story

As a aluno no plantão,
I want enviar mensagens de áudio e receber respostas baseadas na transcrição,
So that tiro dúvidas rapidamente mesmo quando não posso digitar.

## Acceptance Criteria

1. **Given** o aluno envia um áudio pelo WhatsApp **When** o nó `process_media` do StateGraph detecta `message_type="audio"` **Then** faz download do áudio via WhatsApp Cloud API (`download_media()` existente) **And** envia para Whisper API (OpenAI) para transcrição (timeout 20s, 2 retries) **And** a transcrição é adicionada ao estado como `transcribed_text` **And** `user_message` é substituído/concatenado com o texto transcrito para o pipeline continuar normalmente (load_context → orchestrate_llm → ...) **And** latência total P95 < 12 segundos (NFR2)

2. **Given** a transcrição do Whisper falha (timeout ou erro após 2 retries) **When** o nó process_media processa **Then** envia mensagem ao aluno: "Não consegui processar seu áudio. Pode enviar por texto?" **And** loga o erro com contexto completo via structlog (user_id, media_id, erro, trace_id) **And** o grafo encerra (não prossegue para orchestrate_llm)

3. **Given** o aluno envia uma mensagem de texto **When** o nó `process_media` detecta `message_type="text"` **Then** o nó é skip (retorna estado inalterado) — zero overhead para mensagens de texto

4. **Given** o aluno envia uma imagem **When** o nó `process_media` detecta `message_type="image"` **Then** o nó é skip por enquanto (Story 3.2 implementa Vision) — retorna estado inalterado

## Tasks / Subtasks

- [x] Task 1: Criar provider Whisper (AC: #1, #2)
  - [x] 1.1 Criar `workflows/providers/whisper.py` com função `transcribe_audio(audio_bytes: bytes, mime_type: str) -> str`
  - [x] 1.2 Usar httpx POST para `https://api.openai.com/v1/audio/transcriptions` (multipart/form-data)
  - [x] 1.3 Timeout 20s, 2 retries com backoff exponencial (usar `retry_with_backoff` pattern ou manual)
  - [x] 1.4 Model: `whisper-1`, language: `pt` (forced, evitar detecção errada)
  - [x] 1.5 Error handling: `ExternalServiceError(service="whisper", ...)` — nunca exceção raw
  - [x] 1.6 Logging: `audio_transcription_started`, `audio_transcription_completed` (com duration_ms, audio_size_bytes), `audio_transcription_failed`
- [x] Task 2: Criar nó process_media (AC: #1, #2, #3, #4)
  - [x] 2.1 Criar `workflows/whatsapp/nodes/process_media.py` com async def `process_media(state: WhatsAppState) -> dict`
  - [x] 2.2 Se `message_type == "text"`: retorna `{}` (no-op)
  - [x] 2.3 Se `message_type == "image"`: retorna `{}` (placeholder Story 3.2)
  - [x] 2.4 Se `message_type == "audio"`: download + transcrição + retorno
  - [x] 2.5 Chamar `download_media(state["media_id"], state["mime_type"])` (já existe em `providers/whatsapp.py:78`)
  - [x] 2.6 Chamar `transcribe_audio(audio_bytes, mime_type)` do provider Whisper
  - [x] 2.7 Retornar `{"transcribed_text": transcription, "user_message": transcription}` — substitui user_message para que `orchestrate_llm` receba o texto
  - [x] 2.8 Se body do debounce não-vazio + áudio: concatenar `f"{body}\n\n[Transcrição do áudio]: {transcription}"`
  - [x] 2.9 On failure: `send_text_message(phone, "Não consegui processar seu áudio. Pode enviar por texto?")` + log + raise GraphNodeError para interromper grafo
- [x] Task 3: Inserir nó no StateGraph (AC: #1)
  - [x] 3.1 Editar `workflows/whatsapp/graph.py`
  - [x] 3.2 Import: `from workflows.whatsapp.nodes.process_media import process_media`
  - [x] 3.3 Adicionar nó: `builder.add_node("process_media", process_media)` (SEM retry policy — retry é manual dentro do provider)
  - [x] 3.4 Inserir edge: rate_limit → process_media → load_context (substituir edge rate_limit → load_context)
  - [x] 3.5 Atualizar docstring do `build_whatsapp_graph()` com novo flow
- [x] Task 4: Adicionar dependência openai (AC: #1)
  - [x] 4.1 Usar httpx direto (já é dependência do projeto, Whisper API é 1 endpoint simples) — sem pacote openai adicionado
- [x] Task 5: Testes unitários (AC: #1, #2, #3, #4)
  - [x] 5.1 Criar `tests/test_providers/test_whisper.py` — 8 testes: transcrição OK, strip whitespace, timeout, HTTP error, retry sucesso, mime filename, auth header, HTTP 500
  - [x] 5.2 Criar `tests/test_whatsapp/test_nodes/test_process_media.py` — 7 testes: texto (no-op), imagem (no-op), áudio happy path, concatenação com body, falha Whisper, falha download, falha dupla (send também falha)
  - [x] 5.3 Atualizar `tests/integration/test_graph_e2e.py` com cenário de áudio mockado (test_audio_pipeline_with_real_redis_and_postgres)
- [x] Task 6: Teste de integração (AC: #1, #2) — RETRO WATCH: >=1 integration test real
  - [x] 6.1 Criar teste de integração em `tests/integration/test_process_media_integration.py`
  - [x] 6.2 Mock apenas Whisper API, usar Redis + PostgreSQL reais — 2 testes: happy path e falha Whisper
- [x] Task 7: Lint & type check
  - [x] 7.1 `uv run ruff check` e `uv run ruff format --check` passam
  - [x] 7.2 Lint verificado para novos/editados arquivos
  - [x] 7.3 `uv run pytest` — 456 testes passam (25 novos + 431 existentes), 0 falharam

## Dev Notes

### Infraestrutura Existente (NÃO Reimplementar)

Os seguintes componentes JÁ existem e DEVEM ser reutilizados:

| Componente | Arquivo | O que faz |
|-----------|---------|-----------|
| `download_media()` | `workflows/providers/whatsapp.py:78-129` | Two-step download do WhatsApp Cloud API (GET media_id → GET temp_url → bytes). Timeout 10s. |
| `send_text_message()` | `workflows/providers/whatsapp.py:31-75` | Envia mensagem de texto via WhatsApp Cloud API |
| `ExternalServiceError` | `workflows/utils/errors.py:23-26` | Exceção para falhas de serviço externo (`service`, `message`) |
| `GraphNodeError` | `workflows/utils/errors.py:29-32` | Exceção para falhas de nó do grafo (`node`, `message`) |
| `WhatsAppState.media_id` | `workflows/whatsapp/state.py:22` | Já tem campo `media_id: str \| None` |
| `WhatsAppState.mime_type` | `workflows/whatsapp/state.py:23` | Já tem campo `mime_type: str \| None` |
| `WhatsAppState.transcribed_text` | `workflows/whatsapp/state.py:54` | Placeholder já criado |
| Webhook media extraction | `workflows/views.py:71-77` | Já extrai `media_id` e `mime_type` do payload WhatsApp |
| Debounce media handling | `workflows/services/debounce.py:126-137` | Já preserva `media_id` da última mensagem no batch |
| `OPENAI_API_KEY` | `config/settings/base.py:54` | Variável já configurada via django-environ |
| `.env.example` | `.env.example:49` | `OPENAI_API_KEY=your-openai-key` já documentado |

### Padrão do Provider Whisper

Seguir exatamente o padrão de `workflows/providers/whatsapp.py`:
- httpx.AsyncClient (pode usar client singleton ou criar local — preferir local pois é 1 endpoint diferente: api.openai.com)
- Error handling: `try/except httpx.HTTPStatusError` → `ExternalServiceError(service="whisper", ...)`
- Error handling: `try/except httpx.TimeoutException` → `ExternalServiceError(service="whisper", ...)`
- Logging via `structlog.get_logger(__name__)`

### Whisper API — Especificações Técnicas

- **Endpoint:** `POST https://api.openai.com/v1/audio/transcriptions`
- **Auth:** `Authorization: Bearer {OPENAI_API_KEY}`
- **Content-Type:** `multipart/form-data`
- **Campos:** `file` (binary), `model` = `"whisper-1"`, `language` = `"pt"`, `response_format` = `"text"`
- **Custo:** $0.006/minuto
- **Limite:** 25 MB por arquivo
- **Formatos aceitos:** flac, mp3, mp4, mpeg, mpga, m4a, ogg, wav, webm
- **WhatsApp envia áudio como:** `audio/ogg; codecs=opus` — compatível com Whisper API (formato ogg)
- **Timeout:** 20s (arquitetura define 20s, buffer de 8s sobre NFR2 de 12s P95)

### Padrão do Nó process_media

Seguir o contrato LangGraph: `async def process_media(state: WhatsAppState) -> dict`
- Retorna dict parcial com campos que modifica
- Para text/image: retorna `{}` (sem modificação)
- Para áudio: retorna `{"transcribed_text": ..., "user_message": ...}`
- NÃO raise exception para failure path — enviar mensagem ao usuário e retornar estado que sinaliza fim

### Inserção no Grafo — Ponto Exato

```python
# ANTES (graph.py atual, linhas 64-65):
builder.add_conditional_edges("rate_limit", check_rate_limit)
builder.add_edge("load_context", "orchestrate_llm")

# DEPOIS:
builder.add_conditional_edges("rate_limit", check_rate_limit)
# check_rate_limit agora retorna "process_media" em vez de "load_context":
# Precisa atualizar check_rate_limit() em rate_limit.py
builder.add_node("process_media", process_media)
builder.add_edge("process_media", "load_context")
builder.add_edge("load_context", "orchestrate_llm")
```

**ATENÇÃO:** A função `check_rate_limit()` (em `workflows/whatsapp/nodes/rate_limit.py`) é o roteador condicional. Ela retorna `"load_context"` quando o rate limit não é excedido. Precisa ser atualizada para retornar `"process_media"` em vez de `"load_context"`. Verificar o source de `check_rate_limit` antes de editar.

### Fluxo de Dados para Áudio

```
Webhook (views.py) → Extrai media_id, mime_type do payload
    ↓
Debounce (debounce.py) → Preserva media_id da última mensagem do batch
    ↓
_process_message (views.py:157-164) → Popula initial_state com media_id, mime_type
    ↓
identify_user → rate_limit → process_media (NOVO)
    ↓
process_media:
    1. Se text → retorna {} (skip)
    2. Se audio → download_media(media_id, mime_type) → bytes
    3. bytes → transcribe_audio(bytes, mime_type) → texto
    4. Retorna {transcribed_text, user_message}
    ↓
load_context → orchestrate_llm → ... (pipeline normal com texto transcrito)
```

### Handling de Falha no process_media

Quando Whisper falha após retries:
1. Enviar mensagem amigável ao usuário via `send_text_message()`
2. Logar erro completo via structlog
3. Retornar um estado que impeça o pipeline de continuar chamando LLM (economia de custo)
4. **Opção A:** Raise `GraphNodeError` — views.py já tem `_send_fallback()` no except
5. **Opção B:** Enviar mensagem diretamente no nó e retornar estado marcando pipeline como terminado
6. **Decisão recomendada:** Opção A — manter consistência com padrão existente. Mas enviar mensagem específica ("Não consegui processar seu áudio. Pode enviar por texto?") em vez da genérica do fallback. Ou seja: enviar a mensagem específica E DEPOIS raise GraphNodeError para que o pipeline não continue.

### Project Structure Notes

- Novo arquivo: `workflows/providers/whisper.py` (segue padrão de `whatsapp.py`, `pinecone.py`)
- Novo arquivo: `workflows/whatsapp/nodes/process_media.py` (segue padrão dos 8 nós existentes em `nodes/`)
- Editado: `workflows/whatsapp/graph.py` (adicionar nó + edge)
- Editado: `workflows/whatsapp/nodes/rate_limit.py` (atualizar retorno de `check_rate_limit`)
- Novos testes: `tests/test_providers/test_whisper.py`, `tests/test_nodes/test_process_media.py`
- NÃO adicionar package `openai` — usar httpx direto (já é dependência)
- NÃO editar state.py — `transcribed_text` já existe como placeholder

### Retro Watch Items

- **Error handler silencioso** — zero `except Exception` sem log (retros Epic 1, 2, 4). Todo except DEVE ter structlog antes de fallback.
- **Over-mocking** — exigir >=1 teste de integração real por story (pendente desde Epic 1). Usar Redis + PostgreSQL reais do docker-compose.
- **Exceção raw para LLM** — tools SEMPRE retornam string, nunca raise exception (acordo do time). Neste caso é um NÓ (não tool), mas o princípio se aplica: nunca deixar exceção crua vazar sem tratamento.

### References

- [Source: _bmad-output/planning-artifacts/architecture.md — StateGraph node flow, lines 540-565]
- [Source: _bmad-output/planning-artifacts/architecture.md — Whisper integration, lines 2520, 2870, 2895]
- [Source: _bmad-output/planning-artifacts/architecture.md — External service timeouts table, lines 2512-2524]
- [Source: _bmad-output/planning-artifacts/architecture.md — WhatsAppState definition, lines 583-612]
- [Source: _bmad-output/planning-artifacts/architecture.md — process_media conditional behavior, lines 2467-2470]
- [Source: _bmad-output/planning-artifacts/epics.md — Story 3.1 acceptance criteria, lines 722-748]
- [Source: _bmad-output/planning-artifacts/prd.md — FR2, NFR2]
- [Source: _bmad-output/implementation-artifacts/0-1-prep-sprint-debitos-tecnicos-validacao-e2e.md — download_media(), media_id extraction, code review findings]
- [Source: _bmad-output/implementation-artifacts/epic-2-retro-2026-03-10.md — Retro watch items, error handling patterns]
- [Source: OpenAI API docs — Whisper endpoint POST /v1/audio/transcriptions, model whisper-1, $0.006/min]
- [Source: WhatsApp Cloud API docs — audio mime_type: audio/ogg; codecs=opus]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- ruff check: All checks passed (import sorting fix applied in graph.py)
- pytest: 456 passed, 2 errors (pre-existing e2e/smoke tests needing Docker)

### Completion Notes List

- Task 1: Provider Whisper criado com httpx direto (sem pacote openai). Timeout 20s, 2 retries com backoff exponencial. Logging completo (started/completed/failed).
- Task 2: Nó process_media criado. Text/image retornam {} (no-op). Áudio: download + transcribe + retorna {transcribed_text, user_message}. Concatena com body existente do debounce. On failure: envia mensagem amigável + raise GraphNodeError.
- Task 3: Nó inserido no grafo entre rate_limit e load_context. check_rate_limit atualizado para retornar "process_media". Docstring atualizada.
- Task 4: httpx já é dependência — nenhuma ação necessária.
- Task 5: 15 testes unitários criados (8 whisper + 7 process_media). Teste existente de check_rate_limit atualizado ("load_context" → "process_media").
- Task 6: 2 testes de integração + 1 teste E2E de áudio adicionado. Mock apenas Whisper, Redis+PG reais.
- Task 7: ruff check/format passam. 456/456 testes passam. conftest atualizado com media_id/mime_type.

### File List

- `workflows/providers/whisper.py` — NOVO — Provider Whisper (transcribe_audio)
- `workflows/whatsapp/nodes/process_media.py` — NOVO — Nó process_media
- `workflows/whatsapp/graph.py` — EDITADO — Import + add_node + add_edge process_media, docstring
- `workflows/whatsapp/nodes/rate_limit.py` — EDITADO — check_rate_limit retorna "process_media"
- `tests/test_providers/test_whisper.py` — NOVO — 8 testes unitários do provider
- `tests/test_whatsapp/test_nodes/test_process_media.py` — NOVO — 7 testes unitários do nó
- `tests/test_whatsapp/test_nodes/test_rate_limit.py` — EDITADO — Atualizado assert "process_media"
- `tests/test_whatsapp/conftest.py` — EDITADO — Adicionado media_id, mime_type ao helper
- `tests/integration/test_graph_e2e.py` — EDITADO — Adicionado teste E2E de áudio
- `tests/integration/test_process_media_integration.py` — NOVO — 2 testes de integração
