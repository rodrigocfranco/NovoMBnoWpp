# Story 2.2: Web Search — Busca Web com Citações [W-N] e Bloqueio de Concorrentes

Status: done

## Story

As a aluno,
I want receber informações da web quando a base de conhecimento não cobre minha dúvida,
So that tenho acesso a informações atualizadas com fontes verificáveis.

## Acceptance Criteria

1. **Given** o LLM decide que precisa de informações da web **When** o ToolNode executa a tool `web_search` **Then** a tool usa Tavily com `search_depth="advanced"`, `include_raw_content=True`, `max_results=8` **And** `exclude_domains` contém a lista de concorrentes carregada do Config model (Medcurso, Medgrupo, MedCof, Estratégia MED, Medcel, Sanar, Aristo, Yellowbook, O Residente, Afya) **And** resultados são formatados com índice `[W-N]` (ex: `[W-1]`, `[W-2]`) **And** cada resultado inclui: título, URL, trecho relevante **And** os resultados são adicionados ao `web_sources` do WhatsAppState com `type="web"` **And** o rodapé inclui fontes web: `🌐 *Web:* [W-1] PubMed — doi:10.1000/xyz`

2. **Given** todos os resultados do Tavily são de domínios bloqueados **When** a tool executa **Then** retorna mensagem indicando que não encontrou fontes web confiáveis **And** o LLM responde sem citação web

3. **Given** a lista de concorrentes no Config model é atualizada via Django Admin **When** a próxima busca web é executada **Then** usa a lista atualizada (via ConfigService)

## Tasks / Subtasks

