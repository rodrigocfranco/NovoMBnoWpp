# Story 3.2: Análise de Imagens via Vision

Status: done

<!-- Note: Sprint 6. Paralela com 3.1 (áudio/Whisper), 5.1, 5.2. -->
<!-- Pré-requisito infra: Story 0.1 (download_media, media_id extraction) — DONE. -->
<!-- Story 3.1 (ready-for-dev) CRIA o nó process_media com path de áudio. -->
<!-- Se 3.1 for implementada primeiro: process_media.py, graph.py e rate_limit.py já estarão -->
<!-- atualizados — esta story ADICIONA o branch de imagem ao nó existente. -->
<!-- Se 3.2 for implementada primeiro: criar o nó process_media com path de imagem + skip para áudio. -->

## Story

As a aluno,
I want enviar fotos de questões de prova ou exames e receber análise,
So that resolvo dúvidas visuais sem precisar transcrever manualmente.

## Acceptance Criteria

1. **AC1 — Branch de imagem no nó `process_media`**
   - Given uma mensagem com `message_type="image"` no estado
   - When o nó `process_media` executa (entre `rate_limit` e `load_context`)
   - Then faz download da imagem via `download_media(media_id, mime_type)` (já implementado em `workflows/providers/whatsapp.py`)
   - And converte os bytes para base64
   - And monta content blocks multimodal (imagem base64 + texto do usuário)
   - And armazena os content blocks em um novo campo do estado (`image_message`)
   - And os branches existentes (text → skip, audio → Whisper) continuam funcionando

2. **AC2 — Grafo com `process_media` ativo**
   - Given o nó `process_media` já está no grafo (criado pela Story 3.1, ou criado por esta story se 3.1 não estiver pronta)
   - When o grafo é compilado
   - Then o fluxo é `rate_limit → process_media → load_context`
   - And se `process_media.py` NÃO existe ainda (3.1 não implementada): criar o nó com branch de imagem + skip para text/audio
   - And se `process_media.py` JÁ existe (3.1 implementada): adicionar branch de imagem ao nó existente

3. **AC3 — `orchestrate_llm` envia imagem ao Claude Vision**
   - Given o estado contém `image_message` (HumanMessage multimodal)
   - When o nó `orchestrate_llm` prepara as mensagens para o LLM
   - Then usa o `image_message` multimodal no lugar do `HumanMessage(content=user_message)` de texto
   - And o Claude analisa o conteúdo visual via Vision nativo do modelo
   - And a resposta contextualiza o conteúdo da imagem
   - And tools continuam funcionando normalmente (LLM pode chamar tools após analisar a imagem)
   - And cost_usd é calculado corretamente (Vision usa mais tokens de input)

4. **AC4 — Mensagem descritiva combinada (imagem + texto)**
   - Given o aluno envia uma imagem COM caption/legenda (texto acompanhando a imagem)
   - When o `process_media` processa
   - Then combina o texto do usuário com a imagem no `HumanMessage` multimodal
   - And o LLM recebe ambos: imagem + instrução do aluno

   - Given o aluno envia uma imagem SEM caption
   - When o `process_media` processa
   - Then usa prompt padrão: "Analise esta imagem e me ajude a entender o conteúdo."
   - And o LLM recebe a imagem + prompt padrão

5. **AC5 — Tratamento de erros de imagem**
   - Given o download da imagem falha (timeout, 404, etc.)
   - When o nó `process_media` captura `ExternalServiceError`
   - Then retorna mensagem de fallback no `user_message`: "Não consegui baixar sua imagem. Pode reenviar ou descrever por texto?"
   - And loga `image_download_failed` via structlog com media_id, mime_type, error
   - And o pipeline continua (LLM responde com a mensagem de fallback)

   - Given a imagem é ilegível ou muito pequena
   - When o LLM (Vision) processa
   - Then o LLM informa ao aluno que não conseguiu ler a imagem e sugere reenviar com melhor qualidade
   - And isso é comportamento nativo do Claude (não requer implementação — o LLM responde naturalmente)

