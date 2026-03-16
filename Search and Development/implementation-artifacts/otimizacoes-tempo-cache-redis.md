# Otimizações de Tempo - Cache Redis

**Data:** 2026-03-14
**Objetivo:** Reduzir latência de ~19s → ~12-13s (37% redução)
**Estratégia:** Cache Redis para ferramentas externas (RAG + drug_lookup)

---

## 📊 Profiling - Gargalos Identificados

### Breakdown de Latência (3 cenários testados)

| Cenário | Total | orchestrate_llm | tools | overhead |
|---------|-------|-----------------|-------|----------|
| **DROGA + CONTEXTO** | 20.2s | 7.9s (39%) | 8.3s (41%) | 4.0s (20%) |
| **DROGA SEM CONTEXTO** | 21.6s | 12.0s (56%) | 5.4s (25%) | ~4s (19%) |
| **CÁLCULO** | 13.9s | 9.9s (71%) | ~0s (0%) | ~4s (29%) |

### 🎯 Gargalos Principais

1. **orchestrate_llm (LLM API calls): 7-12s** ⚠️ **MAIOR GARGALO**
   - Chamadas à API do Claude (Vertex AI ou Anthropic Direct)
   - Múltiplas chamadas no loop de tools (2-3x por query)

2. **tools (execução de ferramentas): 5-8s** ⚠️ **2º MAIOR GARGALO**
   - RAG: Pinecone API (~3-4s)
   - drug_lookup: PharmaDB API (~2-3s)
   - Web search: Tavily API (~2-3s)

3. **overhead (graph/networking): 3-4s** ⚠️ **20-30% do tempo**
   - LangGraph framework overhead
   - Message serialization entre nós

---

## 🚀 Otimizações Implementadas

### 1. CacheService com Redis

**Arquivo:** `workflows/services/cache_service.py`

**Features:**
- ✅ Graceful degradation (se Redis indisponível, continua sem cache)
- ✅ TTL configurável por namespace
- ✅ Key hashing (SHA-256) para queries longas
- ✅ JSON serialization automática
- ✅ Logging detalhado (cache hit/miss)

**API:**
```python
from workflows.services import cache_service

# Get
value = await cache_service.get("namespace", "key")

# Set com TTL
await cache_service.set("namespace", "key", value, ttl_seconds=3600)

# Invalidate
await cache_service.invalidate("namespace", "key")

# Clear namespace
await cache_service.clear_namespace("namespace")
```

### 2. Cache em rag_medical_search

**Arquivo:** `workflows/whatsapp/tools/rag_medical.py`

**TTL:** 24 horas (respostas médicas mudam raramente)

**Implementação:**
```python
# Check cache first
cached_output = await cache_service.get("rag", query)
if cached_output is not None:
    logger.info("rag_cache_hit", query=query[:80])
    return cached_output

# ... Pinecone query ...

# Cache successful results
if results:
    await cache_service.set("rag", query, output, ttl_seconds=RAG_CACHE_TTL)
```

**Ganho estimado:** ~3-4s por cache hit

### 3. Cache em drug_lookup

**Arquivo:** `workflows/whatsapp/tools/bulas_med.py`

**TTL:** 7 dias (bulas ANVISA são estáveis)

**Implementação:**
```python
# Check cache first
cached_output = await cache_service.get("drug_lookup", drug_name.lower())
if cached_output is not None:
    logger.info("drug_lookup_cache_hit", drug_name=drug_name)
    return cached_output

# ... PharmaDB API call ...

# Cache successful results (skip "not found" errors)
if not any(phrase in output.lower() for phrase in ["não encontrado", "indisponível"]):
    await cache_service.set("drug_lookup", drug_name.lower(), output, ttl_seconds=DRUG_CACHE_TTL)
```

**Ganho estimado:** ~2-3s por cache hit

---

## 📈 Impacto Esperado

### Cenário de Produção

**Premissas:**
- 40% das queries são repetidas (queries comuns: "dose de amoxicilina", "losartana contraindicações")
- Cache hit rate: 40% (conservador)

**Antes do Cache:**
- Tempo médio: 19s
- 100% das queries → API calls

**Depois do Cache (40% hit rate):**
- 60% COLD (sem cache): 19s
- 40% WARM (com cache): ~12s (redução de ~7s)

**Tempo médio ponderado:**
```
(0.6 × 19s) + (0.4 × 12s) = 11.4s + 4.8s = 16.2s
```

**Redução:** 19s → 16.2s (**~15% melhoria**)

**Com 60% hit rate (após warm-up):**
```
(0.4 × 19s) + (0.6 × 12s) = 7.6s + 7.2s = 14.8s
```

**Redução:** 19s → 14.8s (**~22% melhoria**)

---

## 🔧 Configuração

### 1. Instalar redis-py

```bash
pip install -r requirements.txt  # redis>=5.0.0 adicionado
```

### 2. Configurar REDIS_URL

**.env:**
```bash
# Desenvolvimento local
REDIS_URL=redis://localhost:6379

# Produção (Upstash, Cloud Memorystore, etc)
REDIS_URL=redis://user:password@host:port/db
```

### 3. Deploy

**GCP Cloud Run + Cloud Memorystore:**
- Create Cloud Memorystore (Redis) instance
- Configure VPC connector
- Set REDIS_URL env var

**Alternativa (Upstash):**
- Serverless Redis (sem infraestrutura)
- Pay-per-request pricing
- Global replication
- `REDIS_URL=rediss://default:password@region.upstash.io:6379`

---

## 🧪 Testes

### Teste de Performance

```bash
# Requisito: Redis rodando localmente
docker run -d -p 6379:6379 redis:7-alpine

# Rodar benchmark
python scripts/test_cache_performance.py
```

**Output esperado:**
```
⚡ TESTE DE PERFORMANCE - Redis Cache
================================================================================

🔬 TESTE: RAG Medical Search
================================================================================
Query: Qual a dose de amoxicilina para otite média?

❄️  COLD (sem cache):
   Latência: 3842ms
   Tamanho: 2150 bytes

🔥 WARM (com cache):
   Latência: 12ms

📊 GANHO:
   🚀 Speedup: 99.7%
   ⏱️  Tempo economizado: 3830ms

[... mais testes ...]

📊 RESUMO GERAL
================================================================================

Latência média:
  COLD (sem cache): 3250ms
  WARM (com cache): 8ms

Ganho médio:
  Speedup: 99.8%
  Tempo economizado: 3242ms

✅ Cache funcionando perfeitamente! (>90% speedup)
```

---

## 🎯 Próximas Otimizações (Não Implementadas)

### 1. Fix Vertex AI + Prompt Caching (PRIORIDADE #1)
- **Ganho:** ~3s por re-entrada no loop
- **Esforço:** Baixo (debug credenciais GCP)
- **Status:** Vertex AI funciona em produção, apenas local tem problema

### 2. Streaming de Resposta
- **Ganho:** 0s real, mas UX muito melhor
- **Esforço:** Médio (adaptar send_whatsapp)
- **Status:** Backlog

### 3. Parallel Tool Execution (seletivo)
- **Ganho:** ~2-3s em casos raros (2+ tools independentes)
- **Esforço:** Alto (requer análise de dependências)
- **Status:** Backlog

---

## 📝 Referências

- [ADR-013: Haiku Tool Calling Optimization](../planning-artifacts/adr-013-haiku-tool-calling-optimization.md)
- Script de profiling: `scripts/profile_timing.py`
- Script de benchmark cache: `scripts/test_cache_performance.py`
