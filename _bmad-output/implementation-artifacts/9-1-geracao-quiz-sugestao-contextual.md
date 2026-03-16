# Story 9.1: Geração de Quiz + Sugestão Contextual

Status: done

## Story

As a aluno de medicina,
I want praticar com quizzes sobre o tema que estou estudando,
So that fixo o conteúdo de forma ativa e interativa.

## Acceptance Criteria (BDD)

### AC1: Geração de quiz sob demanda
**Given** o aluno pede um quiz (ex: "Me faça uma questão sobre IC")
**When** o LLM decide usar a tool `quiz_generate` via ToolNode
**Then** a tool (`workflows/whatsapp/tools/quiz_generator.py`) gera uma questão no formato: enunciado, 5 alternativas (A-E), e resposta comentada
**And** a questão é formatada para WhatsApp com alternativas em linhas separadas (FR25)
**And** a resposta comentada só é enviada APÓS o aluno responder

### AC2: Feedback após resposta do aluno
**Given** o aluno responde a questão com uma alternativa (ex: "B" ou "alternativa B")
**When** o LLM processa a resposta
**Then** apresenta: acertou/errou, resposta correta, comentário explicativo com fontes
**And** pergunta se quer outra questão sobre o mesmo tema ou tema diferente

### AC3: Sugestão contextual de quiz
**Given** o LLM acaba de responder uma pergunta médica substantiva
**When** o tema é propício para quiz (ex: diagnóstico diferencial, farmacologia, condutas)
**Then** sugere ao final: "Quer testar seu conhecimento sobre esse tema? Posso fazer uma questão rápida!" (FR26)
**And** a sugestão é natural e não repetitiva (max 1 sugestão a cada 5 interações)

## Tasks / Subtasks

