# Story 2.1: RAG Médico — Busca na Base de Conhecimento com Citações `[N]`

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a aluno,
I want fazer perguntas médicas e receber respostas com citações da base de conhecimento curada Medway,
So that confio na resposta porque sei de onde vem a informação.

## Acceptance Criteria

1. **AC1 — Busca Vetorial Pinecone:** Given o aluno pergunta "Quando usar carvedilol vs metoprolol na IC?" When o ToolNode executa a tool `rag_medical_search` Then a tool busca no Pinecone com o embedding da query (top_k=5) And retorna resultados formatados com índice sequencial para citação `[N]` And cada resultado inclui: título da fonte, trecho relevante, metadata (livro/diretriz, página/seção) And os resultados são adicionados ao `retrieved_sources` do WhatsAppState com `type="rag"`

2. **AC2 — Citação pelo LLM:** Given os resultados RAG retornados ao LLM When o LLM compõe a resposta Then usa os marcadores `[N]` para citar fontes RAG And nunca cita da memória/treinamento — apenas fontes retornadas por tools

3. **AC3 — Rodapé de Fontes:** Given a resposta do LLM contém citações `[N]` When o nó `format_response` processa Then o rodapé inclui as fontes no formato `📚 *Fontes:* [1] Harrison, Cap. 252 — IC [2] Diretriz SBC 2023`

4. **AC4 — Validação de Citações:** Given a resposta contém marcadores `[N]` When `validate_citations()` executa no nó `format_response` Then marcadores `[N]` que não correspondem a fontes reais são removidos (strip)

5. **AC5 — Cobertura Zero:** Given a query não retorna resultados no Pinecone (cobertura = 0) When a tool executa Then retorna mensagem indicando que não há conteúdo curado para o tema And o LLM sabe que pode usar web search como alternativa (preparação para Story 2.2)

6. **AC6 — ToolNode no Grafo:** Given o StateGraph compilado When o LLM gera tool_calls na resposta Then o ToolNode executa as tools automaticamente And o loop tools → orchestrate_llm funciona corretamente (tool results retornam ao LLM) And o LLM compõe a resposta final com os resultados das tools

## Tasks / Subtasks

