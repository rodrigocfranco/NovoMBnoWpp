# Pipeline de Correções v1 — Otimização de Tools, Tempo e Custo

**Data:** 2026-03-13
**Origem:** Teste real do pipeline com `scripts/test_pipeline.py`
**Pergunta teste:** "Qual a dose de amoxicilina para otite média?"
**Resultado baseline:** 31 segundos, $0.04, 3 tools chamadas em paralelo

---

## Findings do Teste

### F1: drug_lookup retornou "não encontrado" (APIs não configuradas)
- **Causa:** `PHARMADB_API_KEY` e `BULARIO_API_URL` não existem no `.env`
- **Impacto:** Tool chamada inutilmente — gasta tempo e tokens sem retorno
- **Arquivo:** `workflows/whatsapp/tools/bulas_med.py`

### F2: 3 tools chamadas simultaneamente (sem prioridade)
- **Causa:** O prompt diz "SEMPRE busque no RAG antes" e "use web quando RAG não tiver", mas o LLM ignora a sequência e chama tudo em paralelo
- **Impacto:** Acumula resultados desnecessários → 2a chamada LLM com input enorme
- **Arquivo:** `workflows/whatsapp/prompts/system.py`

### F3: web_search retorna dados excessivos
- **Causa:** `search_depth="advanced"` (lento), `max_results=8` (excessivo), `include_raw_content=True` (~6400 chars)
- **Impacto:** +5-10s no Tavily, +2000 tokens no input da 2a chamada LLM
- **Arquivo:** `workflows/whatsapp/tools/web_search.py`

### F4: Tool descriptions verbosas gastam tokens em TODA chamada
- **Causa:** `medical_calculator` lista 10 calculadoras com todos os parâmetros na docstring
- **Impacto:** ~1500 tokens extras enviados em CADA chamada ao LLM (são pelo menos 2 chamadas)
- **Arquivo:** `workflows/whatsapp/tools/calculators.py`

### F5: drug_lookup não faz fail-fast quando sem configuração
- **Causa:** Quando ambas APIs não estão configuradas, a tool ainda executa toda a lógica, chama `_get_bulas_timeout()` via ConfigService, etc., antes de retornar "não encontrado"
- **Impacto:** Overhead desnecessário + resposta confusa para o LLM ("não encontrado" quando na verdade é "não configurado")
- **Arquivo:** `workflows/whatsapp/tools/bulas_med.py`

---

## Correções Planejadas

### C1: Configurar APIs do drug_lookup
- **Prioridade:** ALTA — sem isso a tool é inútil
- **Ação:** Pesquisar e configurar pelo menos uma API de bulas (Bulário ANVISA é gratuito)
- **Arquivo:** `.env` + `config/settings/base.py`
- **Variáveis:** `BULARIO_API_URL` (gratuito) e/ou `PHARMADB_API_KEY` (pago)

### C2: Prompt — estratégia sequencial de tools
- **Prioridade:** ALTA — maior impacto em tempo e custo
- **Ação:** Reescrever seção "Uso de Ferramentas" com prioridade explícita:
  1. Perguntas sobre MEDICAMENTOS → `drug_lookup` primeiro → RAG → web
  2. Perguntas MÉDICAS gerais → `rag_medical_search` primeiro → web se insuficiente
  3. Cálculos → `medical_calculator`
  4. Verificação de artigos → `verify_medical_paper`
  - Instrução explícita: "NÃO chame múltiplas ferramentas de busca simultaneamente"
- **Arquivo:** `workflows/whatsapp/prompts/system.py`

### C3: web_search — reduzir volume
- **Prioridade:** ALTA — reduz tempo E custo
- **Ação:**
  - `search_depth="basic"` (de "advanced") — 3-5x mais rápido
  - `max_results=4` (de 8) — metade dos tokens
  - `include_raw_content=False` (usar `content` resumido) — reduz ~70% dos tokens
  - `MAX_CONTENT_LENGTH=400` (de 800) — limita texto por resultado
- **Arquivo:** `workflows/whatsapp/tools/web_search.py`

### C4: medical_calculator — compactar descrição
- **Prioridade:** MÉDIA — economiza ~1000 tokens por chamada
- **Ação:** Mover a lista detalhada de calculadoras do docstring para uma tabela compacta
  - Antes: lista cada calculadora com todos os parâmetros (~50 linhas)
  - Depois: lista nomes em uma linha, parâmetros detalhados ficam na implementação
- **Arquivo:** `workflows/whatsapp/tools/calculators.py`

### C5: drug_lookup — fail-fast quando sem configuração
- **Prioridade:** MÉDIA — evita chamada inútil
- **Ação:** No início do `_drug_lookup_impl()`, verificar se pelo menos uma API está configurada. Se nenhuma estiver, retornar imediatamente mensagem informativa diferente: "Consulta de bulas não disponível no momento (nenhum provedor configurado)."
- **Arquivo:** `workflows/whatsapp/tools/bulas_med.py`

---

## Metas após Correções

| Métrica | Baseline (atual) | Meta |
|---|---|---|
| Tempo total | 31s | < 15s |
| Custo por resposta | $0.04 | < $0.02 |
| Tools por pergunta simples | 3 (paralelo) | 1-2 (sequencial) |
| Tokens input (2a chamada) | ~7800 | < 4000 |

---

## Como Testar

```bash
# Teste rápido (mesma pergunta do baseline)
uv run python scripts/test_pipeline.py "Qual a dose de amoxicilina para otite média?"

# Teste pergunta médica geral (deve usar só RAG)
uv run python scripts/test_pipeline.py "O que é síndrome nefrótica?"

# Teste calculadora (deve usar só medical_calculator)
uv run python scripts/test_pipeline.py "Calcule o CHA2DS2-VASc: homem, 72 anos, hipertensão, diabetes"

# Teste multi-turno (modo interativo)
uv run python scripts/test_pipeline.py
```