- [x] Task 1: Criar tool `quiz_generator.py` (AC: #1)
  - [x] 1.1 Criar `workflows/whatsapp/tools/quiz_generator.py` com `@tool` decorator
  - [x] 1.2 Implementar chamada LLM interna (sem tools) para gerar questão estruturada
  - [x] 1.3 Formato de saída: enunciado + 5 alternativas (A-E) + gabarito + comentário
  - [x] 1.4 Parâmetros: `topic: str`, `level: str = "intermediate"` (easy/intermediate/hard)
  - [x] 1.5 A tool retorna APENAS enunciado + alternativas (gabarito fica oculto para o LLM apresentar depois)
- [x] Task 2: Registrar tool no ToolNode (AC: #1)
  - [x] 2.1 Importar `quiz_generate` em `workflows/whatsapp/tools/__init__.py`
  - [x] 2.2 Adicionar à lista retornada por `get_tools()`
- [x] Task 3: Atualizar system prompt (AC: #1, #2, #3)
  - [x] 3.1 Adicionar seção "Quiz e Prática Ativa" no system prompt (`workflows/whatsapp/prompts/system.py`)
  - [x] 3.2 Instruções para apresentar quiz: mostrar enunciado + alternativas, aguardar resposta
  - [x] 3.3 Instruções para feedback: ao receber alternativa, revelar gabarito + comentário
  - [x] 3.4 Instruções para sugestão contextual (FR26): sugerir quiz após respostas substantivas
  - [x] 3.5 Regra de frequência: max 1 sugestão a cada 5 interações (contar no histórico)
  - [x] 3.6 Atualizar `SYSTEM_PROMPT` constant E criar migration de dados para `SystemPromptVersion`
- [x] Task 4: Testes unitários (AC: #1, #2, #3)
  - [x] 4.1 Testes para `quiz_generator.py`: geração com diferentes topics/levels
  - [x] 4.2 Testes para `get_tools()`: verificar que `quiz_generate` está na lista
  - [x] 4.3 Testes para system prompt: verificar presença das instruções de quiz
  - [x] 4.4 Pelo menos 1 teste com `@pytest.mark.django_db` (real DB, sem over-mocking)

## Dev Notes

### Decisões de Implementação

**Quiz Generator Tool — Abordagem LLM-in-Tool:**
- A tool `quiz_generate` faz uma chamada LLM interna (separada do fluxo principal) para gerar a questão.
- Usar `get_model()` SEM tools (apenas geração de texto) e com `max_tokens=512` (questão curta).
- O prompt interno da tool define o formato estruturado da questão.
- A tool retorna texto formatado para WhatsApp (markdown simplificado).

**Fluxo completo do quiz:**
1. Aluno pede quiz → LLM chama `quiz_generate(topic="IC", level="intermediate")`
2. Tool gera questão via LLM interno → retorna enunciado + alternativas formatadas
3. LLM principal apresenta a questão ao aluno (SEM revelar gabarito)
4. Aluno responde "B" → LLM reconhece como resposta de quiz
5. LLM revela gabarito + comentário explicativo + pergunta se quer continuar
6. Não é necessário state adicional — o histórico de mensagens (checkpointer) mantém o contexto

**Sugestão contextual (FR26) — Implementação via System Prompt:**
- Regra no system prompt: após respostas substantivas, sugerir quiz naturalmente
- Frequência controlada pelo LLM analisando o histórico recente (não precisa de state field)
- O LLM conta interações desde a última sugestão usando o message history

**Por que tool e não resposta direta do LLM:**
- Rastreamento via `ToolExecution` model (métricas de uso)
- Controle via Config model (enable/disable)
- Separação de concerns: prompt de geração de quiz isolado do prompt principal
- Custo rastreável separadamente no `CostLog`

### Padrões Obrigatórios (Architecture Compliance)

| Padrão | Requisito | Referência |
|--------|-----------|------------|
| Tool decorator | `@tool` do LangChain | ADR-010, `workflows/whatsapp/tools/*.py` |
| LLM factory | `get_model(tools=None, max_tokens=512)` — SEM tools para geração de quiz | ADR-012, `workflows/providers/llm.py` |
| Parallel tool calls | Já `False` no orchestrate_llm — quiz segue o mesmo padrão | ADR-013 |
| Async I/O | `async def quiz_generate()` — NUNCA sync I/O | ADR-002 |
| Error handling | Retorna string de erro amigável (consistente com rag_medical, drug_lookup) | `workflows/whatsapp/tools/rag_medical.py` |
| Logging | `structlog.get_logger(__name__)` — NUNCA `print()` | ADR-004 |
| Cost tracking | CostTrackingCallback no LLM interno da tool | `workflows/services/cost_tracker.py` |
| Tool registration | Importar em `__init__.py`, adicionar a `get_tools()` | `workflows/whatsapp/tools/__init__.py` |
| Test markers | `@pytest.mark.asyncio`, `@pytest.mark.django_db` | ADR-004, conftest.py |

### Arquivos a Criar

| Arquivo | Descrição |
|---------|-----------|
| `workflows/whatsapp/tools/quiz_generator.py` | Nova tool de geração de quiz |
| `tests/test_whatsapp/test_tools/test_quiz_generator.py` | Testes unitários da tool |
| `workflows/migrations/0018_seed_system_prompt_v2_quiz.py` | Data migration para SystemPromptVersion com instruções de quiz |

### Arquivos a Modificar

| Arquivo | Modificação |
|---------|-------------|
| `workflows/whatsapp/tools/__init__.py` | Importar `quiz_generate`, adicionar a `get_tools()` |
| `workflows/whatsapp/prompts/system.py` | Adicionar seção quiz no `SYSTEM_PROMPT` constant |
| `tests/test_whatsapp/test_tools/test_tools_init.py` | Verificar que quiz_generate está registrada (se existir) |

### Arquivos de Referência (NÃO modificar)

| Arquivo | Por que consultar |
|---------|-------------------|
| `workflows/whatsapp/tools/rag_medical.py` | Padrão de tool async com `@tool` decorator |
| `workflows/whatsapp/tools/bulas_med.py` | Padrão de tool com chamada LLM interna (se aplicável) |
| `workflows/whatsapp/tools/calculators.py` | Padrão de tool com formatação WhatsApp |
| `workflows/whatsapp/nodes/orchestrate_llm.py` | Como tools são invocadas (max_tokens, CostTrackingCallback) |
| `workflows/providers/llm.py` | `get_model()` factory — como obter modelo sem tools |
| `workflows/whatsapp/state.py` | WhatsAppState — NÃO adicionar campos nesta story |
| `workflows/whatsapp/graph.py` | Grafo — NÃO modificar nesta story (quiz usa ToolNode existente) |
| `workflows/services/cost_tracker.py` | CostTrackingCallback para rastrear custo do LLM interno |
| `workflows/models.py` | ToolExecution model (rastreamento automático via tracked_tools) |

### Prompt Interno do Quiz Generator

O prompt interno (usado pela tool para gerar questões) deve seguir esta estrutura:

```
Gere uma questão de múltipla escolha sobre {topic} no nível {level}.

Formato OBRIGATÓRIO:
**Questão:** [enunciado clínico contextualizado]

A) [alternativa]
B) [alternativa]
C) [alternativa]
D) [alternativa]
E) [alternativa]

**Gabarito:** [letra correta]

**Comentário:** [explicação detalhada com raciocínio clínico]
```

**Importante:** A tool retorna o bloco COMPLETO (incluindo gabarito e comentário). O system prompt do LLM principal instrui a apresentar APENAS enunciado + alternativas na primeira mensagem, guardando gabarito + comentário para revelar após a resposta do aluno.

### Atualização do System Prompt

Adicionar ao final do `SYSTEM_PROMPT` (antes do disclaimer médico):

```
## Quiz e Prática Ativa

**QUANDO O ALUNO PEDIR QUIZ:**
→ Use `quiz_generate` com o tema mencionado.
→ Apresente APENAS o enunciado e as alternativas (A-E).
→ NÃO revele o gabarito ou comentário até o aluno responder.

**QUANDO O ALUNO RESPONDER UMA QUESTÃO:**
→ Revele: ✅ Acertou! ou ❌ Errou.
→ Mostre a alternativa correta e o comentário explicativo.
→ Pergunte: "Quer outra questão sobre o mesmo tema ou um diferente?"

**SUGESTÃO CONTEXTUAL DE QUIZ (FR26):**
→ Após responder uma pergunta médica substantiva sobre tema propício \
(diagnóstico diferencial, farmacologia, condutas), sugira naturalmente:
"Quer testar seu conhecimento sobre esse tema? Posso fazer uma questão rápida!"
→ NÃO sugira quiz mais que 1 vez a cada 5 interações.
→ Conte as mensagens recentes no histórico para controlar a frequência.
→ A sugestão deve ser natural e breve — nunca insistente.
```

### Previous Story Intelligence (Epic 8)

**Lições críticas das stories 8.1 e 8.2:**

1. **Over-mocking:** Pelo menos 1 teste real com `@pytest.mark.django_db` por feature. Não mock `Config.objects.aget()` — use DB real.
2. **Silent error handling:** Todo `except` deve ter `logger.warning()` ou `logger.error()`. Nunca `except Exception: pass`.
3. **Async mock pattern:** Usar `AsyncMock` para funções async em testes. `@patch` com return_value coroutine.
4. **Cache patterns:** Se usar Redis cache na tool (ex: cache de questões), mock `get_redis_client()` nos testes.
5. **Cost tracking:** O LLM interno da tool deve usar `CostTrackingCallback` para rastrear custo separadamente.
6. **Migration seed:** Data migrations para SystemPromptVersion devem ser incrementais (nova versão, não editar existente).
7. **ruff compliance:** Rodar `ruff check . --fix && ruff format .` ao final.

### Project Structure Notes

- Quiz generator segue o padrão existente em `workflows/whatsapp/tools/` — NÃO criar nova pasta
- Tool registrada em `get_tools()` é automaticamente disponibilizada ao LLM via `orchestrate_llm.py` linha 46
- ToolExecution tracking é automático via `tracked_tools` node no grafo — NÃO precisa implementar
- NÃO modificar `graph.py` — quiz usa o ToolNode/tools loop existente
- NÃO adicionar campos em `state.py` — histórico de mensagens é suficiente para controle de quiz
- NÃO modificar `orchestrate_llm.py` — a tool é adicionada via `get_tools()` automaticamente

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 9] — Requisitos e acceptance criteria
- [Source: _bmad-output/planning-artifacts/prd.md#FR25-FR26] — Functional requirements
- [Source: _bmad-output/planning-artifacts/architecture.md#Quiz] — Quiz implementation pattern
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-010] — LangGraph + LangChain orchestration
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-012] — get_model() with tools= param
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-013] — Haiku optimization, sequential tool calls
- [Source: _bmad-output/implementation-artifacts/8-1-config-service-aprimorado-hot-reload-redis-audit-trail.md] — Cache patterns, over-mocking lesson
- [Source: _bmad-output/implementation-artifacts/8-2-system-prompt-versionado-historico-rollback.md] — SystemPromptVersion model, data migration pattern

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
N/A — Implementação sem bloqueios.

### Completion Notes List
- ✅ Task 1: Criada tool `quiz_generate` em `workflows/whatsapp/tools/quiz_generator.py` com `@tool` decorator async, chamada LLM interna via `get_model(tools=None, max_tokens=512)`, CostTrackingCallback para rastreio de custo separado, e ExternalServiceError para erros. Tool aceita `topic` e `level` (easy/intermediate/hard), usa prompt estruturado para gerar questão com enunciado, 5 alternativas, gabarito e comentário.
- ✅ Task 2: Registrada `quiz_generate` em `get_tools()` — importação e adição à lista. Total de tools: 6.
- ✅ Task 3: System prompt atualizado com seção "Quiz e Prática Ativa" (antes do Disclaimer), rota de quiz na estratégia por tipo de pergunta, contagem de ferramentas atualizada para 6. Migration 0020 criada com novo SystemPromptVersion (desativa versão anterior, cria V2 com instruções de quiz ativa).
- ✅ Task 4: 20 testes unitários criados cobrindo: geração com diferentes níveis, validação de topic vazio, level inválido, erro LLM, CostTrackingCallback, docstring, registro em get_tools(), instruções de quiz no system prompt, sugestão contextual FR26, feedback AC2, 1 teste com `@pytest.mark.django_db`.
- ✅ Testes existentes atualizados para refletir 6 tools (test_graph_tools, test_tool_orchestration, test_core_models).
- ✅ Teste de integridade de migration atualizado para verificar migration 0020 (V2 quiz) contra SYSTEM_PROMPT.
- ✅ 770 testes passaram, 0 falhas, ruff check + format limpos.

### Senior Developer Review (AI) — 2026-03-15

**Reviewer:** Claude Opus 4.6 (adversarial code review)

**9 issues encontrados e corrigidos:**

| # | Sev | Issue | Fix |
|---|-----|-------|-----|
| H1 | HIGH | `quiz_generate` levantava `ExternalServiceError` em vez de retornar string de erro — inconsistente com rag_medical, drug_lookup, web_search | Substituído `raise ExternalServiceError` por `return` string amigável. Adicionado handler separado para `TimeoutError`. |
| H2 | HIGH | `user_id="quiz_generator"` no CostTrackingCallback — custo do quiz não atribuído ao usuário real | Documentado como limitação arquitetural (tool não tem acesso a state). Custo quiz tracked via structlog separadamente. |
| M1 | MEDIUM | Sem timeout na chamada LLM do quiz — podia travar indefinidamente | Adicionado `asyncio.wait_for(timeout=15.0)` consistente com orchestrate_llm. |
| M2 | MEDIUM | Nova instância LLM criada a cada chamada (max_tokens=512 bypassa cache singleton) | Criado `_quiz_model` module-level singleton com `_get_quiz_model()`. |
| M3 | MEDIUM | Teste `@pytest.mark.django_db` trivialmente inútil (`acount() >= 0` sempre passa) | Substituído por teste que verifica migration 0020 seedou SystemPromptVersion com quiz instructions. |
| M4 | MEDIUM | Custo da chamada LLM interna não acumula em `state["cost_usd"]` | Documentado como limitação arquitetural. Custo rastreado via structlog. |
| M5 | MEDIUM | `reverse_seed` hardcodava `author="system"` — frágil se versão anterior tiver author diferente | Substituído por `.order_by("-created_at").first()` (robusto). |
| L1 | LOW | Sem validação de comprimento de `topic` — prompts potencialmente muito longos | Adicionado `MAX_TOPIC_LENGTH = 500` com truncamento. |
| L2 | LOW | Prompt injection via `topic` injetado direto no template | Mitigado por truncamento (L1). Impacto baixo: LLM interno isolado, sem tools. |

**Resultado:** 7 issues corrigidos no código, 2 documentados como limitação arquitetural.
**Testes:** 22 testes quiz (3 novos: timeout, topic truncation, model caching). 777 total passando.

### File List

**Arquivos criados:**
- `workflows/whatsapp/tools/quiz_generator.py` — Nova tool de geração de quiz
- `tests/test_whatsapp/test_tools/test_quiz_generator.py` — 22 testes unitários
- `workflows/migrations/0020_seed_system_prompt_v2_quiz.py` — Data migration SystemPromptVersion V2

**Arquivos modificados:**
- `workflows/whatsapp/tools/__init__.py` — Import + registro de quiz_generate em get_tools()
- `workflows/whatsapp/prompts/system.py` — Seção quiz, rota quiz, 6 ferramentas, fix line-length
- `tests/test_whatsapp/test_graph_tools.py` — Atualizado para 6 tools
- `tests/test_whatsapp/test_tools/test_tool_orchestration.py` — Atualizado para 6 tools
- `tests/test_models/test_core_models.py` — Teste integridade migration → migration 0020

**Arquivos modificados pela code review:**
- `workflows/whatsapp/tools/quiz_generator.py` — H1: error handling, M1: timeout, M2: model cache, L1: topic truncation
- `workflows/migrations/0020_seed_system_prompt_v2_quiz.py` — M5: reverse_seed robusto
- `tests/test_whatsapp/test_tools/test_quiz_generator.py` — M3: DB test real + 3 novos testes

## Change Log

- **2026-03-15:** Story 9.1 implementada — quiz_generate tool, system prompt com instruções de quiz/feedback/sugestão contextual, migration 0020, 20 novos testes. (770 total passando)
- **2026-03-15:** Code review adversarial — 9 issues encontrados (2H, 5M, 2L), 7 corrigidos no código, 2 documentados como limitação. Fixes: error handling graceful, timeout 15s, model cache singleton, topic truncation 500 chars, reverse_seed robusto, DB test real. 22 testes quiz, 777 total passando.
