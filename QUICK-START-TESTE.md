# 🚀 Quick Start - Teste Local (5 minutos)

## 1️⃣ Verificar Credenciais (30s)

```bash
# Ver se tem API key da Anthropic
cat .env | grep ANTHROPIC_API_KEY

# Se não tiver, adicionar:
echo "ANTHROPIC_API_KEY=sk-ant-api03-..." >> .env
```

**Mínimo necessário:** `ANTHROPIC_API_KEY` OU `GCP_CREDENTIALS`

---

## 2️⃣ Ativar Ambiente (10s)

```bash
source .venv/bin/activate
```

---

## 3️⃣ Rodar Teste (30s de setup + ~3min de execução)

**Opção A - Teste Simples:**
```bash
python scripts/test_tool_calling.py
```

**Opção B - Teste com Monitor (2 terminais):**

Terminal 1 (monitor):
```bash
./scripts/monitor_test.sh
```

Terminal 2 (teste):
```bash
python scripts/test_tool_calling.py
```

---

## 4️⃣ Ver Resultado (5s)

No final você verá:

```
✅ TODOS OS TESTES PASSARAM! 🎉

Custo médio: $0.0245 (baseline: $0.075)  ← 67% de redução ✅
Tempo médio: 17.8s (baseline: ~24s)      ← 26% mais rápido ✅
Tools médias: 1.2 (baseline: 5)          ← 76% menos calls ✅
```

**Sucesso = ✅** em todos os 3 indicadores acima

---

## 🎯 O Que Esperar

### ✅ Teste de Sucesso
```
TESTE: DROGA + CONTEXTO CLÍNICO → RAG
Query: "Qual a dose de amoxicilina para otite média?"
Tools chamadas: 1
Sequência: rag_medical_search
✅ Correto: Tools esperadas foram chamadas
✅ Custo reduzido: 68.8% menor que baseline
```

### ❌ Teste de Falha
```
TESTE: DROGA + CONTEXTO CLÍNICO → RAG
Query: "Qual a dose de amoxicilina para otite média?"
Tools chamadas: 3
Sequência: drug_lookup → rag_medical_search → web_search
❌ ERRO: Tools incorretas! Esperado: ['rag_medical_search'], Obtido: ['drug_lookup', 'rag_medical_search', 'web_search']
```

---

## ⚠️ Problemas Comuns

### "Your default credentials were not found"
→ Adicionar `ANTHROPIC_API_KEY` no `.env`

### "401 Unauthorized"
→ API key inválida, pegar nova em console.anthropic.com

### "Tavily API key not found"
→ Opcional, testes continuam (web_search vai falhar)

---

## 📖 Documentação Completa

- **Instruções detalhadas:** [TESTE-LOCAL-INSTRUCOES.md](TESTE-LOCAL-INSTRUCOES.md)
- **Resumo técnico:** [_bmad-output/implementation-artifacts/resumo-fases-1-2-3-tool-calling.md](_bmad-output/implementation-artifacts/resumo-fases-1-2-3-tool-calling.md)

---

## 🎉 Se Tudo Passar

1. Commit as mudanças
2. Deploy em staging
3. Testar com WhatsApp real
4. 🚀 Produção!
