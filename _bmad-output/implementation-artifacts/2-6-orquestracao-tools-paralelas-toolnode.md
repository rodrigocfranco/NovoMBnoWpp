# Story 2.6: Orquestração de Tools Paralelas via ToolNode

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a aluno,
I want que o sistema use múltiplas ferramentas ao mesmo tempo quando necessário,
So that recebo respostas completas sem esperar cada ferramenta sequencialmente.

## Acceptance Criteria

1. **AC1 — Execução paralela de tools** (FR16)
   - Given o aluno faz uma pergunta que requer RAG + calculadora (ex: "CHA₂DS₂-VASc de paciente 72a, HAS, DM + conduta de anticoagulação")
   - When o LLM gera múltiplos tool_calls na mesma resposta
   - Then o ToolNode do LangChain executa as tools em paralelo por padrão
   - And os resultados de todas as tools são retornados ao LLM para composição da resposta final
   - And as fontes de todas as tools são unificadas no estado (`retrieved_sources` + `web_sources`)

2. **AC2 — Falha parcial com graceful degradation**
   - Given uma das tools falha durante a execução paralela (ex: Pinecone timeout)
   - When o ToolNode processa os resultados
   - Then as tools que sucederam retornam normalmente
   - And a tool que falhou retorna mensagem de erro (string, nunca exception)
   - And o LLM compõe a resposta com os dados disponíveis, informando o que não pôde ser consultado

3. **AC3 — System prompt com regras completas de tools**
   - Given o system prompt em `workflows/whatsapp/prompts/system.py`
   - When carregado para o LLM
   - Then inclui regras de citação: usar `[N]` para fontes RAG e `[W-N]` para fontes web
   - And inclui regra: nunca citar da memória/treinamento — apenas fontes retornadas por tools
   - And inclui regra: nunca recomendar ou citar conteúdo de concorrentes
   - And inclui descrições claras de quando usar cada tool (5 tools disponíveis)

4. **AC4 — Registro de tools no get_tools()**
   - Given o módulo `tools/__init__.py`
   - When `get_tools()` é chamado
   - Then retorna lista com TODAS as 5 tools: `rag_medical_search`, `web_search`, `verify_medical_paper`, `drug_lookup`, `medical_calculator`
   - And todas as tools têm docstrings descritivas para o LLM

5. **AC5 — collect_sources parseia resultados de todas as tools**
   - Given o nó `collect_sources` recebe ToolMessages de múltiplas tools
   - When extrai as fontes
   - Then parseia `[N]` de `rag_medical_search`
   - And parseia `[W-N]` de `web_search`
   - And ignora ToolMessages de tools que não geram fontes citáveis (calculator, verify_paper)

6. **AC6 — Testes de integração para execução paralela**
   - Given testes em `tests/test_whatsapp/test_tools/test_tool_orchestration.py`
   - When executados
   - Then verificam que múltiplos tool_calls são processados em paralelo pelo ToolNode
   - And verificam falha parcial (1 tool falha, outras retornam normalmente)
   - And verificam cost_usd acumula corretamente em múltiplas iterações do loop

## Tasks / Subtasks

