# 🧪 Instruções para Teste Local - Otimizações Tool Calling

**Data:** 2026-03-14
**Objetivo:** Validar FASES 1+2+3 localmente antes de deploy

---

## ✅ Pré-requisitos

### 1. Credenciais Configuradas

Verifique se tem as seguintes variáveis no `.env`:

```bash
# LLM Provider (pelo menos uma)
ANTHROPIC_API_KEY=sk-ant-...        # API direta Anthropic
# OU
GCP_CREDENTIALS={"type": "service_account", ...}  # Vertex AI

# Tools (necessárias para testes completos)
TAVILY_API_KEY=tvly-...             # web_search
PHARMADB_API_KEY=...                # drug_lookup (opcional, pode falhar gracefully)

# Database (PostgreSQL para checkpointer)
DATABASE_URL=postgresql://...

# WhatsApp (não necessário para este teste)
# WHATSAPP_TOKEN=...
# WHATSAPP_VERIFY_TOKEN=...
```

### 2. Ambiente Python Ativo

```bash
# Ativar virtualenv
source .venv/bin/activate  # ou .venv/Scripts/activate no Windows

# Verificar versão Python
python --version  # deve ser 3.12+
```

### 3. Dependências Instaladas

```bash
# Se ainda não instalou
pip install -r requirements.txt
```

---

## 🚀 Passo a Passo para Executar Testes

### Passo 1: Verificar Credenciais

```bash
# Ver se .env tem as keys necessárias
cat .env | grep -E "(ANTHROPIC_API_KEY|GCP_CREDENTIALS|TAVILY_API_KEY)"
```

**O que esperar:**
- Pelo menos `ANTHROPIC_API_KEY` ou `GCP_CREDENTIALS` deve estar presente
- `TAVILY_API_KEY` é necessário para web_search funcionar

**Se faltar alguma credencial:**
- Testes que dependem da tool faltante vão falhar, mas outros funcionarão
- Exemplo: sem `PHARMADB_API_KEY`, drug_lookup retorna erro mas não quebra o teste

---

### Passo 2: Rodar Script de Teste

```bash
# Dar permissão de execução
chmod +x scripts/test_tool_calling.py

# Executar testes
python scripts/test_tool_calling.py
```

**O que você verá:**

```
════════════════════════════════════════════════════════════════════════════════
              🧪 TESTE DE TOOL CALLING - FASES 1+2+3
════════════════════════════════════════════════════════════════════════════════

ℹ️  Testando otimizações de tool calling com queries reais
ℹ️  Baseline: $0.075, ~24s, 5 tools (drug_lookup + RAG×2 + web×2)

ℹ️  Executando teste 1/5...

════════════════════════════════════════════════════════════════════════════════
                    TESTE: DROGA + CONTEXTO CLÍNICO → RAG
════════════════════════════════════════════════════════════════════════════════

📝 Query: Qual a dose de amoxicilina para otite média?
🎯 Esperado: rag_medical_search (1 tool)
────────────────────────────────────────────────────────────────────────────────

[... execução do teste ...]

════════════════════════════════════════════════════════════════════════════════
📊 RESULTADOS
════════════════════════════════════════════════════════════════════════════════
⏱️  Tempo: 18.45s
💰 Custo: $0.0234
🔧 Provider: vertex_ai
🛠️  Tools chamadas: 1
   Sequência: rag_medical_search
   Únicas: rag_medical_search

════════════════════════════════════════════════════════════════════════════════
🔍 VALIDAÇÃO
════════════════════════════════════════════════════════════════════════════════
✅ Correto: Tools esperadas foram chamadas (rag_medical_search)
✅ Sem redundância excessiva (1 calls)
✅ Custo reduzido: 68.8% menor que baseline ($0.075)
✅ Tempo reduzido: 23.1% mais rápido que baseline (24.0s)

────────────────────────────────────────────────────────────────────────────────
📄 RESPOSTA (preview):
────────────────────────────────────────────────────────────────────────────────
Para otite média aguda, a dose de amoxicilina varia conforme a idade:
- Crianças: 80-90 mg/kg/dia dividido em 2-3 doses por 10 dias [1]
- Adultos: 500 mg VO 8/8h ou 875 mg VO 12/12h por 10 dias [2]
...
```