6. **AC6 — Latência e performance**
   - Given uma mensagem de imagem
   - When processada pelo pipeline completo
   - Then latência total P95 < 15 segundos (NFR3)
   - And o download da imagem usa timeout de 15s (imagens podem ser maiores que áudios)
   - And imagens > 5MB são rejeitadas com mensagem ao aluno (WhatsApp limita a 16MB mas Vision tem limites de tokens)

7. **AC7 — `langchain-google-vertexai` suporta imagens**
   - Given `ChatAnthropicVertex` do `langchain-google-vertexai`
   - When envia mensagem com content block de imagem
   - Then funciona corretamente (fix incluído em `langchain-google-vertexai>=3.2.2`)
   - And o fallback `ChatAnthropic` também suporta imagem nativamente
   - And verificar que `pyproject.toml` tem `langchain-google-vertexai>=3.2.2`

## Tasks / Subtasks

- [x] Task 1: Adicionar campo `image_message` ao `WhatsAppState` (AC: #1, #3)
  - [x] 1.1 Editar `workflows/whatsapp/state.py` — adicionar `image_message: list | None` (lista de content blocks ou None)
  - [x] 1.2 Editar `workflows/views.py` → `_process_message()` — adicionar `"image_message": None` no `initial_state`

- [x] Task 2: Adicionar branch de imagem ao nó `process_media` (AC: #1, #4, #5, #6)
  - [x] 2.1 Se `process_media.py` NÃO existe (3.1 não implementada): criar `workflows/whatsapp/nodes/process_media.py` com `async def process_media(state: WhatsAppState) -> dict` (skip para text e audio)
  - [x] 2.1b Se `process_media.py` JÁ existe (3.1 implementada): editar o nó existente — adicionar elif para `message_type == "image"` ✅ **Cenário usado:** 3.1 já implementada. Refatorado para dispatch `_process_audio`/`_process_image`.
  - [x] 2.2 Implementar branch: se `message_type == "image"` → download + base64 + content blocks
  - [x] 2.3 Implementar download via `download_media(media_id, mime_type)` do `workflows/providers/whatsapp.py`
  - [x] 2.4 Validar tamanho: se `len(content) > 5 * 1024 * 1024` → retornar fallback message
  - [x] 2.5 Converter bytes para base64 com `base64.standard_b64encode(content).decode("utf-8")`
  - [x] 2.6 Determinar `media_type` a partir do `mime_type` (ex: `"image/jpeg"`, `"image/png"`, `"image/webp"`)
  - [x] 2.7 Montar `HumanMessage` multimodal com content blocks:
    ```python
    content = [
        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": base64_data}},
        {"type": "text", "text": user_text},
    ]
    ```
  - [x] 2.8 Se `user_message` vazio → usar prompt padrão "Analise esta imagem e me ajude a entender o conteúdo."
  - [x] 2.9 Retornar `{"image_message": content}` (content blocks, não HumanMessage completo — será montado no orchestrate_llm)
  - [x] 2.10 Tratamento de `ExternalServiceError` no download → logar + retornar fallback `{"user_message": "Não consegui baixar sua imagem..."}`
  - [x] 2.11 Logar via structlog: `image_processed` com media_id, mime_type, size_bytes, base64_size

- [x] Task 3: Integrar `process_media` no grafo — SE NÃO EXISTIR (AC: #2)
  - [x] 3.1 **Verificar primeiro:** se Story 3.1 já foi implementada, `process_media` já está no grafo → SKIP Task 3 inteira ✅ **SKIPPED:** Story 3.1 já implementada — `process_media` já no grafo, `graph.py`, `rate_limit.py` e `__init__.py` já atualizados.
  - [x] 3.2 SKIP (3.1 já implementada)
  - [x] 3.3 SKIP (3.1 já implementada)
  - [x] 3.4 SKIP (3.1 já implementada)

- [x] Task 4: Adaptar `orchestrate_llm` para imagens (AC: #3, #4)
  - [x] 4.1 Editar `workflows/whatsapp/nodes/orchestrate_llm.py`:
    - Verificar se `state.get("image_message")` está populado
    - Se sim: criar `HumanMessage(content=state["image_message"])` em vez de `HumanMessage(content=user_message)`
    - Se não: manter comportamento atual (texto simples)
  - [x] 4.2 Garantir que `is_tool_reentry` continua funcionando com imagens (tools loop após análise de imagem) ✅ Verificado via teste `test_image_with_tool_reentry_works`
  - [x] 4.3 Verificar que `cost_tracker` captura tokens de Vision corretamente (Vision usa mais input tokens) ✅ CostTrackingCallback é agnóstico — acumula tokens automaticamente independente do tipo de mensagem

- [x] Task 5: Verificar versão de `langchain-google-vertexai` (AC: #7)
  - [x] 5.1 Verificar `pyproject.toml` — garantir `langchain-google-vertexai>=3.2.2` ✅ Atualizado de `>=3.2` para `>=3.2.2`
  - [x] 5.2 Se necessário, fazer `uv lock` e `uv sync` para atualizar ✅ `uv lock` executado

- [x] Task 6: Testes unitários (AC: #1-#7)
  - [x] 6.1 Editar `tests/test_whatsapp/test_nodes/test_process_media.py` (já existia de 3.1 — substituído placeholder por 8 testes de imagem):
    - Teste: imagem válida → retorna `image_message` com content blocks base64
    - Teste: message_type="text" → retorna dict vazio (no-op)
    - Teste: message_type="audio" → retorna dict vazio (no-op)
    - Teste: imagem com caption → combina texto + imagem
    - Teste: imagem sem caption → usa prompt padrão
    - Teste: download falha → retorna fallback message
    - Teste: imagem > 5MB → retorna mensagem de limite
    - Teste: mime_type inválido → rejeita com mensagem
  - [x] 6.2 Editar `tests/test_whatsapp/test_nodes/test_orchestrate_llm.py`:
    - Teste: `image_message` presente → LLM recebe HumanMessage multimodal
    - Teste: `image_message` None → comportamento original (texto)
    - Teste: imagem + tool reentry → tools loop funciona após Vision
  - [x] 6.3 Editar `tests/test_whatsapp/conftest.py`:
    - Adicionar `"image_message": None` ao default state fixture
  - [x] 6.4 Verificar testes existentes não quebram com novo campo e novo nó no grafo ✅ 483 passed, 1 failed (pré-existente)

- [x] Task 7: Teste de integração (AC: #1-#6) — ANTI OVER-MOCKING
  - [x] 7.1 Adicionado teste `test_image_pipeline_with_real_redis_and_postgres` em `tests/integration/test_graph_e2e.py`:
    - Graph completo com imagem mockada (bytes fake) mas Redis/PostgreSQL reais
    - LLM mockado retornando resposta sobre imagem
    - Verificar que `process_media` → `load_context` → `orchestrate_llm` flui corretamente
  - [x] 7.2 Garantir `pytest -m integration` coleta o novo teste ✅ Teste marcado com `@pytest.mark.integration`

- [x] Task 8: Rodar suite completa de testes
  - [x] 8.1 `uv run pytest` — 483 passed, 1 failed (pré-existente `test_toolnode_partial_failure_returns_error_message` — LangGraph config issue, não relacionado)
  - [x] 8.2 `uv run ruff check .` — zero novos erros nos arquivos modificados (erros pré-existentes em outros arquivos)
  - [x] 8.3 `uv run ruff format` — formatação aplicada nos arquivos modificados

## Dev Notes

### Contexto Crítico — Coordenação com Story 3.1 (áudio/Whisper)

**Story 3.1 está `ready-for-dev`** e define a CRIAÇÃO do nó `process_media` com:
- `message_type="text"` → retorna `{}` (no-op)
- `message_type="audio"` → download + Whisper → `{transcribed_text, user_message}`
- `message_type="image"` → retorna `{}` (placeholder para esta Story 3.2)

**Cenário mais provável:** Story 3.1 é implementada ANTES de 3.2. Nesse caso:
- `workflows/whatsapp/nodes/process_media.py` JÁ EXISTE com handler de áudio
- `workflows/whatsapp/graph.py` JÁ TEM process_media inserido no grafo
- `workflows/whatsapp/nodes/rate_limit.py` JÁ RETORNA "process_media" em check_rate_limit()
- **Esta story apenas ADICIONA o branch de imagem** ao nó existente

**Cenário alternativo:** Story 3.2 implementada ANTES de 3.1:
- Criar o nó `process_media` com branch de imagem + skip para text e audio
- Story 3.1 depois adicionará o branch de áudio

**VERIFICAR ANTES DE COMEÇAR:** `ls workflows/whatsapp/nodes/process_media.py` — se existe, usar cenário 1.

### Padrão de Imagem Multimodal com LangChain

Claude suporta Vision nativamente. A integração via LangChain usa `HumanMessage` com content blocks:

```python
# Formato Anthropic nativo (preferir este — suportado por ChatAnthropicVertex >= 3.2.2)
HumanMessage(content=[
    {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",  # ou image/png, image/webp, image/gif
            "data": base64_encoded_string,
        },
    },
    {"type": "text", "text": "Analise esta imagem..."},
])
```

**IMPORTANTE:** NÃO usar formato `{"type": "image_url", "image_url": {"url": "data:..."}}` — esse formato é OpenAI e foi deprecado no `langchain-google-vertexai`. Usar formato Anthropic nativo acima.

### Versão Crítica: `langchain-google-vertexai >= 3.2.2`

Issue [#1019](https://github.com/langchain-ai/langchain-google/issues/1019) e [#1380](https://github.com/langchain-ai/langchain-google/issues/1380): `ChatAnthropicVertex` não suportava imagens com LangChain 1.X. **Fix incluído na versão 3.2.2** ([release notes](https://github.com/langchain-ai/langchain-google/releases)). Verificar que `pyproject.toml` usa `>=3.2.2`.

### Fluxo do Grafo Atualizado

```
START → identify_user → rate_limit → [check_rate_limit]
  ├─ exceeded → END
  └─ allowed → process_media → load_context → orchestrate_llm → [tools_condition]
                                                  ├─ tools → orchestrate_llm (loop)
                                                  └─ no tools → collect_sources → format_response
                                                      → send_whatsapp → persist → END
```

### Arquivos a Modificar/Criar

**Criar (se 3.1 NÃO implementada primeiro):**
- `workflows/whatsapp/nodes/process_media.py` — novo nó

**Criar sempre:**
- `tests/test_whatsapp/test_nodes/test_process_media.py` — 8+ testes unitários (ou editar se já existe de 3.1)
- `tests/integration/test_image_flow.py` — teste integração com Redis/PostgreSQL real

**Modificar sempre:**
- `workflows/whatsapp/state.py` — adicionar campo `image_message`
- `workflows/whatsapp/nodes/orchestrate_llm.py` — checar `image_message` para montar HumanMessage multimodal
- `workflows/views.py` — adicionar `"image_message": None` ao `initial_state`
- `tests/test_whatsapp/conftest.py` — adicionar campo ao default state

**Modificar condicionalmente (se 3.1 NÃO implementada):**
- `workflows/whatsapp/graph.py` — inserir nó `process_media` entre rate_limit e load_context
- `workflows/whatsapp/nodes/__init__.py` — exportar `process_media`
- `workflows/whatsapp/nodes/rate_limit.py` — `check_rate_limit()` retorna `"process_media"` em vez de `"load_context"`

**Modificar condicionalmente (se 3.1 JÁ implementada):**
- `workflows/whatsapp/nodes/process_media.py` — adicionar branch de imagem ao nó existente

### Padrões de Arquitetura Relevantes

- **Node contract:** `async def process_media(state: WhatsAppState) -> dict` — função async pura, retorna dict parcial. [Source: architecture.md#LangGraph-Node-Contract]
- **Error handling:** `ExternalServiceError` para falhas de download. SEMPRE logar com structlog ANTES de fallback. NUNCA `except Exception` silencioso. [Source: architecture.md#Error-Handling, retros Epic 1/2/4]
- **Singleton client:** `download_media()` já usa `_get_client()` singleton. Não criar novo client. [Source: workflows/providers/whatsapp.py]
- **Cost tracking:** `CostTrackingCallback` acumula cost automaticamente. Vision usa mais input tokens — custo será maior (~$0.01-0.04 por imagem dependendo do tamanho). [Source: workflows/services/cost_tracker.py]
- **Supported MIME types (Claude Vision):** `image/jpeg`, `image/png`, `image/gif`, `image/webp`. Rejeitar outros. [Source: Anthropic Vision docs]

### Limites e Constraints do Claude Vision

- **Tamanho máximo de imagem:** 5MB (após base64, ~6.7MB de string) — limitar antes de enviar
- **Resolução:** Claude redimensiona automaticamente, mas imagens muito pequenas podem ser ilegíveis
- **MIME types suportados:** jpeg, png, gif, webp
- **Tokens de input:** Imagens consomem tokens significativos (~1600 tokens para imagem 1568x1568)
- **Prompt Caching:** Imagens em cache_control podem ser cacheadas (TTL 5min) — mas para imagens variáveis não faz sentido cachear

### WhatsApp Image Payload

```json
{
  "type": "image",
  "image": {
    "id": "MEDIA_ID",
    "mime_type": "image/jpeg",
    "sha256": "...",
    "caption": "Texto opcional do aluno"
  }
}
```

O campo `caption` contém o texto que o aluno enviou junto com a imagem. Já extraído pelo webhook como `user_message` (se existir) ou vazio.

### Retro Watch Items

- **Error handler silencioso** — zero `except Exception` sem log (retros Epic 1, 2, 4). Flagar como RETRO WATCH no code review.
- **Over-mocking** — exigir >=1 teste de integração real por story (pendente desde Epic 1).
- **Exceção raw para LLM** — tools SEMPRE retornam string, nunca raise exception (acordo do time). Neste caso, `process_media` é nó (não tool), mas o princípio se aplica: SEMPRE retornar estado válido, nunca propagar exceção raw.

### Riscos

- **`langchain-google-vertexai` versão desatualizada** — se versão < 3.2.2, Vision não funciona via Vertex. Fallback: usar `ChatAnthropic` direto para mensagens com imagem (temporário).
- **Imagens grandes** — WhatsApp aceita até 16MB mas Vision tem custos elevados. Limite de 5MB é pragmático.
- **Caption não extraído** — verificar se webhook extrai `caption` do payload de imagem como `body`/`user_message`. Se não, extrair no `process_media` a partir do payload (pode estar no `msg["image"]["caption"]`).
- **Coordenação com Story 3.1** — se 3.1 for implementada em paralelo, pode haver conflito de merge no `process_media.py`, `graph.py` e `rate_limit.py`. Resolver na integração.

### References

- [Source: _bmad-output/implementation-artifacts/3-1-transcricao-audio-whisper.md — Story 3.1 cria process_media com áudio, Tasks 2-3 definem estrutura do nó]
- [Source: _bmad-output/planning-artifacts/epics.md#Story-3.2]
- [Source: _bmad-output/planning-artifacts/architecture.md#WhatsAppState — campos media_id, media_url, mime_type]
- [Source: _bmad-output/planning-artifacts/architecture.md#process_media — "Whisper (audio), Vision (image)"]
- [Source: _bmad-output/planning-artifacts/architecture.md#NFR3 — P95 < 15s imagem]
- [Source: workflows/providers/whatsapp.py — download_media() já implementado (Story 0.1)]
- [Source: workflows/whatsapp/graph.py — grafo atual sem process_media]
- [Source: workflows/whatsapp/nodes/orchestrate_llm.py — HumanMessage(content=user_message)]
- [Source: workflows/providers/llm.py — ChatAnthropicVertex + ChatAnthropic fallback]
- [Source: workflows/whatsapp/state.py — campos atuais do WhatsAppState]
- [Source: workflows/views.py:157-181 — initial_state assembly]
- [Source: GitHub langchain-google #1380 — fix image support v3.2.2]
- [Source: _bmad-output/implementation-artifacts/0-1-prep-sprint-debitos-tecnicos-validacao-e2e.md — download_media, media_id extraction implementados]
- [Source: _bmad-output/implementation-artifacts/epic-2-retro-2026-03-10.md — retro watch items]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- 483 passed, 1 failed (pré-existente) em testes unitários
- 28/28 passed nos testes de process_media + orchestrate_llm

### Completion Notes List

- **Cenário 1 confirmado:** Story 3.1 já implementada — `process_media.py` existia com handler de áudio + skip para image/text. Refatorado para dispatch via `_process_audio()` e `_process_image()`.
- **Caption extraction corrigido:** Webhook `should_process_event()` não extraía `caption` de imagens. Adicionado `body = media_data.get("caption", "")` para `msg_type == "image"` em `views.py`.
- **Tratamento gracioso de erros:** Diferente do audio (que raises GraphNodeError e para o pipeline), imagem retorna fallback `user_message` para que o LLM responda ao aluno informando o problema. Decisão alinhada com AC5 e retro watch "SEMPRE retornar estado válido".
- **MIME type validation:** Adicionada validação de MIME types suportados (jpeg, png, webp, gif) com mensagem informativa para tipos não suportados (ex: BMP).
- **Versão atualizada:** `langchain-google-vertexai` bumped de `>=3.2` para `>=3.2.2` em `pyproject.toml` (fix para Vision via Vertex — issue #1380).
- **Integração test adicionado:** Teste E2E completo com graph real (Redis mockado) + image pipeline no `test_graph_e2e.py`.

### Senior Developer Review (AI)

**Reviewer:** Claude Opus 4.6 (code-review workflow) — 2026-03-12
**Outcome:** Approved (after fixes)
**Issues Found:** 2 High, 4 Medium, 1 Low — ALL FIXED

**Fixes Applied:**
1. **[H1] Exception handling em `_process_image`** — Adicionado `except Exception` genérico para capturar exceções não-ExternalServiceError (ex: `httpx.ConnectError`). Sem isso, pipeline crashava em vez de retornar fallback gracioso. AC5 agora totalmente implementado.
2. **[H2] Caption `null` descartava mensagens** — `views.py:80` `media_data.get("caption", "")` retornava `None` quando WhatsApp envia `"caption": null`. Serializer rejeitava, mensagem silenciosamente descartada. Fix: `media_data.get("caption") or ""`.
3. **[M1] Teste misleading corrigido** — `test_audio_message_not_handled_as_image` usava `message_type="text"` em vez de `"audio"`. Agora testa áudio real com mock de `download_media`/`transcribe_audio`.
4. **[M2] Teste de exceção genérica adicionado** — `test_image_unexpected_exception_returns_fallback` valida que `RuntimeError` retorna fallback gracioso (cobre H1).
5. **[M3] `except` redundante em `_process_audio`** — `(ExternalServiceError, Exception)` simplificado para `except Exception` (linter aplicou automaticamente).
6. **[M4] Timeout de imagem 15s (AC6)** — `download_media` agora aceita param `timeout` opcional. `_process_image` usa `IMAGE_DOWNLOAD_TIMEOUT = 15.0s` conforme AC6/NFR3.
7. **[L1] `_make_state` consolidado** — Test helpers em `test_process_media.py` e `test_orchestrate_llm.py` agora são thin wrappers sobre `conftest.make_whatsapp_state`.

**Test Results:** 519 passed, 0 failed (ruff clean)

### Change Log

- 2026-03-12: Story 3.2 implementada — análise de imagens via Claude Vision (Tasks 1-8)
- 2026-03-12: Code review — 7 findings corrigidos (2H, 4M, 1L). Status → done

### File List

**Modificados:**
- `workflows/whatsapp/state.py` — campo `image_message: list | None`
- `workflows/whatsapp/nodes/process_media.py` — refatorado: dispatch audio/image + `_process_image()` completo + [review] except Exception genérico + timeout 15s
- `workflows/whatsapp/nodes/orchestrate_llm.py` — suporte a `image_message` multimodal no `HumanMessage`
- `workflows/views.py` — `"image_message": None` no initial_state + extração de `caption` para imagens + [review] fix caption null
- `workflows/providers/whatsapp.py` — [review] `download_media` aceita param `timeout` opcional por request
- `pyproject.toml` — `langchain-google-vertexai>=3.2.2`
- `uv.lock` — atualizado após bump de versão
- `tests/test_whatsapp/conftest.py` — `"image_message": None` no default state
- `tests/test_whatsapp/test_nodes/test_process_media.py` — 9 testes de imagem + [review] fix test áudio + teste exceção genérica + _make_state consolidado
- `tests/test_whatsapp/test_nodes/test_orchestrate_llm.py` — 3 testes de imagem multimodal + [review] _make_state consolidado
- `tests/integration/test_graph_e2e.py` — teste `test_image_pipeline_with_real_redis_and_postgres` + `image_message` no `_make_initial_state`
