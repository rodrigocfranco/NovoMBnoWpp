# Story 2.4: Bulas de Medicamentos

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a aluno,
I want consultar informações sobre medicamentos (indicações, dosagens, interações),
so that tenho referência confiável sobre farmacologia durante estudos e plantões.

## Acceptance Criteria

1. **Given** o aluno pergunta "Qual a dose de amoxicilina pediátrica?"
   **When** o LLM decide usar a tool `drug_lookup`
   **Then** a tool busca na base de bulas (full-text search)
   **And** retorna: indicações, posologia, contraindicações, interações medicamentosas
   **And** cita a fonte (bula ANVISA ou base curada Medway)

2. **Given** o medicamento não é encontrado na base
   **When** a tool executa
   **Then** retorna mensagem indicando que o medicamento não foi encontrado
   **And** sugere verificar o nome comercial/genérico

## Tasks / Subtasks

- [x] Task 1: Criar `workflows/whatsapp/tools/drug_lookup.py` com estratégia dual (AC: #1, #2)
  - [x] 1.1 Implementar `drug_lookup` tool com `@tool` decorator do LangChain (`langchain_core.tools`)
  - [x] 1.2 Implementar client PharmaDB (primary): busca em `/v1/produtos/busca?q={name}` → `/v1/bulas/{id}`
  - [x] 1.3 Implementar client Bulário fallback (free): busca em `{BULARIO_API_URL}/pesquisar?nome={name}`
  - [x] 1.4 Implementar lógica de fallback: PharmaDB → Bulário → mensagem de erro
  - [x] 1.5 Formatar retorno com seções: indicações, posologia, contraindicações, interações
  - [x] 1.6 Formatar retorno para medicamento não encontrado com sugestão de nome comercial/genérico
  - [x] 1.7 Implementar tratamento de erro/timeout (3 tentativas por provider, backoff, retorno legível para LLM)
  - [x] 1.8 Logging estruturado via structlog (drug_lookup_executed, drug_not_found, drug_lookup_fallback, etc.)
- [x] Task 2: Configurar variáveis de ambiente (AC: #1)
  - [x] 2.1 Adicionar `PHARMADB_API_KEY` ao `.env.example` e `config/settings/base.py` (vazio = desabilitado, usa fallback direto)
  - [x] 2.2 Adicionar `BULARIO_API_URL` ao `.env.example` e `config/settings/base.py` (URL da instância self-hosted ou bulario.app.br)
- [x] Task 3: Registrar tool no graph (AC: #1)
  - [x] 3.1 `drug_lookup` já importado em `workflows/whatsapp/tools/__init__.py` (pré-existente)
  - [x] 3.2 Já incluído na lista retornada por `get_tools()` — o ToolNode no graph executa automaticamente
- [x] Task 4: Testes unitários (AC: #1, #2)
  - [x] 4.1 Reescrito `tests/test_whatsapp/test_tools/test_drug_lookup.py` (18 testes)
  - [x] 4.2 Testar cenário: PharmaDB encontra medicamento → retorna dados estruturados
  - [x] 4.3 Testar cenário: PharmaDB falha → fallback Bulário encontra → retorna dados
  - [x] 4.4 Testar cenário: ambos providers falham → retorna mensagem legível para LLM
  - [x] 4.5 Testar cenário: medicamento não encontrado em nenhum provider → sugere verificar nome
  - [x] 4.6 Testar cenário: PHARMADB_API_KEY vazio → pula direto para Bulário (sem erro)
  - [x] 4.7 Mockar chamadas httpx (NÃO depender de API real em CI)

## Dev Notes

### Decisão de Implementação: Estratégia Dual com Fallback

A arquitetura define `drug_lookup` como "full-text search" em `workflows/whatsapp/tools/bulas_med.py`. A implementação usa **estratégia dual**: PharmaDB (primary, pago) com fallback gratuito.

**PRIMARY — PharmaDB API (pago, dados estruturados)**
- API REST brasileira com 8.793 bulas estruturadas da ANVISA
- Endpoints: `GET /v1/produtos/busca?q={name}` → `GET /v1/bulas/{id}`
- Retorna JSON estruturado: indicações, posologia, contraindicações, interações, reações adversas
- Pricing: Free (20 req/dia), Starter R$77/mês (5.000 req/mês), Pro R$237/mês (50.000 req/mês)
- URL: https://pharmadb.com.br/
- Auth: API key via header `X-API-Key`
- **Nota:** Gasto pendente de aprovação. Se `PHARMADB_API_KEY` estiver vazio, pula direto para fallback

**FALLBACK — Bulário API (gratuito)**
- Duas opções de fonte (configurável via `BULARIO_API_URL`):
  1. **bulario.app.br** — API de bulas com registro gratuito. Requer API key, documentação em `/docs`
  2. **Self-hosted iuryLandin/bulario-api** — Open-source (MIT), deploy no Cloud Run. GitHub: https://github.com/iuryLandin/bulario-api
- Endpoints: `GET /pesquisar?nome={name}&pagina=1` → retorna lista de medicamentos com `numProcesso`
- `GET /medicamento/{numProcesso}` → detalhes do medicamento
- `GET /bula?id={hash}` → link do PDF da bula (paciente ou profissional)
- **Limitação:** Retorna metadados + link PDF (não texto estruturado como PharmaDB). Para texto, seria necessário parsing do PDF — mas os metadados (nome, princípio ativo, categoria, empresa) já são úteis para o LLM
- **Limitação do self-hosted:** Depende de scraping da ANVISA — pode quebrar se o portal mudar

**Lógica de fallback no código:**
```python
async def _search_pharmadb(drug_name: str) -> str | None:
    """Primary: PharmaDB structured API."""
    if not getattr(settings, "PHARMADB_API_KEY", None):
        return None  # skip if no key configured
    # ... httpx call to PharmaDB ...

async def _search_bulario(drug_name: str) -> str | None:
    """Fallback: Bulário API (free)."""
    bulario_url = getattr(settings, "BULARIO_API_URL", None)
    if not bulario_url:
        return None  # skip if not configured
    # ... httpx call to Bulário ...

@tool
async def drug_lookup(drug_name: str) -> str:
    # Try PharmaDB first
    result = await _search_pharmadb(drug_name)
    if result:
        return result
    # Fallback to Bulário
    logger.info("drug_lookup_fallback", provider="bulario", drug_name=drug_name)
    result = await _search_bulario(drug_name)
    if result:
        return result
    # Both failed
    return f"Medicamento '{drug_name}' não encontrado. Verifique o nome comercial ou genérico."
```

**Para o dev agent:** Implementar AMBOS os providers. PharmaDB é primary (melhor dado), Bulário é fallback (gratuito). Se nenhum env var estiver configurado, a tool retorna mensagem de "serviço não configurado" (graceful degradation). Cada provider em função separada (`_search_pharmadb`, `_search_bulario`) para isolamento e testabilidade.

### Padrão de Implementação (copiar de verify_paper.py / rag_medical.py)

```python
# workflows/whatsapp/tools/bulas_med.py
from langchain_core.tools import tool
import structlog

logger = structlog.get_logger(__name__)

@tool
async def drug_lookup(drug_name: str) -> str:
    """Consulta bula de medicamento com posologia, contraindicações e interações.
    Use quando o aluno pergunta sobre um medicamento específico — dose,
    indicação, contraindicação, interação medicamentosa ou efeito colateral.

    Args:
        drug_name: Nome do medicamento (comercial ou genérico).
    """
    # Implementação aqui — Opção A (Pinecone) ou Opção B (PharmaDB)
    ...
```

### Padrões Obrigatórios (extraídos das stories anteriores)

- **Decorator:** `@tool` do `langchain_core.tools` (NUNCA Tool ABC custom)
- **Async:** A tool DEVE ser `async def` — toda I/O é async
- **HTTP client:** `httpx.AsyncClient` para chamadas externas (PharmaDB + Bulário)
- **Docstring:** Usada pelo LLM para decidir quando chamar — deve ser clara e direta
- **Naming:** `drug_lookup` (snake_case, conforme arquitetura)
- **Arquivo:** `workflows/whatsapp/tools/bulas_med.py` (conforme árvore de arquivos da arquitetura)
- **Imports:** Explícitos, nunca `import *`. Ordem: stdlib > third-party > local
- **Logging:** `structlog.get_logger()` para logs JSON. NUNCA `print()`
- **Erros:** Retornar string de erro legível para o LLM (a tool NÃO levanta exceções — retorna texto de erro)
- **Retorno:** Sempre `str` — formatado para consumo do LLM com markdown leve

### Integração com o Graph (NENHUMA mudança necessária no graph.py)

- O graph.py já usa `ToolNode(get_tools())` — basta adicionar `drug_lookup` à lista em `get_tools()`
- O ToolNode executa TODAS as tools em paralelo por padrão
- A tool NÃO modifica o state diretamente — retorna string que o LLM consome
- O LLM decide SE e QUANDO chamar a tool com base na docstring
- A tool drug_lookup alimenta citações Gold `[N]` (se dados vierem do Pinecone/Medway) — o format_response já trata

### Citações e Fontes

- PharmaDB indexa bulas oficiais da ANVISA — atribuir como "Bula ANVISA" na citação
- Bulário fallback também vem da ANVISA — mesma atribuição
- Formato de citação no retorno: incluir fonte no texto para o LLM citar
- Exemplo PharmaDB: `"📋 Fonte: Bula ANVISA — Amoxicilina Tri-hidratada (via PharmaDB)"`
- Exemplo Bulário: `"📋 Fonte: Bula ANVISA — Amoxicilina (Bulário Eletrônico)"`

### Tratamento de Erro e Resiliência

Cada provider tem retry independente. Se o primary (PharmaDB) falha após 3 tentativas, o fallback (Bulário) é acionado — também com 3 tentativas. Só se ambos falharem a tool retorna erro.

```python
# Padrão de retry por provider (igual a verify_paper.py):
async def _request_with_retry(client: httpx.AsyncClient, url: str, params: dict, provider: str) -> httpx.Response | None:
    for attempt in range(3):
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            if attempt == 2:
                logger.warning("drug_provider_unavailable", provider=provider, error=str(e))
                return None
            await asyncio.sleep(1.0 * (attempt + 1))
    return None
```

**Timeouts por provider:**
- PharmaDB: 8s (API REST estruturada, resposta rápida)
- Bulário: 10s (pode ser mais lento se self-hosted ou scraping ANVISA)

### Formatação do Retorno (exemplo)

```
💊 **Amoxicilina** (Genérico)

**Indicações:** Infecções bacterianas do trato respiratório superior e inferior, otite média, sinusite, infecções urinárias, infecções de pele.

**Posologia:**
- Adultos: 500mg a cada 8h ou 875mg a cada 12h
- Pediátrico: 25-50mg/kg/dia divididos em 3 doses (max 3g/dia)
- Neonatos: 30mg/kg/dia divididos em 2 doses

**Contraindicações:** Hipersensibilidade a penicilinas. Cautela em alérgicos a cefalosporinas (reação cruzada 1-10%).

**Interações Medicamentosas:**
- Metotrexato: reduz excreção renal (↑ toxicidade)
- Varfarina: pode ↑ INR
- Alopurinol: ↑ risco de rash cutâneo
- Contraceptivos orais: possível ↓ eficácia

📋 Fonte: Bula ANVISA — Amoxicilina Tri-hidratada
```

### Testes — Padrão do Projeto

- Framework: `pytest` + `pytest-asyncio`
- Diretório: `tests/test_whatsapp/test_tools/test_bulas_med.py`
- Mockar chamadas externas (httpx ou Pinecone) — CI deve rodar offline
- Testar 3 cenários: encontrado, não encontrado, erro/timeout
- Usar `@pytest.mark.asyncio` para testes async
- NÃO usar `@pytest.mark.django_db` (tool não acessa banco diretamente)

### Inteligência da Story 2-3 (Learnings)

De story 2-3 (`verify_medical_paper`):
- **bind_tools() em RunnableWithFallbacks** perdia o fallback — já corrigido via `get_model(tools=)` que faz bind em primary E fallback antes de `with_fallbacks()`. NÃO precisa mexer nisso de novo — está resolvido
- **Exception handling:** Usar `httpx.RequestError` (base class) em vez de exceções específicas
- **Registro da tool:** Adicionar import em `tools/__init__.py` e incluir em `get_tools()`. O `orchestrate_llm` já usa `get_model(tools=get_tools())` e o graph já tem ToolNode
- **Mock pattern:** Nos testes, mockar `httpx.AsyncClient` via `unittest.mock` (o projeto NÃO usa `respx` nem `pytest-httpx`)
- **Testes existentes:** Suite completa tem 287+ testes. Rodar full suite para verificar zero regressões
- **bind_tools mocks:** Se algum teste de graph/orchestrate_llm falhar, verificar se `bind_tools` está mockado corretamente (já foi corrigido em 2-3)

### Project Structure Notes

- **Arquivo CRIA:** `workflows/whatsapp/tools/bulas_med.py` (conforme árvore da arquitetura)
- **Arquivo CRIA:** `tests/test_whatsapp/test_tools/test_bulas_med.py`
- **Arquivo MODIFICA:** `workflows/whatsapp/tools/__init__.py` (adicionar import + get_tools)
- **Arquivo MODIFICA:** `.env.example` (adicionar PHARMADB_API_KEY + BULARIO_API_URL)
- **Arquivo MODIFICA:** `config/settings/base.py` (adicionar PHARMADB_API_KEY + BULARIO_API_URL)
- **Arquivo NÃO MODIFICA:** `workflows/whatsapp/graph.py` (ToolNode já é dinâmico via get_tools())
- **Arquivo NÃO MODIFICA:** `workflows/whatsapp/nodes/orchestrate_llm.py` (já usa get_tools())
- **Arquivo NÃO MODIFICA:** `workflows/models.py` (esta story não cria models novos)
- **Arquivo NÃO MODIFICA:** `workflows/whatsapp/state.py` (nenhum campo novo necessário)

### Dependências entre Stories

- **Depende de:** Story 1.4 (orchestrate_llm + ToolNode + get_model(tools=) devem existir) — DONE
- **Não depende de:** Stories 2.1, 2.2, 2.3 (tools são independentes entre si — esta story usa APIs externas, não Pinecone)
- **Story 2.6 (orquestração)** garante execução paralela com demais tools, mas ToolNode já faz isso por padrão — DONE

### References

- [Source: architecture.md#Tool Definition Pattern] — @tool decorator, async, snake_case
- [Source: architecture.md#Source Tree] — `workflows/whatsapp/tools/bulas_med.py`
- [Source: architecture.md#External Services] — Timeouts e retries por serviço externo
- [Source: architecture.md#Citation Tiers] — Gold `[N]` para conteúdo curado (bulas ANVISA)
- [Source: architecture.md#Enforcement Rules] — @tool decorator obrigatório, docstring obrigatória
- [Source: epics.md#Story 2.4] — Acceptance criteria
- [Source: story 2-3 Dev Notes] — bind_tools fix, exception handling, mock patterns
- [PharmaDB API](https://pharmadb.com.br/) — Primary: API REST de bulas brasileiras (pago, JSON estruturado)
- [PharmaDB Bulas](https://pharmadb.com.br/bulas) — Documentação dos endpoints de bulas
- [iuryLandin/bulario-api](https://github.com/iuryLandin/bulario-api) — Fallback: Open-source (MIT), self-hostable no Cloud Run
- [bulario.app.br](https://bulario.app.br/) — Fallback alternativo: API de bulas com registro gratuito
- [ANVISA Bulário Eletrônico](https://consultas.anvisa.gov.br/#/bulario/) — Fonte oficial dos dados (sem API REST pública)

## Change Log

- 2026-03-09: Implementação completa da tool drug_lookup com estratégia dual PharmaDB + Bulário. Substituiu implementação anterior baseada em Django ORM (modelo Drug) por chamadas a APIs externas com fallback, conforme especificação da story.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Implementação anterior usava Django ORM (`Drug.objects.filter`), reescrita para APIs externas conforme story spec
- O `__init__.py` já importava `drug_lookup` de `drug_lookup.py` — mantido nome do módulo (story sugeria `bulas_med.py` mas sistema já referenciava `drug_lookup`)
- 3 testes de integração pré-existentes falham por falta de credenciais GCP/Anthropic (não são regressão desta story)

### Completion Notes List

- ✅ Task 1: `drug_lookup.py` reescrito — @tool async, httpx.AsyncClient, _search_pharmadb + _search_bulario + _request_with_retry, logging structlog
- ✅ Task 2: PHARMADB_API_KEY e BULARIO_API_URL adicionados ao .env.example e config/settings/base.py
- ✅ Task 3: Registro já existente — import e get_tools() já incluíam drug_lookup
- ✅ Task 4: 18 testes criados — 5 PharmaDB, 5 Bulário, 8 integração/fallback. Todos mockam httpx. 18/18 passing.
- ✅ Full suite: 439 passed, 3 failed (pré-existentes — credenciais GCP/Anthropic ausentes no ambiente local)

### File List

- `workflows/whatsapp/tools/drug_lookup.py` (MODIFIED — reescrito de Django ORM para APIs externas)
- `tests/test_whatsapp/test_tools/test_drug_lookup.py` (MODIFIED — reescrito para novos cenários)
- `.env.example` (MODIFIED — adicionado PHARMADB_API_KEY + BULARIO_API_URL)
- `config/settings/base.py` (MODIFIED — adicionado PHARMADB_API_KEY + BULARIO_API_URL)
