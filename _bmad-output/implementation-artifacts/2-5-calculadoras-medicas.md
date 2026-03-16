# Story 2.5: Calculadoras Médicas

Status: done

## Story

As a aluno,
I want calcular scores médicos (CHA₂DS₂-VASc, Clearance de Creatinina, IMC, Glasgow, etc.) fornecendo dados por texto,
So that resolvo cálculos rapidamente no plantão.

## Acceptance Criteria

1. **Given** o aluno fornece dados para cálculo (ex: "Paciente 72 anos, hipertenso, diabético, sem AVC, sem IC. CHA₂DS₂-VASc?")
   **When** o LLM decide usar a tool `medical_calculator`
   **Then** a tool identifica a calculadora correta e extrai os parâmetros
   **And** executa o cálculo (funções Python locais, sem chamada externa)
   **And** retorna: score calculado, interpretação clínica, conduta recomendada
   **And** cita a diretriz fonte do score

2. **Given** dados insuficientes para o cálculo
   **When** a tool executa
   **Then** retorna quais dados estão faltando para completar o cálculo
   **And** o LLM pergunta ao aluno os dados faltantes

## Tasks / Subtasks

- [x] Task 1: Criar módulo de calculadoras médicas (AC: #1, #2)
  - [x] 1.1 Criar `workflows/whatsapp/tools/calculators.py` com `@tool` decorator
  - [x] 1.2 Implementar calculadora CHA₂DS₂-VASc (score 0-9, interpretação, anticoagulação)
  - [x] 1.3 Implementar Cockcroft-Gault (clearance de creatinina, mL/min)
  - [x] 1.4 Implementar IMC (kg/m², classificação OMS)
  - [x] 1.5 Implementar Escala de Glasgow (3-15, interpretação por gravidade)
  - [x] 1.6 Implementar CURB-65 (0-5, mortalidade, decisão internação)
  - [x] 1.7 Implementar Wells (TEP) (0-12.5, probabilidade, conduta)
  - [x] 1.8 Implementar HEART Score (0-10, risco SCA, conduta)
  - [x] 1.9 Implementar Child-Pugh (5-15, classe A/B/C, sobrevida)
  - [x] 1.10 Implementar correção de sódio para hiperglicemia
  - [x] 1.11 Implementar correção de cálcio pela albumina
- [x] Task 2: Registrar tool no get_tools() (AC: #1)
  - [x] 2.1 Adicionar `medical_calculator` em `workflows/whatsapp/tools/__init__.py`
- [x] Task 3: Atualizar system prompt (AC: #1)
  - [x] 3.1 Adicionar instrução de uso da calculadora em `workflows/whatsapp/prompts/system.py`
- [x] Task 4: Testes unitários (AC: #1, #2)
  - [x] 4.1 Criar `tests/test_whatsapp/test_tools/test_calculators.py`
  - [x] 4.2 Testar cada calculadora com inputs válidos (happy path)
  - [x] 4.3 Testar cada calculadora com inputs inválidos/faltantes
  - [x] 4.4 Testar retorno de dados faltantes (AC #2)
  - [x] 4.5 Testar formatação do resultado (score + interpretação + conduta)

## Dev Notes

### Padrão de Implementação da Tool

A tool `medical_calculator` é uma **ÚNICA tool LangChain** que recebe o nome da calculadora e os parâmetros. Internamente, despacha para a função de cálculo correta. Isso permite ao LLM chamar UMA tool com diferentes calculadoras, em vez de N tools separadas.

```python
# workflows/whatsapp/tools/calculators.py
from langchain_core.tools import tool

CALCULATORS: dict[str, Callable] = {
    "cha2ds2_vasc": _calculate_cha2ds2_vasc,
    "cockcroft_gault": _calculate_cockcroft_gault,
    "imc": _calculate_imc,
    "glasgow": _calculate_glasgow,
    "curb65": _calculate_curb65,
    "wells_tep": _calculate_wells_tep,
    "heart_score": _calculate_heart_score,
    "child_pugh": _calculate_child_pugh,
    "correcao_sodio": _calculate_correcao_sodio,
    "correcao_calcio": _calculate_correcao_calcio,
}

@tool
async def medical_calculator(calculator_name: str, parameters: dict) -> str:
    """Calcula scores e fórmulas médicas. Calculadoras disponíveis:
    - cha2ds2_vasc: Risco de AVC em FA (idade, sexo, ICC, HAS, AVC/AIT, doença vascular, diabetes)
    - cockcroft_gault: Clearance de creatinina (idade, peso_kg, creatinina_serica, sexo)
    - imc: Índice de Massa Corporal (peso_kg, altura_m)
    - glasgow: Escala de Coma de Glasgow (abertura_ocular, resposta_verbal, resposta_motora)
    - curb65: Gravidade de pneumonia (confusao, ureia, freq_resp, pa_sistolica, idade)
    - wells_tep: Probabilidade de TEP (sinais_tvp, diagnostico_alternativo, fc>100, imobilizacao, tep_tvp_previo, hemoptise, cancer)
    - heart_score: Risco de SCA (historia, ecg, idade, fatores_risco, troponina)
    - child_pugh: Classificação de cirrose (bilirrubina, albumina, tp_inr, ascite, encefalopatia)
    - correcao_sodio: Sódio corrigido para hiperglicemia (sodio_medido, glicemia)
    - correcao_calcio: Cálcio corrigido pela albumina (calcio_total, albumina)

    Args:
        calculator_name: Nome da calculadora (ver lista acima)
        parameters: Dicionário com os parâmetros necessários para a calculadora
    """
    calc_fn = CALCULATORS.get(calculator_name)
    if not calc_fn:
        available = ", ".join(sorted(CALCULATORS.keys()))
        return f"Calculadora '{calculator_name}' não encontrada. Disponíveis: {available}"

    try:
        return calc_fn(**parameters)
    except TypeError as e:
        # Parâmetros faltantes
        return _format_missing_params(calculator_name, e)
```

### Fórmulas e Referências Clínicas

#### CHA₂DS₂-VASc (Score 0-9)
- **Referência:** ESC Guidelines 2020 — Atrial Fibrillation
- **Pontuação:** C(ICC)=1, H(HAS)=1, A₂(Idade≥75)=2, D(Diabetes)=1, S₂(AVC/AIT)=2, V(Doença vascular)=1, A(Idade 65-74)=1, Sc(Sexo feminino)=1
- **Interpretação:** 0 (homem) ou 1 (mulher)=baixo risco; 1 (homem)=intermediário; ≥2=alto risco → anticoagulação
- **Params:** `idade: int`, `sexo: str` ("M"/"F"), `icc: bool`, `has: bool`, `avc_ait: bool`, `doenca_vascular: bool`, `diabetes: bool`

#### Cockcroft-Gault (mL/min)
- **Referência:** Cockcroft & Gault, 1976 — Nephron
- **Fórmula:** CrCl = ((140 - idade) × peso_kg) / (72 × creatinina_sérica) × 0.85 se mulher
- **Interpretação:** >90=normal; 60-89=leve; 30-59=moderada; 15-29=grave; <15=falência
- **Params:** `idade: int`, `peso_kg: float`, `creatinina_serica: float`, `sexo: str` ("M"/"F")

#### IMC (kg/m²)
- **Referência:** OMS — Classificação de Obesidade
- **Fórmula:** peso / (altura²)
- **Classificação:** <18.5=baixo peso; 18.5-24.9=normal; 25-29.9=sobrepeso; 30-34.9=obesidade I; 35-39.9=obesidade II; ≥40=obesidade III
- **Params:** `peso_kg: float`, `altura_m: float`

#### Glasgow (3-15)
- **Referência:** Teasdale & Jennett, 1974 — The Lancet
- **Componentes:** Abertura ocular (1-4), Resposta verbal (1-5), Resposta motora (1-6)
- **Interpretação:** 13-15=leve; 9-12=moderado; 3-8=grave
- **Params:** `abertura_ocular: int` (1-4), `resposta_verbal: int` (1-5), `resposta_motora: int` (1-6)

#### CURB-65 (0-5)
- **Referência:** British Thoracic Society, 2009
- **Critérios:** C(Confusão)=1, U(Ureia>42mg/dL)=1, R(FR≥30)=1, B(PAS<90 ou PAD≤60)=1, 65(Idade≥65)=1
- **Interpretação:** 0-1=ambulatorial; 2=considerar internação; 3-5=internação (≥4=UTI)
- **Params:** `confusao: bool`, `ureia: float`, `freq_resp: int`, `pa_sistolica: int`, `pa_diastolica: int`, `idade: int`

#### Wells TEP (0-12.5)
- **Referência:** Wells et al., 2001 — Thrombosis and Haemostasis
- **Critérios:** Sinais/sintomas de TVP=3, Diagnóstico alternativo menos provável=3, FC>100=1.5, Imobilização/cirurgia=1.5, TEP/TVP prévio=1.5, Hemoptise=1, Câncer ativo=1
- **Interpretação:** <2=baixa probabilidade; 2-6=moderada; >6=alta
- **Params:** `sinais_tvp: bool`, `diagnostico_alternativo_improvavel: bool`, `fc_maior_100: bool`, `imobilizacao_cirurgia: bool`, `tep_tvp_previo: bool`, `hemoptise: bool`, `cancer_ativo: bool`

#### HEART Score (0-10)
- **Referência:** Backus et al., 2010 — Netherlands Heart Journal
- **Critérios:** H(História)=0-2, E(ECG)=0-2, A(Idade)=0-2, R(Fatores de risco)=0-2, T(Troponina)=0-2
- **Interpretação:** 0-3=baixo risco (MACE 0.9-1.7%); 4-6=moderado (12-16.6%); 7-10=alto (50-65%)
- **Params:** `historia: int` (0-2), `ecg: int` (0-2), `idade: int`, `fatores_risco: int` (0-2), `troponina: int` (0-2)

#### Child-Pugh (5-15)
- **Referência:** Pugh et al., 1973 — British Journal of Surgery
- **Critérios:** Bilirrubina, Albumina, TP/INR, Ascite, Encefalopatia (cada 1-3 pontos)
- **Classificação:** 5-6=A (sobrevida 100% 1 ano); 7-9=B (80%); 10-15=C (45%)
- **Params:** `bilirrubina: float`, `albumina: float`, `inr: float`, `ascite: str` ("ausente"/"leve"/"moderada_grave"), `encefalopatia: str` ("ausente"/"grau1_2"/"grau3_4")

#### Correção de Sódio para Hiperglicemia
- **Referência:** Katz, 1973 — New England Journal of Medicine
- **Fórmula:** Na corrigido = Na medido + 1.6 × ((glicemia - 100) / 100)
- **Params:** `sodio_medido: float`, `glicemia: float`

#### Correção de Cálcio pela Albumina
- **Referência:** Payne et al., 1973 — British Medical Journal
- **Fórmula:** Ca corrigido = Ca total + 0.8 × (4.0 - albumina)
- **Params:** `calcio_total: float`, `albumina: float`

### Decisões Técnicas Críticas

1. **ÚNICA tool, múltiplas calculadoras:** O LLM recebe uma tool `medical_calculator` com docstring listando todas as calculadoras. Isso evita bind_tools com N tools (poluição do context window) e permite adicionar novas calculadoras sem alterar o registro.

2. **Funções PURAS e LOCAIS:** Todas as calculadoras são funções Python puras, sem I/O, sem chamada de API externa. Execução < 1ms. Zero custo. Embora a tool use `async` (exigido pelo padrão LangChain ToolNode), as funções internas são sync e chamadas diretamente.

3. **Validação de parâmetros:** Cada função interna valida seus inputs e retorna mensagem clara quando faltam dados. O LLM usa essa mensagem para perguntar ao aluno.

4. **Sem estado adicional no WhatsAppState:** Calculadoras não adicionam campos ao state. O resultado volta como ToolMessage no loop de tools, e o LLM compõe a resposta final normalmente.

5. **Sem citação [N]/[W-N]:** Calculadoras não geram citações indexadas como RAG/web. A referência à diretriz fonte é incluída no texto de retorno da tool (ex: "Referência: ESC Guidelines 2020").

### Padrões Obrigatórios (Herdados de Stories 2.1-2.3)

- **LangChain @tool decorator:** Docstring é a descrição para o LLM
- **Async/await:** `async def medical_calculator(...)` — exigido pelo ToolNode
- **structlog JSON logging:** `logger.info("calculator_executed", calculator=name, params=params, result=score)`
- **Error handling via string:** Retornar string de erro, NUNCA levantar exceção — o LLM recebe e decide
- **Import order:** Standard → Third-party → Local
- **Naming:** snake_case (funções, variáveis), PascalCase (classes)
- **PROIBIDO:** `print()`, sync I/O, `import *`, camelCase
- **Tool retorna string:** Sempre `str`, nunca dict/int/float

### Project Structure Notes

- **Novo arquivo:** `workflows/whatsapp/tools/calculators.py`
- **Arquivo de teste:** `tests/test_whatsapp/test_tools/test_calculators.py`
- **Arquivos modificados:**
  - `workflows/whatsapp/tools/__init__.py` — adicionar `medical_calculator` ao `get_tools()`
  - `workflows/whatsapp/prompts/system.py` — adicionar instrução de uso
- **NÃO modificar:** graph.py, orchestrate_llm.py, state.py, format_response.py — infraestrutura de ToolNode já existe desde Story 2.2
- **NÃO criar:** novos models, migrations, providers, services — tudo já existe

### System Prompt Addition

Adicionar ao `build_system_message()` em `workflows/whatsapp/prompts/system.py`:

```
- Use medical_calculator para cálculos de scores e fórmulas médicas (CHA₂DS₂-VASc, Cockcroft-Gault, IMC, Glasgow, CURB-65, Wells TEP, HEART Score, Child-Pugh, correção de sódio, correção de cálcio)
- Se o aluno pedir um cálculo, SEMPRE use a tool — NUNCA calcule de cabeça
- Se dados insuficientes, pergunte ao aluno os dados faltantes antes de calcular
- Inclua a diretriz fonte na resposta (a tool já retorna a referência)
```

### Armadilhas Conhecidas (de Stories Anteriores)

1. **bind_tools já feito em get_model(tools=):** Desde Story 2.3, bind_tools é feito no primary E fallback antes de with_fallbacks(). NÃO fazer bind_tools extra.
2. **ToolNode já existe no grafo:** Desde Story 2.2, o grafo tem ToolNode + tools_condition + loop. Nova tool só precisa ser adicionada ao get_tools().
3. **Custo com tools loop:** Cada round-trip é uma invocação LLM (CostTrackingCallback já acumula). Para calculadora, tipicamente 2 invocações: 1ª (tool_call) + 2ª (com resultado).
4. **collect_sources filtra por turno atual:** Desde code review do Story 2.2. Calculadoras não geram sources, então collect_sources ignora automaticamente.
5. **tools_condition import:** De `langgraph.prebuilt`, NÃO de `langgraph.graph`.
6. **Docstring é contrato com o LLM:** A docstring da tool é o que o LLM vê para decidir quando usar. DEVE listar todas as calculadoras e seus parâmetros claramente.

### Testes Requeridos

```python
# tests/test_whatsapp/test_tools/test_calculators.py

# Para CADA calculadora:
# 1. Happy path — inputs válidos → score correto + interpretação + referência
# 2. Edge cases — valores limítrofes (ex: idade=65 no CHA₂DS₂-VASc)
# 3. Dados faltantes — parâmetro ausente → mensagem clara de qual dado falta
# 4. Inputs inválidos — valores fora de range → mensagem de erro amigável

# Exemplos específicos:
# CHA₂DS₂-VASc: homem 72a, HAS, DM, sem AVC → score 3 → anticoagulação
# Cockcroft-Gault: mulher 65a, 60kg, Cr 1.2 → CrCl ~42 mL/min → insuf. moderada
# IMC: 70kg, 1.75m → 22.9 → normal
# Glasgow: 4+5+6 → 15 → sem alteração
# CURB-65: confuso, ureia 50, FR 32, PAS 85, 70a → score 5 → UTI
# Wells TEP: sinais TVP + sem alt. diagnóstico → score 6 → moderada
# Calculadora inexistente → mensagem de erro com lista de disponíveis
```

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic2-Story2.5] — User story e acceptance criteria
- [Source: _bmad-output/planning-artifacts/architecture.md#tools-directory] — Estrutura de tools e padrão @tool
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-006] — LangGraph + LangChain + ToolNode
- [Source: _bmad-output/planning-artifacts/architecture.md#WhatsAppState] — State TypedDict (sem campos novos)
- [Source: _bmad-output/planning-artifacts/architecture.md#testing] — pytest + pytest-asyncio
- [Source: _bmad-output/implementation-artifacts/2-1-rag-medico.md] — Padrões de tool, singleton, error handling
- [Source: _bmad-output/implementation-artifacts/2-2-web-search.md] — ToolNode infra, collect_sources, get_tools()
- [Source: _bmad-output/implementation-artifacts/2-3-verificacao-artigos-pubmed.md] — bind_tools em get_model, retry pattern

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Nenhum bug encontrado durante implementação.
- Único ajuste: teste `test_class_b` do Child-Pugh usava parâmetros que somavam score 10 (Classe C) em vez de 7-9 (Classe B). Corrigido ajustando INR e encefalopatia do teste.

### Completion Notes List

- Implementadas 10 calculadoras médicas como funções Python puras (sem I/O, <1ms execução)
- Padrão ÚNICA tool `medical_calculator` com dispatch por `calculator_name` conforme spec
- Cada calculadora retorna: score + interpretação clínica + conduta + referência bibliográfica
- Validação de parâmetros com mensagens claras para dados faltantes/inválidos
- Tool registrada no `get_tools()` — integração automática via ToolNode existente
- System prompt atualizado com 4 novas instruções sobre uso da calculadora
- 55+7 testes unitários cobrindo: happy path, edge cases, inputs inválidos, dados faltantes, formatação, type coercion
- Suite completa de testes passa sem regressões

### File List

- `workflows/whatsapp/tools/calculators.py` — **NOVO** — Módulo de calculadoras médicas (10 calculadoras + tool LangChain)
- `workflows/whatsapp/tools/__init__.py` — **MODIFICADO** — Adicionado import e registro de `medical_calculator` no `get_tools()`
- `workflows/whatsapp/prompts/system.py` — **MODIFICADO** — Adicionadas instruções de uso da calculadora no system prompt
- `tests/test_whatsapp/test_tools/test_calculators.py` — **NOVO** — 62 testes unitários para todas as calculadoras
- `tests/test_whatsapp/test_tools/test_medical_calculator.py` — **NOVO** (Story 2.6) — 26 testes complementares

## Change Log

- 2026-03-10: Implementação completa da Story 2.5 — Calculadoras Médicas (10 calculadoras, tool LangChain, system prompt, 55 testes)
- 2026-03-10: Code Review — 9 issues encontrados, 7 corrigidos:
  - H1: Adicionado "Conduta:" nas 5 calculadoras faltantes (IMC, Glasgow, Child-Pugh, correcao_sodio, correcao_calcio) — AC1 compliance
  - H2/H3: Adicionado `except Exception` broad handler (M1/H3 corrigidos pelo autor)
  - M1: Adicionada validação de inputs em correcao_sodio e correcao_calcio (corrigido pelo autor)
  - M3: Adicionados 6 testes de type coercion + 1 teste de conduta para todas as calculadoras
  - M2: Corrigido test_medical_calculator.py (Wells TEP com params explícitos, removido import não usado)
  - M4: Wells TEP defaults mantidos por decisão do autor (design intencional)
  - L1: _CALCULATOR_PARAMS dict mantido (aceitável)

### Melhorias Futuras Identificadas (Code Review)

**Fallback LLM + Telemetria de demanda** — Quando o aluno pede um score/calculadora que NÃO existe na tool, o fluxo atual retorna "calculadora não encontrada". A proposta é:

1. **Fallback imediato:** Se `calculator_name` não existe em `CALCULATORS`, em vez de retornar erro, instruir o LLM a calcular usando seu conhecimento médico (já sabe as fórmulas). Retornar resultado com disclaimer: "Cálculo feito pelo assistente (sem validação por calculadora dedicada)."

2. **Telemetria de demanda:** Logar `calculator_not_found` com o nome solicitado. Após N solicitações (threshold configurável), sugerir ao time a adição da calculadora como função Python pura.

3. **Pipeline de adição:** Nova calculadora = 1 função Python pura + entrada no dict `CALCULATORS` + entrada no dict `_CALCULATOR_PARAMS` + atualizar docstring da tool. Zero mudança em graph/state/infra.

**Impacto:** Transforma a tool de "catálogo fechado" em "catálogo vivo com fallback inteligente". Candidata a story futura (ex: Story 2.7 ou Epic de melhoria contínua).