---

### Passo 3: Interpretar Resultados

O script testa **5 cenários diferentes:**

1. **DROGA + CONTEXTO** ("dose de amoxicilina para otite")
   - ✅ Esperado: 1 call `rag_medical_search`
   - ❌ Falha se: chamar drug_lookup, web_search, ou múltiplas tools

2. **DROGA SEM CONTEXTO** ("contraindicações de losartana")
   - ✅ Esperado: 1 call `drug_lookup`
   - ❌ Falha se: chamar RAG ou web_search

3. **PROTOCOLO MÉDICO** ("protocolo de pneumonia")
   - ✅ Esperado: 1 call `rag_medical_search`
   - ❌ Falha se: chamar web_search desnecessariamente

4. **CÁLCULO MÉDICO** ("calcule CHA2DS2-VASc")
   - ✅ Esperado: 1 call `medical_calculator`
   - ❌ Falha se: chamar RAG ou web para buscar info sobre o score

5. **PERGUNTA CONCEITUAL** ("o que é hipertensão")
   - ✅ Esperado: 0 calls (resposta direta) OU 1 call `rag_medical_search`
   - ❌ Falha se: chamar múltiplas tools

---

### Passo 4: Analisar Métricas

No final, você verá um **RESUMO GERAL:**

```
════════════════════════════════════════════════════════════════════════════════
                              📈 RESUMO GERAL
════════════════════════════════════════════════════════════════════════════════
Total de testes: 5
Sucessos: 5
Falhas: 0
Taxa de sucesso: 100.0%

Custo médio: $0.0245 (baseline: $0.075)
Tempo médio: 17.8s (baseline: ~24s)
Tools médias: 1.2 (baseline: 5)

✅ Redução de custo: 67.3% ✅

════════════════════════════════════════════════════════════════════════════════
DETALHAMENTO POR CENÁRIO
════════════════════════════════════════════════════════════════════════════════
Cenário                                            Tools           Custo      Tempo      Status
────────────────────────────────────────────────────────────────────────────────────────────────
DROGA + CONTEXTO CLÍNICO → RAG                     1 (rag_medic... $0.0234    18.45s     ✅ OK
DROGA SEM CONTEXTO → drug_lookup                   1 (drug_look... $0.0198    16.20s     ✅ OK
PROTOCOLO MÉDICO → RAG                             1 (rag_medic... $0.0267    19.10s     ✅ OK
CÁLCULO MÉDICO → calculator                        1 (medical_c... $0.0189    15.80s     ✅ OK
PERGUNTA CONCEITUAL → resposta direta ou RAG       1 (rag_medic... $0.0238    17.50s     ✅ OK

✅ TODOS OS TESTES PASSARAM! 🎉
```

**Critérios de Sucesso:**
- ✅ **Taxa de sucesso ≥ 80%** (4/5 testes passando)
- ✅ **Custo médio < $0.045** (60% de redução)
- ✅ **Tools médias ≤ 2** (vs 5 no baseline)
- ✅ **Tempo médio < 20s** (vs 24s no baseline)

---

## 🔍 Monitoramento em Tempo Real

Durante a execução, você pode monitorar logs em outra aba do terminal:

```bash
# Abrir nova aba do terminal
# Executar:
tail -f logs/app.log | grep -E "(llm_response_generated|tool_name|cost_usd)"
```

**O que procurar:**
- Cada `llm_response_generated` mostra custo e tokens
- `tool_name=` mostra qual ferramenta foi chamada
- Procure por múltiplas chamadas da mesma tool (indicaria redundância)

---

## ❌ Troubleshooting

### Erro: "Your default credentials were not found"

**Causa:** Falta credenciais GCP