- [x] **Task 1: Infraestrutura ToolNode no grafo** (AC: #1)
  - [x] 1.1 Modificar `graph.py`: adicionar nó `tools` (ToolNode) + conditional edges (`tools_condition`) para loop de tools entre `orchestrate_llm` e `format_response`
  - [x] 1.2 Modificar `orchestrate_llm.py`: usar `model.bind_tools(tools)` para que o LLM saiba quais tools estão disponíveis
  - [x] 1.3 Criar `workflows/whatsapp/tools/__init__.py` com `get_tools() -> list[BaseTool]` que retorna as tools disponíveis
  - [x] 1.4 Adicionar nó para coletar fontes do ToolMessage e popular `web_sources` no state

- [x] **Task 2: Tool `web_search`** (AC: #1, #2, #3)
  - [x] 2.1 Criar `workflows/whatsapp/tools/web_search.py` com `@tool` decorator (async)
  - [x] 2.2 Usar `AsyncTavilyClient` com parâmetros: `search_depth="advanced"`, `include_raw_content=True`, `max_results=8`, `exclude_domains=blocked`
  - [x] 2.3 Carregar lista de concorrentes via `ConfigService.get("blocked_competitors")` com fallback hardcoded
  - [x] 2.4 Formatar resultados com `[W-N]` markers incluindo título, URL, e conteúdo truncado (800 chars)
  - [x] 2.5 Tratar erros: timeout (10s), rate limit (429), API key inválida

- [x] **Task 3: Dependências e configuração** (AC: #1)
  - [x] 3.1 Adicionar `tavily-python` ao pyproject.toml
  - [x] 3.2 Adicionar `TAVILY_API_KEY` ao `.env.example` e `config/settings/base.py`
  - [x] 3.3 Criar data migration para atualizar `blocked_competitors` no Config model com a lista correta de domínios de concorrentes

- [x] **Task 4: Formatação de rodapé de fontes** (AC: #1)
  - [x] 4.1 Adicionar geração de rodapé de fontes no `format_response.py`: `🌐 *Web:* [W-1] Título — URL`
  - [x] 4.2 O rodapé é inserido ANTES do disclaimer médico e ANTES do rate limit warning

- [x] **Task 5: Testes** (AC: #1, #2, #3)
  - [x] 5.1 Testes unitários para `web_search` tool com Tavily mockado
  - [x] 5.2 Testes para `exclude_domains` com lista de concorrentes
  - [x] 5.3 Testes para cenário de todos resultados bloqueados
  - [x] 5.4 Testes para formatação `[W-N]` e rodapé de fontes
  - [x] 5.5 Testes para `validate_citations` com web_sources (já existente, garantir cobertura)
  - [x] 5.6 Testes para integração ToolNode no grafo (tool loop funcional)

## Dev Notes

### Contexto Crítico — Primeira Tool do Projeto

**Esta é a PRIMEIRA tool implementada no projeto.** O grafo atual é linear (sem ToolNode):

```
START → identify_user → rate_limit → load_context → orchestrate_llm → format_response → send_whatsapp → persist → END
```

Precisa ser modificado para:

```
START → identify_user → rate_limit → load_context → orchestrate_llm
    ↓ (tools_condition: se LLM pediu tools)
    tools (ToolNode) → orchestrate_llm (loop)
    ↓ (tools_condition: se NÃO pediu tools)
    collect_sources → format_response → send_whatsapp → persist → END
```

### Padrões de Arquitetura Obrigatórios

**LangGraph node contract:**
```python
async def node_name(state: WhatsAppState) -> dict
```

**LangChain @tool decorator:**
```python
from langchain_core.tools import tool

@tool
async def web_search(query: str) -> str:
    """Busca informações médicas atualizadas na internet.
    Use quando a informação não está disponível na base de conhecimento Medway.

    Args:
        query: Consulta médica para buscar na web.
    """
```

**Error hierarchy:**
- `ExternalServiceError(service="tavily", message=...)` para falhas do Tavily
- NÃO levantar exceção fatal — retornar mensagem de erro como string para o LLM decidir

### Modificações em Arquivos Existentes

#### 1. `workflows/whatsapp/graph.py` (MODIFICAR)

Adicionar ToolNode + conditional edges. Código atual:

```python
# Atual (linha 58-59):
builder.add_edge("load_context", "orchestrate_llm")
builder.add_edge("orchestrate_llm", "format_response")

# Deve virar:
from langgraph.prebuilt import ToolNode, tools_condition
from workflows.whatsapp.tools import get_tools

tools = get_tools()
builder.add_node("tools", ToolNode(tools))
builder.add_node("collect_sources", collect_sources)

builder.add_edge("load_context", "orchestrate_llm")
builder.add_conditional_edges(
    "orchestrate_llm",
    tools_condition,
    {"tools": "tools", "__end__": "collect_sources"},
)
builder.add_edge("tools", "orchestrate_llm")  # loop
builder.add_edge("collect_sources", "format_response")
```

**ATENÇÃO:** `tools_condition` do LangGraph retorna `"tools"` se a última AIMessage contém `tool_calls`, e `"__end__"` caso contrário. Mapear `"__end__"` para o próximo nó real (NÃO para END).

[Source: workflows/whatsapp/graph.py — linhas 54-62]

#### 2. `workflows/whatsapp/nodes/orchestrate_llm.py` (MODIFICAR)

O modelo precisa saber quais tools existem via `bind_tools()`:

```python
# Atual (linha 29):
model = get_model()

# Deve virar:
from workflows.whatsapp.tools import get_tools

model = get_model()
tools = get_tools()
if tools:
    model = model.bind_tools(tools)
```

**ATENÇÃO:** `bind_tools()` retorna um novo modelo (Runnable), NÃO modifica in-place. Atribuir ao mesmo `model`.

[Source: workflows/whatsapp/nodes/orchestrate_llm.py — linhas 25-43]

#### 3. `workflows/whatsapp/nodes/format_response.py` (MODIFICAR)

Adicionar formatação de rodapé de fontes web. Inserir ANTES do disclaimer médico:

```python
# Após strip_competitor_citations (linha 108) e ANTES de markdown_to_whatsapp (linha 111):

# Build source footer
source_footer = _build_source_footer(
    state.get("retrieved_sources", []),
    state.get("web_sources", []),
)
if source_footer:
    text = text + "\n\n" + source_footer
```

Função auxiliar:
```python
def _build_source_footer(rag_sources: list[dict], web_sources: list[dict]) -> str:
    """Build formatted source footer for WhatsApp."""
    lines = []
    if rag_sources:
        lines.append("📚 *Fontes:*")
        for src in rag_sources:
            idx = src.get("index", "?")
            title = src.get("title", "Fonte desconhecida")
            lines.append(f"[{idx}] {title}")
    if web_sources:
        lines.append("🌐 *Web:*")
        for src in web_sources:
            idx = src.get("index", "?")
            title = src.get("title", "")
            url = src.get("url", "")
            lines.append(f"[W-{idx}] {title} — {url}")
    return "\n".join(lines)
```

**IMPORTANTE:** O rodapé deve ser inserido ANTES da conversão markdown_to_whatsapp para que os marcadores sejam formatados corretamente.

[Source: workflows/whatsapp/nodes/format_response.py — linhas 70-137]

#### 4. `pyproject.toml` (MODIFICAR)

```toml
# Adicionar na seção dependencies:
"tavily-python>=0.5",
```

[Source: pyproject.toml — linha 24]

#### 5. `.env.example` (MODIFICAR)

```env
# Tavily (Web Search)
TAVILY_API_KEY=your-tavily-api-key
```

[Source: .env.example — após linha 33]

#### 6. `config/settings/base.py` (MODIFICAR)

```python
# Tavily (Web Search)
TAVILY_API_KEY: str = env("TAVILY_API_KEY", default="")
```

[Source: config/settings/base.py — após linha 34]

### Novos Arquivos a Criar

#### 1. `workflows/whatsapp/tools/web_search.py` (CRIAR)

Tool principal. Padrão da arquitetura:

```python
"""Tool: web search via Tavily with competitor domain blocking."""

import structlog
from langchain_core.tools import tool
from tavily import AsyncTavilyClient

from workflows.services.config_service import ConfigService

logger = structlog.get_logger(__name__)

# Fallback hardcoded — usado se Config model não tiver a chave
FALLBACK_COMPETITOR_DOMAINS = [
    "medgrupo.com.br",
    "grupomedcof.com.br",
    "med.estrategia.com",
    "estrategia.com",
    "medcel.com.br",
    "sanarmed.com",
    "sanarflix.com.br",
    "sanar.com.br",
    "aristo.com.br",
    "eumedicoresidente.com.br",
    "revisamed.com.br",
    "medprovas.com.br",
    "vrmed.com.br",
    "medmentoria.com",
    "oresidente.org",
    "afya.com.br",
]


async def _get_blocked_domains() -> list[str]:
    """Load blocked competitor domains from Config model with hardcoded fallback."""
    try:
        config_value = await ConfigService.get("blocked_competitors")
        if isinstance(config_value, dict):
            return config_value.get("domains", FALLBACK_COMPETITOR_DOMAINS)
        if isinstance(config_value, list):
            return config_value
    except Exception:
        logger.warning("blocked_competitors_config_not_found", fallback="hardcoded")
    return FALLBACK_COMPETITOR_DOMAINS


@tool
async def web_search(query: str) -> str:
    """Busca informações médicas atualizadas na internet.

    Use quando a informação não está disponível na base de conhecimento
    Medway (RAG), ou quando precisa de dados recentes como diretrizes
    atualizadas, artigos recentes, ou informações que mudam frequentemente.

    Args:
        query: Consulta médica para buscar na web.
    """
    # ... implementação
```

**Parâmetros Tavily obrigatórios (da arquitetura):**
- `search_depth="advanced"` — busca profunda para conteúdo médico
- `include_raw_content=True` — conteúdo completo, não resumo
- `max_results=8` — máximo de resultados
- `exclude_domains=blocked` — CRÍTICO: bloquear concorrentes
- `topic="general"` — default (não usar "news" para médico)

**Formato de retorno:** String formatada com `[W-N]` markers para o LLM citar.

**API Key:** Usar `django.conf.settings.TAVILY_API_KEY` para inicializar `AsyncTavilyClient(api_key=...)`.

[Source: architecture.md — linhas 1975-2017, padrão code pattern]

#### 2. `workflows/whatsapp/tools/__init__.py` (MODIFICAR — atualmente vazio)

```python
"""LangChain tools for WhatsApp graph ToolNode."""

from langchain_core.tools import BaseTool

from workflows.whatsapp.tools.web_search import web_search


def get_tools() -> list[BaseTool]:
    """Return all available tools for ToolNode."""
    return [web_search]
```

**IMPORTANTE:** Esta função é importada por `graph.py` e `orchestrate_llm.py`. Quando novas tools forem adicionadas (RAG, calculadoras, etc.), basta adicionar ao return list.

#### 3. `workflows/whatsapp/nodes/collect_sources.py` (CRIAR)

Nó intermediário para extrair fontes web dos ToolMessages e popular o state:

```python
"""Graph node: collect sources from tool execution results."""

import re
import structlog
from langchain_core.messages import ToolMessage
from workflows.whatsapp.state import WhatsAppState

logger = structlog.get_logger(__name__)


async def collect_sources(state: WhatsAppState) -> dict:
    """Extract web sources from tool messages and populate state fields."""
    web_sources = []
    # Parse [W-N] markers from tool results in messages
    for msg in state["messages"]:
        if isinstance(msg, ToolMessage) and msg.name == "web_search":
            # Parse sources from formatted tool output
            # ... extração de fontes
    return {"web_sources": web_sources}
```

#### 4. Data migration: `workflows/migrations/0005_update_blocked_competitors.py` (CRIAR)

A migration atual (`0002_initial_configs.py`) tem `blocked_competitors` com valores errados (`["chatgpt", "gemini", "copilot"]`). Criar migration para atualizar com a lista correta de domínios:

```python
def update_blocked_competitors(apps, schema_editor):
    Config = apps.get_model("workflows", "Config")
    config = Config.objects.get(key="blocked_competitors")
    config.value = {
        "domains": [
            "medgrupo.com.br", "grupomedcof.com.br",
            "med.estrategia.com", "estrategia.com",
            "medcel.com.br", "sanarmed.com", "sanarflix.com.br",
            "sanar.com.br", "aristo.com.br",
            "eumedicoresidente.com.br", "revisamed.com.br",
            "medprovas.com.br", "vrmed.com.br",
            "medmentoria.com", "oresidente.org", "afya.com.br",
        ],
        "names": [
            "medcurso", "medgrupo", "medcof", "estratégia med",
            "medcel", "afya", "sanar", "sanarflix", "aristo",
            "jj medicina", "eu médico residente", "revisamed",
            "mediccurso", "medprovas", "vr med", "medmentoria",
            "o residente", "yellowbook",
        ],
    }
    config.updated_by = "migration"
    config.save()
```

**ATENÇÃO ao número da migration:** Verificar qual é a última migration existente antes de criar. Atualmente existem: `0001_initial.py`, `0002_initial_configs.py`, `0003_update_config_messages.py`, `0004_rate_limit_configs.py`. A próxima deve ser `0005`.

#### 5. Testes: `tests/test_tools/test_web_search.py` (CRIAR)

```python
"""Tests for web_search tool."""
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
class TestWebSearch:
    async def test_search_returns_formatted_results(self):
        """Verify [W-N] formatting with title, URL, content."""

    async def test_search_excludes_competitor_domains(self):
        """Verify exclude_domains is passed to Tavily."""

    async def test_search_all_results_blocked(self):
        """Verify message when no results after exclusion."""

    async def test_search_tavily_timeout(self):
        """Verify graceful error on timeout."""

    async def test_search_uses_config_competitors(self):
        """Verify competitor list loaded from ConfigService."""

    async def test_search_fallback_hardcoded_competitors(self):
        """Verify fallback to hardcoded list when Config unavailable."""
```

### Project Structure Notes

**Alinhamento com estrutura do projeto:**
- Tool em `workflows/whatsapp/tools/web_search.py` — correto per arquitetura
- Nó em `workflows/whatsapp/nodes/collect_sources.py` — novo nó, segue padrão existente
- Testes em `tests/test_tools/test_web_search.py` — novo diretório de testes
- Migration em `workflows/migrations/0005_*.py` — segue numeração sequencial

**Conflitos detectados:**
- `blocked_competitors` no Config model tem valores incorretos (migration 0002) — corrigido via nova migration

### Informações Técnicas Atuais (Pesquisa Web)

#### Tavily Python SDK (AsyncTavilyClient)

**Versão:** `tavily-python>=0.5` (última estável)

**Import e inicialização:**
```python
from tavily import AsyncTavilyClient
client = AsyncTavilyClient(api_key="tvly-...")
```

**Parâmetros relevantes do `search()`:**

| Parâmetro | Tipo | Default | Valor na Story |
|-----------|------|---------|----------------|
| `query` | str | Obrigatório | Query do LLM |
| `search_depth` | str | `"basic"` | `"advanced"` |
| `topic` | str | `"general"` | `"general"` |
| `max_results` | int | `5` | `8` |
| `include_raw_content` | bool/str | `False` | `True` |
| `exclude_domains` | list[str] | `[]` | Lista de concorrentes |
| `timeout` | float | `60` | `10` (reduzir!) |

**Estrutura da resposta:**
```python
{
    "query": str,
    "results": [
        {
            "title": str,
            "url": str,
            "content": str,           # Resumo
            "raw_content": str | None, # HTML parseado (se include_raw_content)
            "score": float,            # Relevância
        },
        ...
    ],
    "response_time": float,
}
```

**ATENÇÃO:** O `raw_content` pode ser muito longo. Truncar a 800 caracteres antes de enviar ao LLM para evitar estourar o context window.

[Fonte: https://docs.tavily.com/sdk/python/reference]

#### LangGraph ToolNode + tools_condition

```python
from langgraph.prebuilt import ToolNode, tools_condition
```

- `ToolNode(tools)` — executa tools em paralelo por padrão
- `tools_condition(state)` — retorna `"tools"` se AIMessage tem `tool_calls`, senão `"__end__"`
- O `"__end__"` no mapping do conditional edge NÃO é `END` do LangGraph — é só a chave string que mapeia para o próximo nó

### Dependências de Outras Stories

| Dependência | Status | Impacto |
|-------------|--------|---------|
| Story 1.1 (setup base) | done | Models, ConfigService, structlog |
| Story 1.4 (LLM + orquestração) | done | get_model(), orchestrate_llm, graph |
| Story 1.5 (format_response) | done | validate_citations, strip_competitor_citations |
| Story 2.1 (RAG) | backlog | Independente — RAG tool não bloqueia web search |
| Epic 8 (ConfigService hot-reload Redis) | backlog | ConfigService atual busca direto no banco (sem cache Redis) — OK para MVP |

### Regras PROIBIDAS (da Arquitetura)

- **PROIBIDO:** `print()` — usar `structlog` sempre
- **PROIBIDO:** sync I/O — toda I/O deve ser async
- **PROIBIDO:** `import *`
- **PROIBIDO:** camelCase em Python
- **PROIBIDO:** Gerar URLs da memória/treinamento da LLM
- **PROIBIDO:** Citar conteúdo de concorrentes
- **PROIBIDO:** Inventar marcadores `[N]` sem fonte real retornada por tool
- **PROIBIDO:** Tool ABC custom — usar `@tool` do LangChain
- **PROIBIDO:** supabase-py para queries de dados — usar Django ORM

### Naming Conventions

- Arquivos: `snake_case.py`
- Funções: `snake_case()`
- Classes: `PascalCase`
- Constantes: `UPPER_SNAKE_CASE`
- Events structlog: `snake_case`, verbo no passado (`web_search_completed`, `competitor_domain_blocked`)

### References

- [Source: architecture.md — ADR-010: LangGraph + LangChain, linhas 1975-2017 (code pattern web_search)]
- [Source: architecture.md — Competitor Blocking 3 Layers, linhas 2062-2118]
- [Source: architecture.md — Citation Pipeline 4 stages, linhas 1960-1972]
- [Source: architecture.md — External Services Table, linha 2523 (Tavily: $5/mês, timeout 10s)]
- [Source: architecture.md — Enforcement Rules, linhas 2220-2251]
- [Source: epics.md — Epic 2, Story 2.2 acceptance criteria, linhas 596-620]
- [Source: workflows/whatsapp/graph.py — grafo atual sem ToolNode]
- [Source: workflows/whatsapp/nodes/orchestrate_llm.py — model.ainvoke sem bind_tools]
- [Source: workflows/whatsapp/nodes/format_response.py — validate_citations + strip_competitor_citations já existem]
- [Source: workflows/whatsapp/state.py — web_sources, retrieved_sources já definidos como placeholders]
- [Source: workflows/whatsapp/prompts/system.py — regras de citação [N]/[W-N] já existem]
- [Source: workflows/migrations/0002_initial_configs.py — blocked_competitors com valores incorretos]
- [Source: Tavily SDK Reference — https://docs.tavily.com/sdk/python/reference]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- 281 testes passaram, 3 falharam (testes de integração que precisam de credenciais GCP reais — pre-existentes, não relacionados a esta story)
- 44 testes novos/modificados passaram (web_search, collect_sources, format_response footer, graph build)
- Ruff lint: all checks passed

### Completion Notes List

- **Task 1:** Grafo atualizado com ToolNode, collect_sources e conditional edges. Story 2-3 já havia adicionado ToolNode e bind_tools; esta story adicionou collect_sources e o mapping correto de tools_condition ({"tools": "tools", "__end__": "collect_sources"})
- **Task 2:** Tool web_search criada com @tool decorator, AsyncTavilyClient, exclude_domains, [W-N] formatting, truncamento a 800 chars, e error handling graceful (retorna string de erro para o LLM)
- **Task 3:** tavily-python adicionado ao pyproject.toml, TAVILY_API_KEY em .env.example, base.py e test.py, migration 0005 corrige blocked_competitors de ["chatgpt","gemini","copilot"] para domínios reais de concorrentes
- **Task 4:** _build_source_footer() adicionada ao format_response.py, gera rodapé com 📚 Fontes (RAG) e 🌐 Web (web), inserido ANTES do markdown_to_whatsapp
- **Task 5:** 10 testes para web_search (7 tool + 3 blocked_domains), 4 testes para collect_sources, 6 testes adicionados ao format_response (2 footer integration + 4 _build_source_footer unit), 1 teste de grafo (nós tools + collect_sources presentes)

### Change Log

- 2026-03-09: Implementação completa Story 2.2 — web search com Tavily, bloqueio de concorrentes, [W-N] citations, source footer, ToolNode + collect_sources no grafo
- 2026-03-09: Code review adversarial (Claude Opus 4.6) — 7 issues encontrados e corrigidos:
  - HIGH: collect_sources filtrava todas as mensagens (cross-turn leak) → agora filtra apenas turno atual
  - MEDIUM: web_search vazava exceção raw para o LLM → mensagem sanitizada + TimeoutError separado
  - MEDIUM: cost_usd sobrescrito no tool loop → acumula custo entre iterações
  - MEDIUM: bind_tools movido para get_model(tools=...) com guard if tools: (fix do user)
  - LOW: validate_citations usava contagem → agora usa índices reais das fontes
  - LOW: web_search não diferenciava tipo de erro Tavily → TimeoutError separado + error_type no log
  - LOW: Sem teste para ConfigService retornando None → teste adicionado

### File List

**Novos:**
- workflows/whatsapp/tools/web_search.py
- workflows/whatsapp/nodes/collect_sources.py
- workflows/migrations/0005_update_blocked_competitors.py
- tests/test_whatsapp/test_tools/test_web_search.py
- tests/test_whatsapp/test_nodes/test_collect_sources.py

**Modificados:**
- workflows/whatsapp/graph.py
- workflows/whatsapp/tools/__init__.py
- workflows/whatsapp/nodes/format_response.py
- workflows/whatsapp/nodes/orchestrate_llm.py
- workflows/providers/llm.py
- pyproject.toml
- .env.example
- config/settings/base.py
- config/settings/test.py
- tests/test_whatsapp/test_nodes/test_format_response.py
- tests/test_whatsapp/test_nodes/test_format_response_citations.py
- tests/test_graph.py
