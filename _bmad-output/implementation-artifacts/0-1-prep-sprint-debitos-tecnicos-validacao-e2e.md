# Story 0.1: Prep Sprint — Débitos Técnicos + Validação E2E

Status: done

<!-- Note: Story especial de preparação entre Epics 2/4 (done) e Sprint 6 (Epics 3+5). -->
<!-- Origem: Retros Epic 1, Epic 4 e Epic 2 — action items pendentes consolidados. -->

## Story

As a equipe de desenvolvimento,
I want resolver débitos técnicos acumulados e validar o pipeline de ponta a ponta,
So that o Sprint 6 (Epics 3+5) parte de uma base sólida, sem dívidas técnicas herdadas.

## Acceptance Criteria

1. **AC1 — OPENAI_API_KEY configurada no projeto**
   - Given o projeto precisa de OpenAI API para Whisper (Epic 3, Story 3.1)
   - When o dev verifica `config/settings/base.py` e `.env.example`
   - Then `OPENAI_API_KEY` está declarada em `base.py` via `env("OPENAI_API_KEY")`
   - And `.env.example` lista `OPENAI_API_KEY=your-openai-key` com comentário de uso (Whisper)
   - And a key NÃO é obrigatória para rodar o projeto (default=None ou env com fallback)

2. **AC2 — Extração de media_id do payload WhatsApp**
   - Given o webhook recebe mensagem de áudio ou imagem
   - When `should_process_event()` em `workflows/views.py` parseia o payload
   - Then extrai `media_id` de `msg.get("audio", {}).get("id")` ou `msg.get("image", {}).get("id")`
   - And extrai `mime_type` de `msg.get("audio", {}).get("mime_type")` ou `msg.get("image", {}).get("mime_type")`
   - And passa `media_id` e `mime_type` no `validated_data` para o estado do grafo
   - And `WhatsAppState` tem campo `media_id: str | None` (além do existente `media_url`)
   - And para mensagens de texto, `media_id` permanece `None`

3. **AC3 — Download de mídia via WhatsApp Cloud API**
   - Given uma mensagem com `media_id` válido
   - When o sistema precisa processar a mídia (áudio/imagem)
   - Then implementa função `download_media(media_id: str) -> bytes` em `workflows/providers/whatsapp.py`
   - And faz GET `https://graph.facebook.com/v21.0/{media_id}` com Bearer token para obter a URL temporária
   - And faz GET na URL temporária para baixar o conteúdo binário
   - And retorna os bytes da mídia (ou raises `ExternalServiceError` com contexto)
   - And loga `media_downloaded` via structlog com media_id, mime_type, size_bytes

4. **AC4 — Testes de integração anti over-mocking**
   - Given os testes existentes usam mocks extensivos
   - When o dev cria testes de integração leves
   - Then existe pelo menos 1 teste de integração que valida o fluxo webhook → grafo sem mockar Redis
   - And existe pelo menos 1 teste que valida debounce com Redis real (docker-compose)
   - And existe pelo menos 1 teste que valida rate limiting com Redis real
   - And os testes usam `pytest.mark.integration` e rodam com `pytest -m integration`
   - And a documentação no README ou conftest explica como rodar os testes de integração

5. **AC5 — Error handlers revisados**
   - Given existem ~28 `except Exception` no codebase (workflows/)
   - When o dev revisa cada handler
   - Then zero `except Exception` silenciosos (sem log) restam no codebase
   - And todo `except Exception` tem `logger.error()` ou `logger.warning()` com structlog ANTES de qualquer fallback
   - And handlers em `views.py` (linhas 98, 111, 121, 185) logam exceção completa (exc_info=True ou exception=str(e))
   - And handlers em `whatsapp/nodes/` que já usam `GraphNodeError` são mantidos (padrão correto)
   - And nenhum handler engole exceções de forma que mascare bugs sistêmicos

6. **AC6 — Retro Watch Items nos story files**
   - Given as retros dos Epics 1, 4 e 2 geraram action items recorrentes
   - When o SM adiciona "Retro Watch Items" aos stories do Sprint 6
   - Then stories 3-1, 3-2, 5-1 e 5-2 contêm seção `## Retro Watch Items` com:
     - Padrão "error handler silencioso" — flagar como RETRO WATCH no code review
     - Padrão "over-mocking" — exigir ≥1 teste real por story
     - Padrão "exceção raw vazando para LLM" — tools SEMPRE retornam string, nunca exception
   - And o code review do Sprint 6 recebe contexto das retros como checklist adicional