**Solução:**
```bash
# Adicionar ao .env:
ANTHROPIC_API_KEY=sk-ant-...

# OU configurar GCP credentials
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

---

### Erro: "401 Unauthorized" da Anthropic

**Causa:** API key inválida ou expirada

**Solução:**
```bash
# Verificar se API key está correta
echo $ANTHROPIC_API_KEY

# Obter nova key em: https://console.anthropic.com/
# Atualizar .env
```

---

### Erro: "Tavily API key not found"

**Causa:** Falta TAVILY_API_KEY

**Impacto:** web_search vai falhar, mas outros testes continuam

**Solução:**
```bash
# Adicionar ao .env:
TAVILY_API_KEY=tvly-...

# OU aceitar que testes de web_search falharão
```

---

### Teste Falhando: "ERRO: Tools incorretas!"

**Causa:** LLM está chamando tools erradas apesar das otimizações

**Diagnóstico:**
1. Veja qual tool foi chamada vs esperada
2. Verifique se o prompt está sendo carregado corretamente
3. Analise a query - pode ser ambígua

**Exemplo de falha:**
```
Query: "Qual a dose de amoxicilina para otite média?"
Esperado: rag_medical_search
Obtido: drug_lookup, rag_medical_search

❌ ERRO: LLM ainda está chamando drug_lookup antes de RAG
```

**Ações:**
1. Verificar se FASE 3 está ativa: `grep "parallel_tool_calls=False" workflows/whatsapp/nodes/orchestrate_llm.py`
2. Verificar se system prompt tem STOPPING CRITERIA
3. Reportar caso específico para ajuste fino do prompt

---

### Custo Ainda Alto (> $0.05)

**Causa:** Múltiplas chamadas de tools ou tokens excessivos

**Diagnóstico:**
```bash
# Ver quantas tools foram chamadas
grep "tool_name=" logs/app.log | tail -20

# Ver custo detalhado
grep "cost_usd" logs/app.log | tail -10
```

**Possíveis causas:**
- RAG retornando poucos docs → escala para web_search (legítimo)
- LLM ignorando STOPPING CRITERIA → ajustar prompt
- Contexto acumulado muito grande → verificar message history

---

## 📊 Comparação com Baseline

| Métrica | Baseline (antes) | Meta (após FASES) | Melhoria |
|---------|------------------|-------------------|----------|
| **Tools/query** | 5 | 1-2 | 60-80% ↓ |
| **Custo médio** | $0.075 | $0.02-0.03 | ~60% ↓ |
| **Tempo médio** | ~24s | ~15-20s | ~30% ↓ |

---

## ✅ Checklist Final

Antes de considerar o teste bem-sucedido:

- [ ] Script executou sem erros fatais
- [ ] Taxa de sucesso ≥ 80%
- [ ] Custo médio < $0.045 (60% de redução)
- [ ] Tools médias ≤ 2 por query
- [ ] Cenário "DROGA + CONTEXTO" chamou apenas RAG (crítico!)
- [ ] Sem chamadas redundantes (mesma tool 2x para mesma query)

---

## 🎯 Próximos Passos Após Teste Local

Se testes locais passarem:

1. **Commit das mudanças:**
   ```bash
   git add workflows/ tests/
   git commit -m "feat: otimizações tool calling (FASES 1+2+3)

   - Tool descriptions ultra-específicas (FASE 1)
   - System prompt com STOPPING CRITERIA (FASE 2)
   - parallel_tool_calls=False (FASE 3)
   - Redução ~60% custo, ~30% tempo, 60-80% menos tools

   Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
   ```

2. **Deploy em staging:**
   - Testar com WhatsApp real
   - Monitorar métricas de produção
   - Validar com usuários reais

3. **Documentar resultados:**
   - Atualizar MEMORY.md com resultados dos testes
   - Registrar casos edge descobertos
   - Ajustar prompts se necessário

---

## 📞 Suporte

Se encontrar problemas:
1. Verificar logs em `logs/app.log`
2. Rodar testes unitários: `pytest tests/ --ignore=tests/e2e --ignore=tests/integration`
3. Revisar documentação: `_bmad-output/implementation-artifacts/resumo-fases-1-2-3-tool-calling.md`