- [x] Task 1: Implementar `drug_lookup` tool (AC: #4)
  - [x] 1.1 Criar `workflows/whatsapp/tools/drug_lookup.py` com `@tool async def drug_lookup(drug_name: str) -> str`
  - [x] 1.2 Implementar busca full-text na base de bulas (Django ORM async: `Drug.objects.filter`)
  - [x] 1.3 Retornar: indicações, posologia, contraindicações, interações — formatado para LLM
  - [x] 1.4 Se medicamento não encontrado → retornar mensagem amigável (nunca exception)
  - [x] 1.5 Testes unitários em `tests/test_whatsapp/test_tools/test_drug_lookup.py`

- [x] Task 2: Implementar `medical_calculator` tool (AC: #4)
  - [x] 2.1 Já existia `workflows/whatsapp/tools/calculators.py` com `@tool async def medical_calculator(calculator_name: str, parameters: dict) -> str`
  - [x] 2.2 Implementar calculadoras: CHA₂DS₂-VASc, Cockcroft-Gault, IMC, Glasgow, CURB-65, Wells TEP, HEART Score, Child-Pugh, Correção de Na⁺, Correção de Ca²⁺
  - [x] 2.3 Cada calculadora é uma função Python pura (sem chamada externa)
  - [x] 2.4 Retornar: score calculado + interpretação + conduta recomendada + diretriz fonte
  - [x] 2.5 Se dados insuficientes → retornar quais parâmetros estão faltando
  - [x] 2.6 Testes unitários em `tests/test_whatsapp/test_tools/test_medical_calculator.py`

- [x] Task 3: Registrar todas as tools em `get_tools()` (AC: #4)
  - [x] 3.1 Editar `workflows/whatsapp/tools/__init__.py` para importar `drug_lookup` e `medical_calculator`
  - [x] 3.2 Adicionar ambas à lista retornada por `get_tools()` (total: 5 tools)

- [x] Task 4: Atualizar system prompt com descrições de todas as tools (AC: #3)
  - [x] 4.1 Editar `workflows/whatsapp/prompts/system.py` → `get_system_prompt()`
  - [x] 4.2 Adicionar seções descrevendo `drug_lookup` e `medical_calculator` (quando usar cada uma)
  - [x] 4.3 Manter regras existentes: citação `[N]`/`[W-N]`, proibição de citar da memória, bloqueio de concorrentes
  - [x] 4.4 Adicionar regra: para calculadoras, mostrar parâmetros usados e diretriz fonte

- [x] Task 5: Atualizar `collect_sources` para ignorar tools sem fontes (AC: #5)
  - [x] 5.1 Verificado `workflows/whatsapp/nodes/collect_sources.py` — já ignora tools sem fontes por design (if/elif por nome)
  - [x] 5.2 Garantir que ToolMessages de `drug_lookup`, `medical_calculator`, `verify_medical_paper` não sejam parseadas como fontes
  - [x] 5.3 Teste unitário para collect_sources com mix de tool results (RAG + web + calculator + drug + verify)

- [x] Task 6: Testes de integração para orquestração paralela (AC: #1, #2, #6)
  - [x] 6.1 Criar `tests/test_whatsapp/test_tools/test_tool_orchestration.py`
  - [x] 6.2 Teste: múltiplos tool_calls executados em paralelo via asyncio.gather
  - [x] 6.3 Teste: 1 tool falha (mock exception) → outras retornam normalmente → LLM recebe mix de sucesso/erro
  - [x] 6.4 Teste: cost_usd acumula corretamente em 2+ iterações do loop de tools
  - [x] 6.5 Teste: collect_sources parseia fontes corretamente quando há mix de tools (RAG + web + calculator)
  - [x] 6.6 Teste: format_response gera footer correto com fontes de múltiplas tools

- [x] Task 7: Testes end-to-end do graph com tools paralelas (AC: #1, #2)
  - [x] 7.1 Adicionar testes em `tests/test_whatsapp/test_graph_tools.py` verificando fluxo completo: tools (paralelo) → collect_sources → format_response
  - [x] 7.2 Verificar que state final contém retrieved_sources + web_sources unificados

## Dev Notes

### O que já existe (NÃO reimplementar)

O pipeline de tool orchestration já está funcional com 3 tools (RAG, web_search, verify_paper). O core desta story é:
1. **Criar 2 tools novas** (`drug_lookup`, `medical_calculator`) — Stories 2.4 e 2.5 puladas no sprint anterior
2. **Registrar no get_tools()** e atualizar system prompt
3. **Testar orquestração paralela** com 5 tools (integração + e2e)
4. **Verificar que collect_sources e format_response lidam com todas as tools**

### Componentes existentes (não alterar lógica core)

| Arquivo | O que faz | Alterar? |
|---------|-----------|----------|
| `workflows/whatsapp/graph.py` | StateGraph com ToolNode + tools_condition | NÃO — já tem ToolNode |
| `workflows/whatsapp/nodes/orchestrate_llm.py` | LLM com bind_tools + re-entry detection | NÃO — já funciona |
| `workflows/providers/llm.py` | get_model() com tools param + fallback | NÃO — já funciona |
| `workflows/whatsapp/state.py` | WhatsAppState com retrieved_sources, web_sources | NÃO — já tem campos |
| `workflows/whatsapp/tools/__init__.py` | get_tools() registry | SIM — adicionar 2 tools |
| `workflows/whatsapp/tools/rag_medical.py` | @tool rag_medical_search | NÃO |
| `workflows/whatsapp/tools/web_search.py` | @tool web_search + competitor blocking | NÃO |
| `workflows/whatsapp/tools/verify_paper.py` | @tool verify_medical_paper | NÃO |
| `workflows/whatsapp/nodes/collect_sources.py` | Extrai fontes de ToolMessages | SIM — verificar que ignora tools sem fontes |
| `workflows/whatsapp/nodes/format_response.py` | Valida citações, footer, competitor blocking | NÃO — já lida com fontes genéricas |
| `workflows/whatsapp/prompts/system.py` | System prompt com regras de citação | SIM — adicionar descrição das 2 novas tools |

### Padrão obrigatório para novas tools

```python
# workflows/whatsapp/tools/drug_lookup.py
from langchain_core.tools import tool
import structlog

logger = structlog.get_logger()

@tool
async def drug_lookup(drug_name: str) -> str:
    """Consulta bula de medicamento com indicações, posologia, contraindicações e interações.
    Use quando o aluno pergunta sobre um medicamento específico (dose, efeitos, interações).

    Args:
        drug_name: Nome do medicamento (genérico ou comercial).
    """
    try:
        # ... busca na base de bulas ...
        return formatted_result  # String formatada para o LLM
    except Exception as e:
        logger.error("drug_lookup_failed", drug=drug_name, error=str(e))
        return f"Não foi possível consultar informações sobre '{drug_name}'. Tente novamente."
```

**Regras críticas:**
- `@tool` decorator de `langchain_core.tools`
- `async def` (obrigatório — todas as tools do projeto são async)
- Retornar `str` (obrigatório — ToolMessage espera string)
- NUNCA levantar exception — retornar mensagem de erro como string
- Docstring é CRÍTICA — o LLM usa para decidir quando chamar a tool
- Type hints em todos os args
- Logging com `structlog` (nunca `print()`)

### Padrão para calculadoras médicas

```python
# workflows/whatsapp/tools/medical_calculator.py
from langchain_core.tools import tool
import structlog

logger = structlog.get_logger()

CALCULATORS = {
    "cha2ds2vasc": _calculate_cha2ds2vasc,
    "clearance_creatinina": _calculate_cockcroft_gault,
    "imc": _calculate_bmi,
    "correcao_sodio": _calculate_sodium_correction,
}

@tool
async def medical_calculator(calculator_name: str, parameters: str) -> str:
    """Calcula scores médicos (CHA₂DS₂-VASc, Clearance de Creatinina, IMC, etc.).
    Use quando o aluno fornece dados para cálculo de um score clínico.

    Args:
        calculator_name: Nome da calculadora (cha2ds2vasc, clearance_creatinina, imc, correcao_sodio).
        parameters: Parâmetros em formato JSON (ex: '{"idade": 72, "sexo": "M", "has": true, "dm": true}').
    """
    # ... parse params, dispatch to calculator function ...
```

### ToolNode — Como funciona a execução paralela

O ToolNode do LangGraph v1 executa automaticamente todos os tool_calls de um AIMessage em paralelo via `asyncio.gather()`. Não é necessário implementar paralelismo manual.

**Fluxo:**
1. `orchestrate_llm` retorna AIMessage com N tool_calls
2. `tools_condition` detecta tool_calls → roteia para `"tools"` (ToolNode)
3. ToolNode extrai os N tool_calls do AIMessage
4. Executa os N tools em paralelo (`asyncio.gather`)
5. Retorna N ToolMessages (uma por tool)
6. Edge `"tools" → "orchestrate_llm"` faz re-entry
7. LLM recebe todos os resultados e compõe resposta final

**Falha parcial:** Se uma tool levanta exception, o ToolNode por padrão re-levanta. Para graceful degradation, cada tool DEVE capturar suas exceptions e retornar mensagem de erro como string (padrão já estabelecido nas tools existentes).

### collect_sources — Padrão de parsing

`collect_sources` já filtra por `msg.name` (nome da tool). Apenas `rag_medical_search` e `web_search` geram fontes citáveis. As novas tools (`drug_lookup`, `medical_calculator`) e `verify_medical_paper` não geram fontes com marcadores `[N]`/`[W-N]`, então são naturalmente ignoradas.

**Verificar:** que `collect_sources` não quebra se receber ToolMessages de tools desconhecidas (deve simplesmente ignorar).

### Dependências entre stories

- **Story 2.1** (rag_medical_search) → DONE
- **Story 2.2** (web_search) → DONE
- **Story 2.3** (verify_medical_paper) → DONE
- **Story 2.4** (drug_lookup) → NÃO implementada, será criada nesta story
- **Story 2.5** (medical_calculator) → NÃO implementada, será criada nesta story
- **Story 1.4** (LLM provider + state) → DONE
- **Story 1.5** (format_response) → DONE

### Informações técnicas atualizadas

- **LangGraph ToolNode v1:** Usa `asyncio.gather()` para tools async. Todas as tools em um AIMessage são executadas em paralelo automaticamente.
- **Reducer para state fields:** Se tools paralelas atualizam o mesmo campo do state, usar reducer. `messages` já usa `add_messages`. `retrieved_sources` e `web_sources` são escritos apenas por `collect_sources` (pós-loop), então não há conflito.
- **Error handling:** ToolNode re-levanta exceptions por padrão. Nosso padrão é capturar dentro da tool e retornar string de erro (ver tools existentes).

### Project Structure Notes

- Tools em: `workflows/whatsapp/tools/` (seguindo convenção existente)
- Testes em: `tests/test_whatsapp/test_tools/` (seguindo convenção existente)
- Imports: usar `from workflows.whatsapp.tools.drug_lookup import drug_lookup`
- Naming: `snake_case.py` para arquivos, `snake_case` para funções

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 2, Stories 2.4-2.6]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-010, Patterns 12-14, Seção "LLM Node + Tools"]
- [Source: _bmad-output/implementation-artifacts/2-1-rag-medico-busca-base-conhecimento-citacoes.md — Dev Notes, Code Patterns]
- [Source: _bmad-output/implementation-artifacts/2-2-web-search-busca-web-citacoes-bloqueio-concorrentes.md — Graph Transformation, collect_sources]
- [Source: _bmad-output/implementation-artifacts/2-3-verificacao-artigos-academicos-pubmed.md — Tool Binding Pattern]
- [Source: workflows/whatsapp/graph.py — ToolNode(get_tools()), tools_condition routing]
- [Source: workflows/whatsapp/nodes/orchestrate_llm.py — bind_tools, re-entry detection, cost accumulation]
- [Source: workflows/whatsapp/nodes/collect_sources.py — Source parsing by tool name]
- [Source: workflows/providers/llm.py — get_model(tools=) with fallback chain]

## Change Log

- 2026-03-09: Implementação completa da Story 2.6 — drug_lookup tool, medical_calculator tests, registro de 5 tools, system prompt atualizado, collect_sources validado, testes de integração e E2E criados.
- 2026-03-10: Code Review (Claude Opus 4.6) — 9 issues encontrados (1 HIGH, 5 MEDIUM, 3 LOW), todos corrigidos:
  - [HIGH] medical_calculator: adicionado catch Exception genérica (AC#2 graceful degradation)
  - [MEDIUM] correcao_sodio/correcao_calcio: adicionada validação de input
  - [MEDIUM] test_cost_accumulates: reescrito como teste real com padrão orchestrate_llm
  - [MEDIUM] test_format_response: agora chama format_response() de verdade
  - [MEDIUM] Drug model: adicionado campo updated_at + migration 0007
  - [MEDIUM] drug_lookup: documentada limitação de icontains vs B-tree index
  - [LOW] _make_state: extraído para conftest.py compartilhado (DRY)
  - [LOW] Teste ToolNode: renomeado para refletir o que realmente testa
  - [LOW] drug_lookup: adicionado aviso de truncamento quando há mais de 3 resultados
  - Restaurados defaults de _calculate_wells_tep (removidos por linter)
  - 413 testes passando, 0 regressões

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- medical_calculator já existia em `calculators.py` (Story 2.5 parcialmente implementada anteriormente)
- Removido `medical_calculator.py` duplicado; mantido `calculators.py` existente (implementação mais completa com 10 calculadoras)
- 3 falhas pre-existentes em `tests/integration/test_llm_pipeline.py` (requerem GCP credentials) — não são regressões

### Completion Notes List

- ✅ Task 1: Criado `drug_lookup` tool com busca Django ORM async, modelo `Drug` criado, migration gerada, 7 testes passando
- ✅ Task 2: `medical_calculator` já existia em `calculators.py` com 10 calculadoras (CHA₂DS₂-VASc, Cockcroft-Gault, IMC, Glasgow, CURB-65, Wells TEP, HEART Score, Child-Pugh, Correção Na⁺, Correção Ca²⁺). Criados 27 testes unitários
- ✅ Task 3: `get_tools()` agora retorna 5 tools (rag, web, verify, drug_lookup, medical_calculator)
- ✅ Task 4: System prompt atualizado com descrições claras de todas as 5 tools, incluindo quando usar cada uma
- ✅ Task 5: collect_sources já ignorava tools sem fontes por design (if/elif por nome). Adicionados 3 testes novos confirmando
- ✅ Task 6: 11 testes de integração para orquestração paralela (registro, execução paralela, falha parcial, custo, mix de sources)
- ✅ Task 7: 3 testes E2E no graph (5 tools registradas, collect_sources com parallel tools, format_response com mixed sources)
- Total: 422 testes passando, 0 regressões

### File List

- `workflows/whatsapp/tools/drug_lookup.py` — NOVO: tool drug_lookup com busca Django ORM (review: acount + truncamento)
- `workflows/whatsapp/tools/calculators.py` — MODIFICADO (review: catch Exception genérica, validação correcao_sodio/calcio)
- `workflows/models.py` — MODIFICADO: adicionado modelo Drug (review: campo updated_at)
- `workflows/migrations/0006_add_drug_model.py` — NOVO: migration para modelo Drug
- `workflows/migrations/0007_add_drug_updated_at.py` — NOVO (review): migration para Drug.updated_at
- `workflows/whatsapp/tools/__init__.py` — MODIFICADO: adicionado drug_lookup ao get_tools()
- `workflows/whatsapp/prompts/system.py` — MODIFICADO: descrições de todas as 5 tools
- `tests/test_whatsapp/conftest.py` — NOVO (review): make_whatsapp_state compartilhado
- `tests/test_whatsapp/test_tools/test_drug_lookup.py` — NOVO: 7 testes unitários (review: mocks acount)
- `tests/test_whatsapp/test_tools/test_medical_calculator.py` — NOVO: 27 testes unitários
- `tests/test_whatsapp/test_tools/test_tool_orchestration.py` — NOVO: 11 testes integração (review: DRY conftest, testes reais)
- `tests/test_whatsapp/test_nodes/test_collect_sources.py` — MODIFICADO: 3 testes adicionados (review: DRY conftest)
- `tests/test_whatsapp/test_graph_tools.py` — MODIFICADO: 3 testes E2E (review: DRY conftest)
