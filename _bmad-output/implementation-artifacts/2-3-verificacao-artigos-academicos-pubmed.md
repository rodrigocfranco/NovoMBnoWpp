# Story 2.3: Verificação de Artigos Acadêmicos via PubMed

Status: done

## Story

As a aluno,
I want que artigos citados sejam verificados como reais,
so that não recebo referências inventadas (alucinações do LLM).

## Acceptance Criteria

1. **Given** o aluno menciona um estudo ou artigo específico (ex: "o estudo PARADIGM-HF")
   **When** o LLM decide usar a tool `verify_medical_paper`
   **Then** a tool busca no PubMed E-utilities API (`esearch.fcgi` + `esummary.fcgi`)
   **And** busca por título e autores (quando disponíveis)

2. **Given** o artigo existe no PubMed
   **When** a verificação retorna resultado
   **Then** retorna dados verificados: título completo, autores, journal, DOI, ano de publicação
   **And** o LLM pode citar o artigo com confiança

3. **Given** o artigo NÃO existe no PubMed
   **When** a verificação retorna zero resultados
   **Then** retorna "⚠️ ARTIGO NÃO ENCONTRADO no PubMed. NÃO cite este estudo."
   **And** o LLM não cita o artigo na resposta

4. **Given** o PubMed API está indisponível (timeout 5s, 2 retries)
   **When** a verificação falha
   **Then** retorna mensagem indicando que a verificação não foi possível
   **And** o LLM pode citar com ressalva ("verificação indisponível no momento")

## Tasks / Subtasks