- [x] Task 1: Criar `workflows/providers/pinecone.py` — Pinecone Async Client (AC: #1)
  - [x] 1.1 Implementar `PineconeProvider` com `PineconeAsyncio` (SDK v8+, async nativo)
  - [x] 1.2 Implementar `query_similar(query_vector: list[float], top_k: int = 5) -> list[dict]` retornando matches com metadata (título, trecho, livro/diretriz, página/seção, score)
  - [x] 1.3 Usar singleton pattern com lazy initialization (mesmo padrão do `get_checkpointer()`)
  - [x] 1.4 Configurar via Django settings: `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`
  - [x] 1.5 Tratar exceções Pinecone como `ExternalServiceError` com log structlog

- [x] Task 2: Criar `workflows/providers/embeddings.py` — Embedding Provider (AC: #1)
  - [x] 2.1 Implementar `get_embeddings()` retornando instância `VertexAIEmbeddings` (model `text-embedding-004`) — MESMA VPC que Vertex AI, zero egress
  - [x] 2.2 Implementar `embed_query(text: str) -> list[float]` async wrapper
  - [x] 2.3 Usar `langchain-google-vertexai` (já é dependência do projeto)
  - [x] 2.4 Singleton caching da instância
  - [x] 2.5 **CRÍTICO:** O modelo de embedding DEVE ser o mesmo usado para indexar os documentos no Pinecone. Verificar com o time de dados qual modelo foi usado. Se não for `text-embedding-004`, ajustar aqui.

- [x] Task 3: Criar `workflows/whatsapp/tools/rag_medical.py` — RAG Tool (AC: #1, #2, #5)
  - [x] 3.1 Implementar `@tool async def rag_medical_search(query: str) -> str` com docstring clara para o LLM
  - [x] 3.2 Chamar `embed_query()` para gerar vector da query
  - [x] 3.3 Chamar `PineconeProvider.query_similar()` com top_k=5
  - [x] 3.4 Formatar cada resultado com índice `[N]` sequencial
  - [x] 3.5 Para cobertura = 0: retornar mensagem indicando sem conteúdo curado
  - [x] 3.6 Logar via structlog: `tool_executed`, query, results_count, latency_ms

- [x] Task 4: Criar `workflows/whatsapp/tools/__init__.py` — Registry de Tools (AC: #6)
  - [x] 4.1 Implementar `get_tools() -> list` retornando lista de tools registradas
  - [x] 4.2 Importar e registrar `rag_medical_search`
  - [x] 4.3 Preparar estrutura para futuras tools (web_search, drug_lookup, etc. — NÃO implementar agora)

- [x] Task 5: Modificar `workflows/whatsapp/graph.py` — Adicionar ToolNode + Loop (AC: #6)
  - [x] 5.1 Importar `ToolNode`, `tools_condition` de `langgraph.prebuilt`
  - [x] 5.2 Importar `get_tools` de `workflows.whatsapp.tools`
  - [x] 5.3 Adicionar nó `"tools"` com `ToolNode(get_tools())`
  - [x] 5.4 Substituir edge direto `orchestrate_llm → format_response` por conditional edges com tools_condition e path_map
  - [x] 5.5 Adicionar edge `"tools" → "orchestrate_llm"` (loop — tool results voltam ao LLM)
  - [x] 5.6 Manter RetryPolicy no nó orchestrate_llm
  - Nota: Tasks 5.1-5.6 já implementados pelas Stories 2.2/2.3 paralelas; verificado que rag_medical_search é incluída via get_tools()

- [x] Task 6: Modificar `workflows/whatsapp/nodes/orchestrate_llm.py` — Bind Tools ao Modelo (AC: #2, #6)
  - [x] 6.1 Importar `get_tools()` de `workflows.whatsapp.tools`
  - [x] 6.2 Usar `model.bind_tools(get_tools())` para habilitar tool calling no LLM
  - [x] 6.3 Quando o LLM retorna AIMessage com `tool_calls`, o nó retorna normalmente — o `tools_condition` no grafo roteia para ToolNode
  - [x] 6.4 Garantir que o CostTrackingCallback registra tokens de todas as invocações (incluindo re-entrada após tool results)
  - [x] 6.5 **IMPORTANTE:** NÃO alterar a lógica de system prompt ou contexto — apenas adicionar bind_tools
  - Nota: Tasks 6.1-6.5 já implementados pelas Stories 2.2/2.3 paralelas; verificado e testado

- [x] Task 7: Modificar `workflows/whatsapp/nodes/format_response.py` — Extração de Fontes + Rodapé (AC: #3, #4)
  - [x] 7.1 Implementar extração de fontes RAG de ToolMessages (via collect_sources node com _RAG_SOURCE_PATTERN)
  - [x] 7.2 Popular `retrieved_sources` no estado com as fontes extraídas (tipo `"rag"`)
  - [x] 7.3 `validate_citations()` já existe — verificado que funciona com `retrieved_sources` populadas (count de fontes RAG)
  - [x] 7.4 `_build_source_footer()` já implementado — gera bloco `📚 *Fontes:*` com cada fonte formatada
  - [x] 7.5 Rodapé inserido antes do disclaimer médico (se houver)
  - [x] 7.6 Se não há fontes RAG, não gera rodapé (mantém comportamento atual para respostas sem tools)

- [x] Task 8: Modificar `workflows/whatsapp/prompts/system.py` — Regras de Citação e Tool Use (AC: #2)
  - [x] 8.1 Adicionada seção "Uso de Ferramentas" no system prompt com regras de quando usar rag_medical_search
  - [x] 8.2 Adicionada descrição de quando usar `rag_medical_search`: perguntas médicas, farmacologia, procedimentos, diagnósticos, diretrizes
  - [x] 8.3 Mantido cache_control ephemeral no SystemMessage (prompt caching)
  - [x] 8.4 Regras de `[W-N]` já presentes no prompt (implementadas pela Story 2.2 paralela)

- [x] Task 9: Atualizar dependências e configuração (AC: #1)
  - [x] 9.1 Adicionado `pinecone[asyncio]>=8.0` ao pyproject.toml
  - [x] 9.2 Adicionados settings `PINECONE_API_KEY` e `PINECONE_INDEX_NAME` em `config/settings/base.py`
  - [x] 9.3 Atualizado `.env.example` com `PINECONE_API_KEY` e `PINECONE_INDEX_NAME`
  - [x] 9.4 Verificado que `langchain-google-vertexai` já inclui `VertexAIEmbeddings`

- [x] Task 10: Testes (AC: todos)
  - [x] 10.1 `tests/test_providers/test_pinecone.py` — 5 testes: singleton, query_similar, empty results, ExternalServiceError, correct params
  - [x] 10.2 `tests/test_providers/test_embeddings.py` — 3 testes: VertexAI instance, singleton, embed_query
  - [x] 10.3 `tests/test_whatsapp/test_tools/test_rag_medical.py` — 6 testes: formatted [N] markers, zero coverage, error handling, docstring, embed_query call, top_k=5
  - [x] 10.4 `tests/test_whatsapp/test_nodes/test_format_response_citations.py` — 8 testes: footer format, no footer when empty, combined footer, valid citations, phantom citations, format_response with footer, without footer, strips phantoms
  - [x] 10.5 `tests/test_whatsapp/test_graph_tools.py` — 5 testes: tools node, collect_sources node, orchestrate_llm node, rag in tools, full graph compilation
  - [x] 10.6 `tests/test_whatsapp/test_nodes/test_orchestrate_llm_tools.py` — 3 testes: bind_tools, tool_calls in response, cost tracking

## Dev Notes

### Contexto de Negócio

Esta é a **primeira story do Epic 2 — Medical Knowledge Tools**, o diferenciador #1 do Medbrain vs ChatGPT. A capacidade de citar fontes verificáveis (livros, diretrizes, artigos) é o que justifica o produto para alunos de medicina que precisam de referências confiáveis.

**Impacto direto:**
- FR11: Q&A médico com citações `[N]`/`[W-N]`
- FR12: RAG com fontes verificáveis (Gold `[N]`)
- FR16: Seleção automática de tools (ToolNode) — fundação para todas as tools subsequentes

**Valor para o usuário:** "Carvedilol reduz mortalidade em IC [1]" é infinitamente mais valioso que "Carvedilol é usado em IC" sem fonte.

### Padrões Obrigatórios

**Todos os padrões já estabelecidos nas Stories 1.1-1.6 e 4.1 CONTINUAM VÁLIDOS:**

| Padrão | Referência |
|--------|-----------|
| LangGraph node contract | `async def node_name(state: WhatsAppState) -> dict` |
| LangChain `@tool` decorator | Docstring usada pelo LLM para decisão de uso |
| Async/await obrigatório | Sem sync I/O |
| structlog JSON logging | Event naming: snake_case, verbos no passado |
| AppError hierarchy | `ExternalServiceError` para falhas Pinecone |
| Import order | Standard → Third-party → Local |
| Naming | snake_case (arquivos, funções), PascalCase (classes) |
| PROIBIDO | `print()`, sync I/O, `import *`, camelCase |

**Enforcement Rules de Citação (ADR-010, Padrões 12-17):**
- Marcadores `[N]` para RAG (Gold), `[W-N]` para web (Silver) — esta story implementa apenas `[N]`
- `validate_citations()` strip marcadores sem fonte real
- LLM NUNCA gera URLs ou referências de memória
- Toda citação é rastreável a fonte verificada

### Infraestrutura Já Disponível (NUNCA recriar)

| Componente | Arquivo | Status |
|-----------|---------|--------|
| WhatsAppState TypedDict | `workflows/whatsapp/state.py` | Campos `retrieved_sources`, `cited_source_indices`, `web_sources` já existem |
| StateGraph base | `workflows/whatsapp/graph.py` | `build_whatsapp_graph()` compilado — ADICIONAR ToolNode aqui |
| format_response | `workflows/whatsapp/nodes/format_response.py` | `validate_citations()` e `strip_competitor_citations()` já existem |
| orchestrate_llm | `workflows/whatsapp/nodes/orchestrate_llm.py` | Invoke model + CostTrackingCallback — ADICIONAR bind_tools |
| System prompt | `workflows/whatsapp/prompts/system.py` | Prompt com cache_control — ADICIONAR regras de citação |
| LLM provider | `workflows/providers/llm.py` | `get_model()` com Vertex AI + fallback — NÃO modificar |
| Checkpointer | `workflows/providers/checkpointer.py` | AsyncPostgresSaver singleton — NÃO modificar |
| Redis/Cache | `workflows/services/cache_manager.py` | Session cache — NÃO modificar |
| Error hierarchy | `workflows/utils/errors.py` | `ExternalServiceError` — USAR para erros Pinecone |
| Formatters | `workflows/utils/formatters.py` | Markdown → WhatsApp — NÃO modificar |
| Rate limiter | `workflows/services/rate_limiter.py` | Dual rate limiting — NÃO modificar |
| Cost tracker | `workflows/services/cost_tracker.py` | CostTrackingCallback — NÃO modificar |
| **Testes existentes** | `tests/` | ~206 testes passando (após Stories 1.1-1.6 + 4.1) |

### Inteligência de Stories Anteriores

**Lições aprendidas de Epic 1 e Epic 4:**

1. **Singleton pattern:** Usar o mesmo padrão de `get_checkpointer()` para PineconeProvider — global `_instance`, lazy init, async setup
2. **RetryPolicy no grafo:** Já funciona para orchestrate_llm e send_whatsapp. Para o nó ToolNode, o LangGraph já tem retry built-in — NÃO adicionar retry manual
3. **CostTrackingCallback:** Registra tokens de CADA invocação do LLM. Com o tools loop, o LLM será invocado múltiplas vezes — cada invocação gera um callback. O custo total da interação é a soma de todas as invocações
4. **validate_citations():** Já implementado no format_response. Atualmente faz no-op porque `retrieved_sources` está vazio. Quando populado com fontes RAG, passará a validar de verdade
5. **strip_competitor_citations():** Já implementado. Funciona independentemente de tools — sempre executa
6. **Mock patterns:** Em testes, usar `unittest.mock.AsyncMock` para providers async. Ver padrões em `tests/test_providers/test_llm.py`
7. **Config dinâmica:** `ConfigService.get()` já funciona para buscar configs. A lista de concorrentes (`blocked_competitors`) já está no Config model — será usada pela Story 2.2 (web search)

### Decisões Técnicas Específicas desta Story

**1. SDK Raw vs langchain-pinecone:**
Usar SDK raw (`pinecone[asyncio]`) conforme exemplo da arquitetura (`pinecone_index.query(vector=embed(query), top_k=5)`). O `langchain-pinecone` adiciona abstração desnecessária para nosso caso (já temos o index pronto).

**2. Embedding Model:**
Usar `VertexAIEmbeddings(model_name="text-embedding-004")` do `langchain-google-vertexai` (já é dependência). **CRÍTICO:** Confirmar com o time de dados que o index Pinecone foi criado com `text-embedding-004`. Se foi outro modelo, ajustar aqui.

**3. Fontes no State:**
O `format_response` extrai as fontes dos `ToolMessage` na conversa (parse do retorno da tool). Não precisamos de mecanismo especial — as mensagens do grafo já contêm os tool outputs.

**4. tools_condition Path Map:**
O `tools_condition` do langgraph.prebuilt retorna `"tools"` ou `END`. Para nosso grafo, `END` deve ir para `format_response`, não para o END real. Usar:
```python
builder.add_conditional_edges(
    "orchestrate_llm",
    tools_condition,
    {"tools": "tools", END: "format_response"},
)
```

**5. Pinecone Index "já indexado":**
A arquitetura diz que o Pinecone já tem documentos curados indexados. Esta story NÃO faz indexação — apenas consulta. O indexamento é responsabilidade de outro pipeline.

### Armadilhas Conhecidas (Pitfalls)

1. **Embedding dimension mismatch:** Se o modelo de embedding usado para indexar é diferente do usado para query, os resultados serão lixo. SEMPRE verificar dimensão do index vs modelo
2. **Pinecone serverless cold start:** Serverless tier pode ter latência alta na primeira query (~2-3s). Considerar warm-up no startup da aplicação
3. **tools_condition import:** Importar de `langgraph.prebuilt`, NÃO de `langgraph.graph`
4. **bind_tools vs ToolNode:** `bind_tools()` é chamado no modelo (dentro do nó orchestrate_llm). `ToolNode` é um nó separado no grafo. São coisas diferentes e AMBOS são necessários
5. **Custo com tools loop:** Cada round-trip do tools loop é uma invocação do LLM (tokens de input + output). Para uma query RAG simples: ~2 invocações (1ª com tool_call, 2ª com resultado). Monitorar custo
6. **ToolNode error handling:** Se a tool lança exceção, o ToolNode captura e retorna ToolMessage com o erro. O LLM recebe o erro e pode tentar novamente ou responder sem a tool. NÃO é necessário try/except no grafo
7. **State fields defaults:** `retrieved_sources`, `cited_source_indices`, `web_sources` podem não ter defaults. Tratar `KeyError` / usar `state.get("retrieved_sources", [])` no format_response

### Specs Técnicas Atualizadas (Web Research 2026-03-09)

**Pinecone Python SDK v8+:**
- Pacote: `pinecone` (NÃO `pinecone-client` — renomeado desde v5.1.0)
- Install: `pip install "pinecone[asyncio]"` (adiciona aiohttp para async)
- Async client: `PineconeAsyncio(api_key=...)` → `index = pc.IndexAsyncio(index_name)`
- Query: `await index.query(vector=[...], top_k=5, include_metadata=True)`
- Requer Python 3.10+

**VertexAIEmbeddings (langchain-google-vertexai):**
- Modelo recomendado: `text-embedding-004` (768 dims, melhor quality/cost)
- Instanciação: `VertexAIEmbeddings(model_name="text-embedding-004", project=PROJECT_ID, location=LOCATION)`
- Async: `await embeddings.aembed_query(text)` (nativo async)
- Já dentro da VPC do GCP — zero egress cost

### Project Structure Notes

**Arquivos a CRIAR:**
```
workflows/
├── providers/
│   ├── pinecone.py          # CRIAR — Pinecone async client
│   └── embeddings.py        # CRIAR — VertexAI embedding provider
└── whatsapp/
    └── tools/
        ├── __init__.py       # CRIAR — get_tools() registry
        └── rag_medical.py    # CRIAR — RAG search tool

tests/
├── test_providers/
│   ├── test_pinecone.py      # CRIAR — Pinecone provider tests
│   └── test_embeddings.py    # CRIAR — Embeddings provider tests
└── test_whatsapp/
    ├── test_tools/
    │   └── test_rag_medical.py       # CRIAR — RAG tool tests
    ├── test_graph_tools.py           # CRIAR — Graph + ToolNode integration
    └── test_nodes/
        ├── test_format_response_citations.py  # CRIAR — Citation tests
        └── test_orchestrate_llm_tools.py      # CRIAR — LLM + tools tests
```

**Arquivos a MODIFICAR:**
```
workflows/
├── whatsapp/
│   ├── graph.py              # MODIFICAR — Adicionar ToolNode + tools_condition
│   ├── nodes/
│   │   ├── orchestrate_llm.py    # MODIFICAR — bind_tools()
│   │   └── format_response.py    # MODIFICAR — Extração fontes + rodapé
│   └── prompts/
│       └── system.py             # MODIFICAR — Regras de citação
├── pyproject.toml               # MODIFICAR — Adicionar pinecone[asyncio]
├── config/settings/base.py      # MODIFICAR — Adicionar PINECONE_* settings
└── .env.example                 # MODIFICAR — Adicionar PINECONE_* vars
```

**Arquivos que NÃO devem ser modificados:**
- `workflows/providers/llm.py` — get_model() já funciona
- `workflows/providers/checkpointer.py` — singleton OK
- `workflows/whatsapp/state.py` — campos de citação já existem
- `workflows/models.py` — nenhum model novo nesta story
- `workflows/services/` — nenhum serviço modificado
- `workflows/utils/` — errors, formatters, sanitization OK

### References

- [Source: `_bmad-output/planning-artifacts/architecture.md` — Seção "Citation & Source Attribution Patterns" (lines 1956-2164)]
- [Source: `_bmad-output/planning-artifacts/architecture.md` — Seção "Tool Definition Pattern" (lines 631-652)]
- [Source: `_bmad-output/planning-artifacts/architecture.md` — Seção "WhatsAppState TypedDict" (lines 575-612)]
- [Source: `_bmad-output/planning-artifacts/architecture.md` — Seção "StateGraph Integration" (lines 527-548)]
- [Source: `_bmad-output/planning-artifacts/architecture.md` — Seção "Providers Directory Structure" (lines 1367-1377)]
- [Source: `_bmad-output/planning-artifacts/architecture.md` — Seção "Enforcement Rules" (lines 2228-2251)]
- [Source: `_bmad-output/planning-artifacts/epics.md` — Epic 2, Story 2.1 (lines 574-595)]
- [Source: `_bmad-output/planning-artifacts/prd.md` — FR11, FR12, FR16]
- [Source: Pinecone Python SDK docs — https://docs.pinecone.io/reference/python-sdk]
- [Source: Pinecone AsyncIO docs — https://sdk.pinecone.io/python/asyncio.html]
- [Source: LangChain-Pinecone — https://pypi.org/project/langchain-pinecone/]
- [Source: langchain-google-vertexai VertexAIEmbeddings — https://docs.langchain.com/oss/python/integrations/text_embedding]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- All 291 tests passing (0 regressions, 30 new tests for Story 2.1)
- Pinecone SDK v8.1.0 installed with asyncio support
- Tasks 5 and 6 (graph.py, orchestrate_llm.py) already implemented by parallel Stories 2.2/2.3 — verified integration

### Completion Notes List

- **Task 1:** PineconeProvider with PineconeAsyncio SDK v8+, singleton pattern, ExternalServiceError handling, structlog logging
- **Task 2:** VertexAIEmbeddings with text-embedding-004, singleton caching, async embed_query wrapper
- **Task 3:** rag_medical_search @tool with docstring for LLM, [N] formatted output, zero coverage message, error handling, structlog logging
- **Task 4:** Added rag_medical_search to get_tools() registry alongside web_search and verify_medical_paper
- **Task 5:** Graph already had ToolNode + tools_condition + tools→orchestrate_llm loop from Stories 2.2/2.3. Verified rag_medical_search is included via get_tools()
- **Task 6:** orchestrate_llm already had bind_tools(get_tools()) from Stories 2.2/2.3. Verified and tested
- **Task 7:** Added RAG source extraction (_RAG_SOURCE_PATTERN) to collect_sources node. _build_source_footer and validate_citations already worked correctly. Footer generated with 📚 *Fontes:* format
- **Task 8:** Added "Uso de Ferramentas" section to system prompt with rag_medical_search guidance. Enhanced citation rules to emphasize tool-sourced only
- **Task 9:** Added pinecone[asyncio]>=8.0 to pyproject.toml, PINECONE_API_KEY/PINECONE_INDEX_NAME to base.py and test.py and .env.example
- **Task 10:** 30 new tests across 7 test files, all passing. Full suite: 291 tests, 0 failures

### Change Log

- 2026-03-09: Story 2.1 implementation complete — RAG medical search with Pinecone, embeddings, citation system
- 2026-03-09: Code Review — 10 issues found (5 HIGH, 3 MEDIUM, 2 LOW), all fixed:
  - [HIGH] Fixed `_RAG_SOURCE_PATTERN` regex: last result not captured + title truncation on commas
  - [HIGH] Added `asyncio.Lock` to `get_pinecone()` singleton (race condition)
  - [HIGH] Fixed HumanMessage duplication in tools loop (orchestrate_llm re-entry detection)
  - [HIGH] Added `min_score=0.5` threshold to `query_similar()` (filter irrelevant results)
  - [MEDIUM] Added `ExternalServiceError` wrapping in `embed_query()`
  - [MEDIUM] Fixed `PineconeProvider.__init__` type hint (`object` → `Any`)
  - [MEDIUM] Fixed test docstring (bind_tools → get_model(tools=...))
  - [LOW] Truncated query to 80 chars in rag_medical logs (privacy)
  - [LOW] Populated `cited_source_indices` in format_response return
  - 4 new tests added, 1 test updated. Full suite: 301 passed, 0 regressions

### File List

**Created:**
- workflows/providers/pinecone.py
- workflows/providers/embeddings.py
- workflows/whatsapp/tools/rag_medical.py
- tests/test_providers/test_pinecone.py
- tests/test_providers/test_embeddings.py
- tests/test_whatsapp/test_tools/__init__.py
- tests/test_whatsapp/test_tools/test_rag_medical.py
- tests/test_whatsapp/test_nodes/test_format_response_citations.py
- tests/test_whatsapp/test_graph_tools.py
- tests/test_whatsapp/test_nodes/test_orchestrate_llm_tools.py

**Modified:**
- workflows/whatsapp/tools/__init__.py (added rag_medical_search to registry)
- workflows/whatsapp/nodes/collect_sources.py (added RAG source extraction)
- workflows/whatsapp/prompts/system.py (added tool use guidance section)
- config/settings/base.py (added PINECONE_API_KEY, PINECONE_INDEX_NAME)
- config/settings/test.py (added test Pinecone credentials)
- pyproject.toml (added pinecone[asyncio]>=8.0)
- .env.example (added PINECONE_API_KEY, PINECONE_INDEX_NAME)