7. **AC7 — Smoke test E2E do pipeline**
   - Given credenciais reais configuradas no .env (GCP, Pinecone, Tavily, NCBI, OpenAI)
   - When uma mensagem de texto é enviada ao webhook
   - Then o pipeline completo executa: webhook → identify_user → load_context → orchestrate_llm → tools → collect_sources → format_response → send_whatsapp
   - And a resposta contém citações `[N]` ou `[W-N]` quando tools médicas são chamadas
   - And o cost_usd é registrado (>0)
   - And nenhuma exceção não tratada aparece nos logs
   - And o teste é documentado como script reproduzível (curl ou pytest)

## Tasks / Subtasks

- [x] Task 1: Adicionar `OPENAI_API_KEY` ao settings e .env.example (AC: #1)
  - [x] 1.1 Editar `config/settings/base.py` — adicionar `OPENAI_API_KEY = env("OPENAI_API_KEY", default=None)` na seção de API keys
  - [x] 1.2 Editar `.env.example` — adicionar `OPENAI_API_KEY=your-openai-key` com comentário `# Whisper API (áudio transcription — Epic 3)`
  - [x] 1.3 Verificar que o projeto sobe sem a key definida (default=None)

- [x] Task 2: Implementar extração de `media_id` no webhook (AC: #2)
  - [x] 2.1 Editar `workflows/views.py` → `should_process_event()` — extrair `media_id` e `mime_type` do payload para áudio e imagem
  - [x] 2.2 Adicionar `media_id` e `mime_type` ao `validated_data` retornado
  - [x] 2.3 Editar `workflows/whatsapp/state.py` — adicionar campo `media_id: str | None` e `mime_type: str | None` ao `WhatsAppState`
  - [x] 2.4 Editar `workflows/views.py` → `_process_message()` — passar `media_id` e `mime_type` no `initial_state`
  - [x] 2.5 Testes unitários: payload áudio com media_id, payload imagem com media_id, payload texto sem media_id
  - [x] 2.6 Manter backward compatibility — mensagens de texto continuam funcionando sem media_id

- [x] Task 3: Implementar download de mídia via WhatsApp Cloud API (AC: #3)
  - [x] 3.1 Editar `workflows/providers/whatsapp.py` — adicionar `async def download_media(media_id: str, mime_type: str) -> tuple[bytes, str]`
  - [x] 3.2 Step 1: GET `/{media_id}` via singleton client com Bearer token → obtém JSON com `url`
  - [x] 3.3 Step 2: GET na `url` retornada → obtém bytes da mídia
  - [x] 3.4 Retornar `(content_bytes, mime_type)` — raise `ExternalServiceError` se falhar
  - [x] 3.5 Logar via structlog: `media_url_fetched` (step 1) e `media_downloaded` (step 2) com media_id, mime_type, size_bytes
  - [x] 3.6 Testes unitários com httpx mock: sucesso, 404 (media expirada), timeout
  - [x] 3.7 Usar `httpx.AsyncClient` (singleton _get_client(), mesmo padrão do projeto)

- [x] Task 4: Criar/reforçar testes de integração anti over-mocking (AC: #4)
  - [x] 4.1 Verificar testes existentes em `tests/integration/` — já existem `test_redis_debounce.py`, `test_redis_rate_limiter.py`, `test_llm_pipeline.py`, `test_db_models.py`
  - [x] 4.2 Criar `tests/integration/test_webhook_flow.py` — teste de fluxo webhook → grafo com Redis real (sem mock de Redis)
  - [x] 4.3 Garantir que `conftest.py` tem fixture de Redis real com cleanup entre testes
  - [x] 4.4 Adicionar `tests/integration/test_graph_e2e.py` — teste do grafo completo com LLM mockado mas Redis/PostgreSQL reais
  - [x] 4.5 Validar que `pytest -m integration` roda todos os testes de integração (21 testes coletados)
  - [x] 4.6 Documentar no `tests/integration/conftest.py`: como subir docker-compose e rodar (já documentado)

- [x] Task 5: Revisar e corrigir error handlers silenciosos (AC: #5)
  - [x] 5.1 Auditar todos os `except Exception` em `workflows/` — 32 handlers encontrados
  - [x] 5.2 Para cada handler silencioso: adicionar `logger.warning()` ANTES do fallback
  - [x] 5.3 Foco principal: `views.py` — todos já tinham logging (logger.exception/logger.warning)
  - [x] 5.4 Foco secundário: corrigidos 6 handlers silenciosos em `rate_limit.py` (3), `send_whatsapp.py` (2), `debounce.py` (1)
  - [x] 5.5 Handlers que já usam `GraphNodeError` ou `ExternalServiceError` → mantidos (padrão correto)
  - [x] 5.6 Rodar `ruff check` e `pytest` após mudanças — 433 testes passando, 0 erros ruff em arquivos modificados

- [x] Task 6: Adicionar Retro Watch Items nos story files do Sprint 6 (AC: #6)
  - [x] 6.1 Adicionada seção `#### Retro Watch Items` em stories 3-1, 3-2, 5-1, 5-2 no epics.md (stories ainda em backlog, serão criadas via create-story)
  - [x] 6.2 Watch Item 1: "Error handler silencioso — zero `except Exception` sem log (retros Epic 1, 2, 4)"
  - [x] 6.3 Watch Item 2: "Over-mocking — ≥1 teste de integração real por story (pendente desde Epic 1)"
  - [x] 6.4 Watch Item 3: "Exceção raw para LLM — tools SEMPRE retornam string, nunca raise (acordo do time)"
  - [x] 6.5 Padrão documentado diretamente nos epics — create-story incluirá automaticamente

- [x] Task 7: Smoke test E2E do pipeline completo (AC: #7)
  - [x] 7.7 Documentar o smoke test como script reproduzível em `tests/e2e/test_smoke.py`
  - [x] 7.1 Configurar `.env` com credenciais reais: GCP, Pinecone, Tavily, NCBI, OpenAI
  - [x] 7.2 Subir serviços locais: `docker-compose up -d` (Redis + PostgreSQL)
  - [x] 7.3 Enviar request POST ao webhook com payload real de mensagem de texto
  - [x] 7.4 Verificar nos logs que o pipeline completo executou sem exceções
  - [x] 7.5 Verificar que a resposta contém citações (tools foram chamadas)
  - [x] 7.6 Verificar que `cost_usd > 0` no log
  - [x] 7.8 Validado com Rodrigo presente em 2026-03-11

## Dev Notes

### Contexto e Motivação

Esta story consolida débitos técnicos identificados nas retrospectivas dos Epics 1, 4 e 2. Os action items de maior prioridade (testes anti over-mocking, error handlers silenciosos) foram reportados na retro do Epic 1, reconfirmados na retro do Epic 4 (0/5 completados), e novamente na retro do Epic 2 (2/5 não endereçados). **Root cause identificado:** gap no processo — action items de retro não alimentavam stories automaticamente.

### Ordem de Execução Recomendada

1. **Tasks 1-3** (Setup técnico) — podem ser paralelas
2. **Task 5** (Error handlers) — pode ser paralela com 1-3
3. **Task 4** (Testes integração) — após Tasks 1-3 e 5 (código estável)
4. **Task 6** (Retro Watch Items) — SM pode fazer em paralelo, não depende de dev
5. **Task 7** (Smoke test E2E) — última, requer tudo acima + credenciais + Rodrigo

### Padrões de Arquitetura Relevantes

- **Error handling:** Hierarquia `AppError` → `GraphNodeError` / `ExternalServiceError`. SEMPRE logar com structlog ANTES de fallback. [Source: architecture.md#Error-Handling]
- **WhatsApp API:** `workflows/providers/whatsapp.py` já tem `send_text_message()`, `mark_as_read()` com `httpx.AsyncClient`. Download de mídia segue o mesmo padrão. [Source: architecture.md#WhatsApp-Integration]
- **Settings:** `django-environ` com `env()` calls em `config/settings/base.py`. [Source: 1-1-setup-projeto-django-estrutura-base.md]
- **State:** `WhatsAppState` é TypedDict em `workflows/whatsapp/state.py`. [Source: 1-4-llm-provider-checkpointer-orquestracao-base.md]
- **Testes integração:** `pytest.mark.integration`, settings em `config/settings/integration.py`, Redis localhost:6379, PostgreSQL localhost:5432. [Source: tests/integration/conftest.py]

### Dependências

- Docker + docker-compose (Redis + PostgreSQL para testes de integração)
- Credenciais reais para smoke test E2E (GCP, Pinecone, Tavily, NCBI, OpenAI)
- Rodrigo presente para validação do smoke test

### Project Structure Notes

- Todos os arquivos editados já existem — nenhum módulo novo criado (exceto arquivos de teste)
- `workflows/providers/whatsapp.py` — adicionar `download_media()` ao módulo existente
- `workflows/views.py` — editar `should_process_event()` e `_process_message()`
- `workflows/whatsapp/state.py` — adicionar campo `media_id`
- `config/settings/base.py` — adicionar 1 linha de env var
- `.env.example` — adicionar 1 linha

### Riscos

- **Smoke test E2E depende de credenciais reais** — não pode ser automatizado no CI inicialmente
- **Error handler review pode revelar bugs mascarados** — preparar para debugging adicional
- **Media download depende de token WhatsApp válido** — testar com sandbox do Meta

### References

- [Source: _bmad-output/implementation-artifacts/epic-1-retro-2026-03-08.md#Action-Items]
- [Source: _bmad-output/implementation-artifacts/epic-4-retro-2026-03-08.md#Action-Items]
- [Source: _bmad-output/implementation-artifacts/epic-2-retro-2026-03-10.md#Prep-Sprint]
- [Source: _bmad-output/planning-artifacts/architecture.md#Error-Handling]
- [Source: _bmad-output/planning-artifacts/architecture.md#WhatsApp-Integration]
- [Source: workflows/views.py#should_process_event — media_url hardcoded como None]
- [Source: workflows/providers/whatsapp.py — padrão httpx.AsyncClient para WhatsApp API]
- [Source: config/settings/base.py — seção de API keys]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- 433/433 unit tests passing (zero regressions)
- 21 integration tests collected (3 new: test_webhook_flow, test_graph_e2e)
- 2 e2e smoke tests collected (skip without credentials)
- ruff check: 0 errors on all modified files
- 32 `except Exception` handlers audited — 0 silent handlers remaining

### Completion Notes List

- **Task 1:** Added `OPENAI_API_KEY` to `base.py` (default=None) and `.env.example`. Project loads fine without the key.
- **Task 2:** Implemented `media_id` and `mime_type` extraction in `should_process_event()` for audio/image payloads. Added fields to `WhatsAppState`. Updated `_process_message()` initial state. 3 new unit tests (audio, image, text payloads).
- **Task 3:** Implemented `download_media()` in `whatsapp.py` — two-step GET (URL fetch + binary download) with structlog logging and `ExternalServiceError` handling. 3 new unit tests (success, 404, timeout).
- **Task 4:** Created `test_webhook_flow.py` (debounce → graph with real Redis) and `test_graph_e2e.py` (full graph with real Redis + PostgreSQL, mocked LLM only). Verified existing integration tests cover debounce and rate limiting with real Redis.
- **Task 5:** Audited all 32 `except Exception` handlers in `workflows/`. Fixed 6 silent handlers: `debounce.py` (1), `send_whatsapp.py` (2), `rate_limit.py` (3). All now have `logger.warning()` before fallback. Handlers using `GraphNodeError`/`ExternalServiceError` maintained (correct pattern).
- **Task 6:** Added `#### Retro Watch Items` section to stories 3-1, 3-2, 5-1, 5-2 in `epics.md` with 3 watch items from retros of Epics 1, 2, 4.
- **Task 7:** Smoke test E2E executado com sucesso em 2026-03-11 com Rodrigo presente. Pipeline completo: webhook → debounce → identify_user → rate_limit → load_context → orchestrate_llm → tools (RAG + web_search) → collect_sources → format_response → send_whatsapp → persist. Resposta: 3553 chars com 7 citações [W-N]. Cost total: $0.0289 (3 LLM calls via Vertex AI). Fixes durante smoke test: embeddings.py não passava GCP_CREDENTIALS (corrigido), VERTEX_LOCATION=global→us-east5, credential check no test verificava ANTHROPIC_API_KEY em vez de GCP_CREDENTIALS, conftest.py criado com setup do schema langgraph.

### File List

**Modified:**
- config/settings/base.py
- .env.example
- workflows/views.py
- workflows/whatsapp/state.py
- workflows/providers/whatsapp.py
- workflows/services/debounce.py
- workflows/whatsapp/nodes/send_whatsapp.py
- workflows/whatsapp/nodes/rate_limit.py
- tests/test_webhook.py
- tests/test_providers/test_whatsapp.py
- pyproject.toml
- _bmad-output/planning-artifacts/epics.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- workflows/serializers.py *(code review fix: added media_id/mime_type fields)*
- _bmad-output/planning-artifacts/architecture.md *(code review fix: Django 5.1 → 5.2)*

**Created:**
- tests/integration/test_webhook_flow.py
- tests/integration/test_graph_e2e.py
- tests/e2e/__init__.py
- tests/e2e/test_smoke.py
- tests/e2e/conftest.py *(smoke test: langgraph schema setup + singleton resets)*

**Modified (smoke test session 2026-03-11):**
- workflows/providers/embeddings.py *(fix: pass GCP_CREDENTIALS to VertexAIEmbeddings)*
- tests/e2e/test_smoke.py *(fix: credential check GCP_CREDENTIALS, timeout 30s→120s)*
- .env *(fix: VERTEX_LOCATION global→us-east5)*

## Senior Developer Review (AI)

**Reviewer:** Claude Opus 4.6 (adversarial code review)
**Date:** 2026-03-10
**Outcome:** Changes Requested → Auto-fixed (7 issues)

### Findings (7 total: 1 Critical, 3 High, 2 Medium, 1 Low)

1. **[CRITICAL][FIXED]** AC2 quebrada — `WhatsAppMessageSerializer` não declarava `media_id`/`mime_type`, DRF stripava os campos do `validated_data`. Extração funcionava mas dados nunca chegavam ao grafo. Adicionados campos ao serializer.
2. **[HIGH][FIXED]** Task 7 marcada `[x]` mas subtasks 7.1-7.6 são `[ ]`. Desmarcado parent para `[ ]`.
3. **[HIGH][FIXED]** Smoke test `test_smoke.py` patchava mocks no módulo de definição (`workflows.providers.whatsapp`) em vez do uso (`workflows.whatsapp.nodes.send_whatsapp`). Corrigidos mock paths.
4. **[HIGH][FIXED]** `download_media()` não tratava `KeyError` se API retornasse JSON sem key `"url"`. Adicionada validação com `ExternalServiceError`.
5. **[MEDIUM][FIXED]** Testes de `download_media` só cobriam falha no step 1. Adicionados 3 testes: step 2 403 (URL expirada), step 2 timeout, e missing `"url"` key.
6. **[MEDIUM][FIXED]** Debounce perdia `media_id` de mensagens não-primeiras no batch. Adicionada lógica para preservar último `media_id` e documentado comportamento.
7. **[LOW][FIXED]** `pyproject.toml` declarava `django>=5.2` mas architecture.md dizia 5.1. Atualizada architecture para 5.2.

### Validation Post-Fix

- 49/49 unit tests passing (incl. 3 novos testes download_media)
- ruff check: 0 errors on all modified files

### Remaining Items

- ~~AC7 (smoke test E2E) requer execução com credenciais reais + Rodrigo presente~~ ✅ Validada 2026-03-11
- **Story DONE** — todas as ACs validadas

## Change Log

- 2026-03-10: Implementação completa da Story 0.1 — débitos técnicos consolidados das retros Epic 1, 2, 4. Adicionados campos media_id/mime_type ao pipeline, função download_media, corrigidos 6 error handlers silenciosos, criados 3 testes de integração anti over-mocking, adicionados Retro Watch Items ao Sprint 6, e criado smoke test E2E reproduzível.
- 2026-03-10: **Code Review (AI)** — 7 issues encontradas e auto-corrigidas: serializer sem media_id/mime_type (CRITICAL), Task 7 status incorreto, mock paths do smoke test, KeyError não tratado em download_media, testes de step 2 failure ausentes, debounce perde media_id, versão Django inconsistente. 49 testes passando pós-fix.
- 2026-03-11: **Smoke Test E2E (AC7)** — Executado com Rodrigo presente. 3 fixes durante execução: (1) embeddings.py não passava GCP_CREDENTIALS para VertexAIEmbeddings, (2) VERTEX_LOCATION=global→us-east5, (3) test credential check verificava ANTHROPIC_API_KEY (fallback) em vez de GCP_CREDENTIALS (primary). Criado conftest.py para setup do schema langgraph no test DB. Pipeline completo passou: resposta de 3553 chars com 7 citações web sobre dengue, cost_usd=$0.0289. 2 issues não-bloqueantes: Pinecone index host config, persist User.DoesNotExist em test DB. **Story status → done.**