- [x] Task 1: Criar `workflows/whatsapp/tools/verify_paper.py` (AC: #1, #2, #3, #4)
  - [x] 1.1 Implementar `verify_medical_paper` tool com `@tool` decorator do LangChain
  - [x] 1.2 Implementar chamada `esearch.fcgi` via httpx async (busca por título + autores)
  - [x] 1.3 Implementar chamada `esummary.fcgi` via httpx async (extração de metadados)
  - [x] 1.4 Formatar retorno com dados verificados (PMID, título, journal, data, URL PubMed)
  - [x] 1.5 Formatar retorno negativo ("⚠️ ARTIGO NÃO ENCONTRADO no PubMed. NÃO cite este estudo.")
  - [x] 1.6 Implementar tratamento de erro/timeout com mensagem de ressalva
- [x] Task 2: Configurar API key e parâmetros no .env (AC: #1)
  - [x] 2.1 Adicionar `NCBI_API_KEY` ao `.env.example` e ao settings
  - [x] 2.2 Adicionar `NCBI_EMAIL` ao `.env.example` (recomendado pela NCBI)
- [x] Task 3: Registrar tool no graph (AC: #1)
  - [x] 3.1 Adicionar `verify_medical_paper` à lista de tools no `build_whatsapp_graph()` / ToolNode
  - [x] 3.2 Garantir que o ToolNode pode executar a tool em paralelo com as demais
- [x] Task 4: Testes unitários (AC: #1, #2, #3, #4)
  - [x] 4.1 Criar `tests/test_whatsapp/test_tools/test_verify_paper.py`
  - [x] 4.2 Testar cenário: artigo encontrado → retorna dados verificados
  - [x] 4.3 Testar cenário: artigo não encontrado → retorna aviso
  - [x] 4.4 Testar cenário: API timeout/erro → retorna mensagem de ressalva
  - [x] 4.5 Mockar chamadas httpx (não depender de API real em CI)

## Dev Notes

### Implementação de Referência (Architecture Doc)

O arquivo da arquitetura já contém o código de referência completo. Seguir exatamente este padrão:

```python
# workflows/whatsapp/tools/verify_paper.py
from langchain_core.tools import tool
import httpx

PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

@tool
async def verify_medical_paper(title: str, authors: str = "") -> str:
    """Verifica se um artigo médico existe realmente no PubMed.
    Use ANTES de citar qualquer artigo/estudo mencionado pelo usuário.

    Args:
        title: Título do artigo ou estudo.
        authors: Autores (opcional, melhora precisão).
    """
    # ... implementação conforme architecture.md
```

### PubMed E-utilities API — Especificações Técnicas

- **Base URL:** `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`
- **Endpoints usados:**
  - `esearch.fcgi` — busca por termo, retorna lista de PMIDs
  - `esummary.fcgi` — retorna metadados (título, autores, journal, DOI, data) dado PMID
- **Parâmetros esearch:** `db=pubmed`, `term="{title} {authors}"`, `retmode=json`, `retmax=3`
- **Parâmetros esummary:** `db=pubmed`, `id={pmids}`, `retmode=json`
- **Rate limits:**
  - Sem API key: max 3 requests/segundo por IP
  - Com API key (`api_key=...`): max 10 requests/segundo
  - Param: `api_key=XXXXX` na query string ou `tool=app_name&email=user@email.com`
- **Recomendação NCBI:** Sempre enviar `api_key` + `tool` + `email` nos requests
- **Timeout:** 5s (definido na arquitetura)
- **Retries:** 2 (definido na arquitetura, via tratamento de exceção no próprio tool — NÃO via LangGraph RetryPolicy pois é tool, não nó)
- **API é gratuita** e sem necessidade de autenticação (API key é opcional mas recomendada para rate limit maior)

### Padrões Obrigatórios

- **Decorator:** `@tool` do `langchain_core.tools` (NUNCA Tool ABC custom)
- **Async:** A tool DEVE ser `async def` — toda I/O é async
- **HTTP client:** Usar `httpx.AsyncClient` (já é dependência do projeto)
- **Docstring:** A docstring da tool É usada pelo LLM para decidir quando chamar — deve ser clara e direta
- **Naming:** `verify_medical_paper` (snake_case, conforme arquitetura)
- **Arquivo:** `workflows/whatsapp/tools/verify_paper.py` (conforme árvore de arquivos da arquitetura)
- **Imports:** Explícitos, nunca `import *`. Ordem: stdlib → third-party → local
- **Logging:** `structlog.get_logger()` para logs (JSON, com PII sanitizado). NUNCA `print()`
- **Erros:** Retornar string de erro legível para o LLM (a tool não deve levantar exceções — o LLM precisa da mensagem de erro como texto para decidir o que fazer)

### Integração com o Graph

- A tool é registrada na lista de tools passada ao `orchestrate_llm` node / ToolNode
- O ToolNode executa todas as tools em paralelo por padrão
- A tool NÃO adiciona nada ao state diretamente — ela retorna string que o LLM consome
- O LLM decide SE e QUANDO chamar a tool com base na docstring
- Diferente de `rag_medical_search` e `web_search`, esta tool NÃO alimenta `retrieved_sources` nem `web_sources` — ela apenas valida existência

### Tratamento de Erro e Resiliência

```python
# Padrão de retry dentro da tool (não usa RetryPolicy do LangGraph):
async with httpx.AsyncClient(timeout=5.0) as client:
    for attempt in range(3):  # 1 tentativa + 2 retries
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            break
        except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
            if attempt == 2:
                logger.warning("pubmed_api_unavailable", error=str(e))
                return "⚠️ Verificação de artigo indisponível no momento. Cite com ressalva."
            await asyncio.sleep(1.0 * (attempt + 1))  # backoff simples
```

### Testes — Padrão do Projeto

- Framework: `pytest` + `pytest-asyncio`
- Diretório: `tests/test_whatsapp/test_tools/test_verify_paper.py`
- Mockar `httpx.AsyncClient` via `respx` ou `pytest-httpx` (verificar qual já está no projeto)
- Não depender de API real em testes (CI deve rodar offline)
- Testar os 3 cenários: encontrado, não encontrado, erro/timeout
- Usar `@pytest.mark.asyncio` para testes async

### API Key como Variável de Ambiente

```
# .env.example (adicionar):
NCBI_API_KEY=           # Opcional: PubMed E-utilities API key (aumenta rate limit de 3 para 10 req/s)
NCBI_EMAIL=             # Recomendado pela NCBI para identificação
```

No código, carregar via `django.conf.settings`:

```python
from django.conf import settings

params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": 3}
if api_key := getattr(settings, "NCBI_API_KEY", None):
    params["api_key"] = api_key
```

### Project Structure Notes

- Arquivo cria: `workflows/whatsapp/tools/verify_paper.py` (conforme árvore da arquitetura)
- Arquivo cria: `tests/test_whatsapp/test_tools/test_verify_paper.py`
- Arquivo modifica: `.env.example` (adicionar NCBI_API_KEY e NCBI_EMAIL)
- Arquivo modifica: `config/settings/base.py` (adicionar NCBI_API_KEY e NCBI_EMAIL)
- Arquivo modifica: `workflows/whatsapp/graph.py` ou equivalente (registrar tool no ToolNode)
- Arquivo NÃO modifica: `workflows/models.py` (esta story não cria models)
- Alinhamento: Segue exatamente a estrutura de arquivos definida na arquitetura (seção 8.1)

### Dependências entre Stories

- **Depende de:** Story 1.4 (orchestrate_llm + ToolNode devem existir para registrar a tool)
- **Não depende de:** Stories 2.1 e 2.2 (tools são independentes entre si, podem ser criadas em qualquer ordem)
- **Story 2.6 (orquestração)** eventualmente garante que esta tool funciona em paralelo com as demais, mas o ToolNode já faz isso por padrão

### References

- [Source: architecture.md#Verify Medical Paper Tool] — Código de referência completo
- [Source: architecture.md#External Services] — PubMed timeout=5s, retries=2x
- [Source: architecture.md#Enforcement Rules] — @tool decorator, async, snake_case
- [Source: architecture.md#Source Tree] — `workflows/whatsapp/tools/verify_paper.py`
- [Source: epics.md#Story 2.3] — Acceptance criteria completos
- [PubMed E-utilities docs](https://www.ncbi.nlm.nih.gov/books/NBK25499/) — API reference
- [NCBI API Keys](https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/) — Rate limits com/sem API key

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Testes GREEN: 6/6 passed (verify_paper) + 263/263 full suite (zero regressions)
- Ruff lint: 0 errors após auto-fix
- Mock fix: `AsyncMock.bind_tools` retorna coroutine — corrigido com `MagicMock(return_value=mock_model)` em test_graph.py e test_orchestrate_llm.py

### Completion Notes List

- ✅ Task 1: `verify_medical_paper` tool implementada com `@tool` decorator, `esearch.fcgi` + `esummary.fcgi`, retorno formatado com PMID/título/autores/journal/DOI/URL, aviso de "NÃO ENCONTRADO", e tratamento de erro com retry (3 tentativas, backoff simples)
- ✅ Task 2: `NCBI_API_KEY` e `NCBI_EMAIL` adicionados ao `.env.example` e `config/settings/base.py`
- ✅ Task 3: Tool registrada via `get_tools()` em `tools/__init__.py`, `model.bind_tools()` no `orchestrate_llm`, `ToolNode` + `tools_condition` no graph com routing condicional
- ✅ Task 4: 6 testes unitários cobrindo: artigo encontrado (dados verificados), busca por título+autores, artigo não encontrado (aviso), timeout, erro HTTP, e retries (3 tentativas confirmadas). Mocks via `unittest.mock` (httpx.AsyncClient mockado, sem dependência de API real)
- ✅ Testes de regressão: mocks existentes em `test_graph.py` e `test_orchestrate_llm.py` atualizados para suportar `bind_tools`

### File List

- `workflows/whatsapp/tools/verify_paper.py` (CRIADO) — Tool verify_medical_paper
- `workflows/whatsapp/tools/__init__.py` (MODIFICADO) — Registra verify_medical_paper em get_tools()
- `workflows/whatsapp/nodes/orchestrate_llm.py` (MODIFICADO) — Usa get_model(tools=get_tools()) preservando fallback
- `workflows/whatsapp/graph.py` (MODIFICADO) — Adiciona ToolNode + tools_condition
- `config/settings/base.py` (MODIFICADO) — Adiciona NCBI_API_KEY e NCBI_EMAIL
- `.env.example` (MODIFICADO) — Adiciona NCBI_API_KEY e NCBI_EMAIL
- `tests/test_whatsapp/test_tools/__init__.py` (CRIADO) — Package init
- `tests/test_whatsapp/test_tools/test_verify_paper.py` (CRIADO) — 6 testes unitários
- `tests/test_graph.py` (MODIFICADO) — Mock bind_tools para compatibilidade
- `tests/test_whatsapp/test_nodes/test_orchestrate_llm.py` (MODIFICADO) — Mock bind_tools para compatibilidade
- `workflows/providers/llm.py` (MODIFICADO) — [Review] get_model aceita tools= e faz bind em primary+fallback
- `tests/test_whatsapp/test_nodes/test_orchestrate_llm_tools.py` (MODIFICADO) — [Review] Mocks adaptados para get_model(tools=)

## Senior Developer Review (AI)

**Reviewer:** Claude Opus 4.6 (adversarial code review)
**Date:** 2026-03-09
**Outcome:** Approved (com correções aplicadas)

### Findings Corrigidos

| # | Severidade | Descrição | Status |
|---|-----------|-----------|--------|
| 1 | HIGH | `bind_tools()` em `RunnableWithFallbacks` perdia o fallback LLM — movido para `get_model(tools=)` que faz bind em primary E fallback antes de `with_fallbacks()` | FIXED |
| 2 | MEDIUM | `httpx.ConnectError`/`NetworkError` não eram capturados — alterado para `httpx.RequestError` (base class) | FIXED |
| 3 | MEDIUM | Parâmetros `email`/`tool` NCBI ausentes no request esummary | FIXED |
| 4 | LOW | Texto AC#3 com adição editorial ("pode ser alucinação do LLM") | ACCEPTED (útil) |
| 5 | LOW | DOI exibido com prefixo "doi: " redundante — adicionado `.removeprefix("doi: ")` | FIXED |
| 6 | LOW | Faltava teste para busca só por título (sem autores) | FIXED |
| 7 | LOW | Faltava teste para retry do esummary | FIXED |

### Test Results Post-Review

- verify_paper: 8/8 passed (6 originais + 2 novos)
- Full suite: 287/293 passed (6 falhas pré-existentes de stories 2-1/2-2 in-progress)
- Zero regressões das correções do review

## Change Log

- 2026-03-09: Story 2.3 implementada — verify_medical_paper tool (PubMed E-utilities), registro no ToolNode/graph, testes unitários (6), configuração NCBI env vars
- 2026-03-09: [Review] Corrigidos 6/7 findings — fallback LLM preservado via get_model(tools=), exception handling ampliado (RequestError), parâmetros NCBI consistentes, DOI limpo, +2 testes
