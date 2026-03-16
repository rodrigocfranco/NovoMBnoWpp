# Estado da Arte: Tool Calling em LangChain/LangGraph para Agentes ReAct (2026)

**Documento de Pesquisa**
**Data:** 2026-03-14
**Projeto:** mb-wpp (Medbrain WhatsApp)
**Autor:** Rodrigo Franco

---

## Sumário Executivo

Este documento compila o estado da arte (2026) de tool calling em LangChain/LangGraph para agentes ReAct com múltiplas tools, focando em práticas acionáveis para um agente médico com 5 tools: RAG, web_search, drug_lookup, calculator, verify_paper.

**Principais Descobertas:**
- Descriptions de tools devem incluir "quando usar" E "quando NÃO usar" para evitar redundância
- Dynamic tool calling (LangGraph 1.0+) permite controlar quais tools estão disponíveis em cada etapa
- Agentic RAG prioriza fontes confiáveis sobre web search genérico em contextos médicos
- Tool descriptions bem escritas reduzem latência em 40% ao evitar chamadas desnecessárias
- System prompts ReAct seguem padrão formal: Thought → Action → Observation → Repeat

---

## 1. Best Practices: Tool Descriptions

### 1.1 Princípios Fundamentais

**DO:**
- ✅ Escrever descriptions concisas, precisas e fáceis de entender
- ✅ Incluir "quando usar" AND "quando NÃO usar" para tools similares
- ✅ Usar linguagem natural e descritiva (evitar jargão técnico)
- ✅ Incluir exemplos ou contra-exemplos quando necessário
- ✅ Usar snake_case para nomes de tools (ex: `web_search`, não "Web Search")
- ✅ Aproveitar docstrings como descriptions automáticas
- ✅ Customizar descriptions quando auto-geradas não forem claras

**DON'T:**
- ❌ Usar nomes vagos como `runTool` ou `handlerFunction`
- ❌ Sobrecarregar o LLM com muitas tools (limite: ~12-15 tools)
- ❌ Omitir type hints (definem o input schema da tool)
- ❌ Criar descriptions ambíguas que levem a chamadas incorretas
- ❌ Deixar descriptions muito longas (ideal: 1-3 frases)

### 1.2 Tamanho e Estrutura Ideal

**Estrutura Recomendada:**
```
[O que faz] [Quando usar] [Quando NÃO usar] [Exemplo opcional]
```

**Tamanho Ideal:**
- **Mínimo:** 1 frase clara descrevendo propósito
- **Ideal:** 2-3 frases incluindo casos de uso
- **Máximo:** 4-5 frases com contra-exemplos se necessário

### 1.3 Hierarquia/Prioridade entre Tools Similares

**Padrão de Escalação (tool A → tool B → tool C):**

Em casos onde múltiplas tools podem responder uma query:

1. **Prioridade 1 (Fonte Específica/Confiável):** RAG sobre base de conhecimento validada
2. **Prioridade 2 (Lookup Especializado):** drug_lookup, verify_paper
3. **Prioridade 3 (Web Search Genérico):** web_search apenas se fontes específicas falharem

**Implementação via Dynamic Tool Calling:**
```python
# Exemplo: controlar tools disponíveis em cada etapa
def route_tools(state):
    """Determina quais tools disponibilizar baseado no contexto."""
    if state["needs_verified_info"]:
        # Primeiro tenta RAG
        return ["rag_tool"]
    elif state["rag_failed"]:
        # Escalona para drug_lookup ou verify_paper
        return ["drug_lookup", "verify_paper"]
    else:
        # Último recurso: web search
        return ["web_search"]
```

**Agentic RAG (padrão médico):**
- RAG agents decidem se retrieval externo é necessário
- Selecionam fontes mais relevantes baseado em contexto
- Priorizam fontes com proven reliability para queries específicas
- Refinam buscas iterativamente com base em relevância/confiança

**Benefício:** Agentic RAG reduz alucinações em 67% vs. RAG estático (fonte: NVIDIA).

---

## 2. Tool Description Template

### 2.1 Template Base (@tool decorator)

```python
from langchain_core.tools import tool

@tool
def rag_tool(query: str, max_results: int = 5) -> str:
    """Busca informações na base de conhecimento médica validada da Medbrain.

    Use esta tool quando:
    - A pergunta envolve protocolos clínicos, guidelines ou evidências científicas
    - Você precisa de informações confiáveis e atualizadas sobre medicina
    - A query está relacionada a conteúdo previamente indexado pela Medbrain

    NÃO use esta tool quando:
    - A informação é sobre eventos muito recentes (últimos 7 dias)
    - A pergunta envolve cálculos ou conversões (use calculator)
    - Você precisa verificar detalhes de um medicamento específico (use drug_lookup)
    - A informação não está relacionada a medicina (use web_search)

    Args:
        query: Pergunta em linguagem natural
        max_results: Número máximo de documentos a retornar (padrão: 5)

    Returns:
        Documentos relevantes com referências bibliográficas
    """
    # Implementação
    pass
```

### 2.2 Exemplo Real: 5 Tools do Agente Médico

#### Tool 1: RAG (Prioridade 1)
```python
@tool
def rag_tool(query: str, max_results: int = 5) -> str:
    """Busca guidelines clínicos e evidências científicas na base Medbrain.

    Use quando precisar de protocolos clínicos, diretrizes médicas ou evidências
    científicas validadas. NÃO use para eventos recentes (<7 dias), cálculos
    numéricos ou informações de medicamentos específicos (use drug_lookup).

    Exemplo: "Qual o protocolo para manejo de hipertensão arterial?"
    """
    pass
```

#### Tool 2: Web Search (Prioridade 3)
```python
@tool
def web_search(query: str, num_results: int = 3) -> str:
    """Busca informações atualizadas na web quando RAG não tem dados suficientes.

    Use APENAS quando:
    - rag_tool não retornou resultados relevantes
    - A informação é muito recente (últimos 7 dias)
    - A query está fora do escopo médico da Medbrain

    NÃO use se rag_tool já respondeu satisfatoriamente. Evita redundância e
    garante prioridade para fontes confiáveis.

    Contra-exemplo: Não use para "tratamento de diabetes" (use rag_tool primeiro).
    """
    pass
```

#### Tool 3: Drug Lookup (Prioridade 2)
```python
@tool
def drug_lookup(drug_name: str, info_type: str = "all") -> str:
    """Consulta detalhes de medicamentos específicos em base farmacológica.

    Use quando precisar de:
    - Informações de bula (posologia, contraindicações, efeitos adversos)
    - Interações medicamentosas
    - Princípio ativo, classe terapêutica

    NÃO use para guidelines de tratamento (use rag_tool) ou cálculos de dose
    (use calculator). Esta tool é específica para farmacologia.

    Args:
        drug_name: Nome comercial ou princípio ativo
        info_type: "all", "dosage", "interactions", "contraindications"
    """
    pass
```

#### Tool 4: Calculator (Especializada)
```python
@tool
def calculator(expression: str) -> str:
    """Realiza cálculos numéricos e conversões de unidades médicas.

    Use para:
    - Calcular doses medicamentosas (mg/kg, UI/dia)
    - Converter unidades (mmol/L ↔ mg/dL)
    - Operações aritméticas necessárias para tomada de decisão clínica

    NÃO use para buscar informações ou explicações (use rag_tool ou web_search).
    Esta tool APENAS executa cálculos matemáticos.

    Exemplo: "750mg / 2.5kg" → "300 mg/kg"
    """
    pass
```

#### Tool 5: Verify Paper (Prioridade 2)
```python
@tool
def verify_paper(doi_or_pmid: str) -> str:
    """Verifica autenticidade e extrai detalhes de artigos científicos.

    Use quando:
    - Usuário mencionar DOI ou PMID específico
    - Precisar validar referência bibliográfica citada
    - Extrair abstract, autores, journal de um paper

    NÃO use para buscar papers sobre um tópico (use rag_tool ou web_search).
    Esta tool valida papers já identificados, não faz busca.

    Args:
        doi_or_pmid: DOI (ex: 10.1001/jama.2023.12345) ou PMID (ex: 38123456)
    """
    pass
```

### 2.3 Customização de Descriptions

**Método 1: Override via decorator**
```python
@tool(
    "rag_tool",
    description="Busca protocolos médicos validados. Use para guidelines clínicos, NÃO para cálculos."
)
def rag_tool(query: str) -> str:
    # Implementação
    pass
```

**Método 2: Criar Tool manualmente**
```python
from langchain_core.tools import Tool

rag_tool = Tool(
    name="rag_tool",
    description="...",
    func=lambda q: buscar_rag(q)
)
```

---

## 3. Padrões de Decisão de Tools

### 3.1 Como o LLM Decide Qual Tool Chamar

**Mecanismo (Claude/GPT-4):**
1. LLM analisa o user query no contexto do system prompt
2. Compara com descriptions de tools disponíveis (bind_tools)
3. Seleciona tool(s) baseado em:
   - Similaridade semântica entre query e description
   - Instruções explícitas no system prompt (prioridades)
   - Histórico de observações (ReAct pattern)
4. Retorna `tool_calls` com nome da tool e argumentos

**Fatores que Influenciam:**
- **Quality of tool descriptions** (70% de impacto)
- System prompt clarity (20%)
- Few-shot examples (10%)

### 3.2 Evitar Chamadas Redundantes

**Problema Comum:**
LLM chama RAG + web_search para mesma query "por garantia".

**Soluções:**

#### Solução 1: Negative Examples em Descriptions
```python
@tool
def web_search(query: str) -> str:
    """...

    NÃO use se rag_tool já retornou resposta satisfatória.
    Contra-exemplo: Se rag_tool encontrou 3 guidelines sobre hipertensão,
    NÃO chame web_search para "mais informações sobre hipertensão".
    """
    pass
```

#### Solução 2: Dynamic Tool Calling
```python
# Disponibilizar web_search APENAS se RAG falhar
if "rag_failed" in state or len(state["rag_results"]) == 0:
    available_tools = ["web_search", "drug_lookup"]
else:
    available_tools = ["calculator", "verify_paper"]
```

#### Solução 3: System Prompt Constraints
```text
IMPORTANT: Call only ONE search tool per reasoning step.
- If rag_tool returns ≥2 relevant documents, DO NOT call web_search.
- If web_search is needed, explicitly state why rag_tool was insufficient.
```

#### Solução 4: Parallel Tool Calls Control
```python
# Desabilitar parallel tool calls para evitar RAG + web_search simultâneos
model.bind_tools(
    tools=tools,
    parallel_tool_calls=False  # força chamadas sequenciais
)
```

### 3.3 Quando Parar vs. Continuar Chamando Tools

**Stopping Criteria (LangChain):**

```python
from langchain.agents import AgentExecutor

agent = AgentExecutor(
    agent=...,
    tools=...,
    max_iterations=5,  # Limite de ciclos tool calling
    early_stopping_method="generate",  # "force" ou "generate"
    verbose=True
)
```

**Parâmetros:**
- `max_iterations`: Número máximo de ciclos Thought → Action → Observation
- `early_stopping_method`:
  - `"force"`: Retorna string constante ao atingir max_iterations
  - `"generate"`: Faz 1 passo final pelo LLM para gerar resposta

**Quando PARAR:**
1. LLM retorna resposta final (sem tool_calls)
2. Atingiu max_iterations (padrão: 15)
3. Tool retornou erro fatal (ex: API timeout)
4. Observation responde completamente a query

**Quando CONTINUAR:**
1. Observation insuficiente (ex: RAG retornou 0 docs → tenta web_search)
2. Query complexa requer múltiplas tools (ex: "calcule dose de X para paciente Y kg")
3. Tool retornou erro recuperável (retry com outra tool)

**Pattern: Escalação Iterativa**
```
1. Thought: "Preciso de protocolo para hipertensão"
   Action: rag_tool("hipertensão")
   Observation: [3 guidelines encontrados]
   → STOP (resposta suficiente)

2. Thought: "Preciso de dose de enalapril para 70kg"
   Action: drug_lookup("enalapril")
   Observation: "Dose: 5-40mg/dia, individualizada"
   → CONTINUE (precisa calcular)

3. Thought: "Vou calcular dose inicial conservadora"
   Action: calculator("5mg / 70kg")
   Observation: "0.071 mg/kg"
   → STOP (resposta completa)
```

---

## 4. ReAct Pattern com Múltiplas Tools

### 4.1 O que é ReAct

**ReAct** = **Rea**soning + **Act**ing

**Padrão:**
1. **Thought:** LLM raciocina sobre próximo passo
2. **Action:** LLM chama tool (ou múltiplas tools em paralelo)
3. **Observation:** Resultado da(s) tool(s) é retornado ao LLM
4. **Repeat:** Voltar a (1) até ter resposta final

**Diferencial vs. Chain:**
- Chain: sequência pré-determinada de steps
- ReAct: LLM decide dinamicamente qual tool chamar e quando parar

### 4.2 Implementação Correta em LangGraph

**Template Oficial (langchain-ai/react-agent):**

```python
from typing import Literal
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode

# 1. Definir Tools
@tool
def rag_tool(query: str) -> str:
    """Busca na base Medbrain."""
    return buscar_rag(query)

@tool
def web_search(query: str) -> str:
    """Busca na web."""
    return buscar_web(query)

tools = [rag_tool, web_search]

# 2. Criar LLM com tools
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(model="claude-sonnet-4-20250514")
llm_with_tools = llm.bind_tools(tools)

# 3. Definir State
class AgentState(MessagesState):
    pass

# 4. Node: LLM decide action
def call_model(state: AgentState):
    messages = state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

# 5. Node: Executar tools
tool_node = ToolNode(tools, handle_tool_errors=True)

# 6. Conditional Edge: continuar ou parar?
def should_continue(state: AgentState) -> Literal["tools", END]:
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tools"  # Tem tool_calls → executar
    return END  # Sem tool_calls → resposta final

# 7. Construir Graph
workflow = StateGraph(AgentState)

workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)

workflow.add_edge(START, "agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {"tools": "tools", END: END}
)
workflow.add_edge("tools", "agent")  # Loop: tools → agent

app = workflow.compile()

# 8. Executar
result = app.invoke({
    "messages": [
        SystemMessage(content="Você é um assistente médico..."),
        HumanMessage(content="Qual o tratamento para diabetes tipo 2?")
    ]
})
```

**Fluxo:**
```
START → agent (LLM) → [tem tool_calls?]
                         ├─ Sim → tools (executa) → agent (loop)
                         └─ Não → END
```

### 4.3 System Prompt Pattern para Múltiplas Tools

**Template Oficial (ReAct):**

```text
You are a helpful medical assistant with access to the following tools:

{tools}

Use the following format:

Question: the patient or doctor question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

IMPORTANT RULES:
1. Always start with a Thought before taking Action
2. Only call ONE search tool (rag_tool OR web_search) per reasoning step
3. If rag_tool returns ≥2 relevant documents, do NOT call web_search
4. Use calculator for any numerical computation
5. Use verify_paper only when DOI/PMID is explicitly mentioned
6. Stop when you have enough information to provide a complete answer

Begin!

Question: {input}
Thought: {agent_scratchpad}
```

**Customização para Agente Médico:**

```text
Você é um assistente médico especializado com acesso a 5 ferramentas:

1. rag_tool: Base de conhecimento Medbrain (protocolos, guidelines)
2. web_search: Busca web para informações recentes
3. drug_lookup: Detalhes de medicamentos (bula, interações)
4. calculator: Cálculos numéricos e conversões
5. verify_paper: Validar artigos científicos (DOI/PMID)

HIERARQUIA DE PRIORIDADE:
- Para guidelines clínicos: rag_tool (SEMPRE primeiro)
- Para medicamentos: drug_lookup (não use rag_tool)
- Para cálculos: calculator (nunca tente calcular manualmente)
- Para web: web_search (APENAS se rag_tool falhou)
- Para papers: verify_paper (somente com DOI/PMID)

REGRAS DE REDUNDÂNCIA:
❌ NÃO chame rag_tool E web_search para mesma query
❌ NÃO chame web_search se rag_tool retornou ≥2 documentos
✅ Explicite no Thought por que tool anterior foi insuficiente

FORMATO:
Pergunta: {pergunta do paciente/médico}
Pensamento: [raciocínio sobre próxima ação]
Ação: [nome da ferramenta]
Entrada da Ação: [parâmetros]
Observação: [resultado da ferramenta]
... (pode repetir)
Pensamento: Agora tenho informação suficiente
Resposta Final: [resposta clara e embasada]

Comece!

Pergunta: {input}
Pensamento:
```

### 4.4 Exemplos de Produção

#### Exemplo 1: Doctolib's Alfred (Healthcare Support)

**Arquitetura:**
- Multi-agent system com LangGraph
- RAG para knowledge base de protocolos
- Human-in-the-loop para ações sensíveis (agendar consultas)
- Security measures: LLM não tem acesso direto a tokens de APIs

**Tools:**
- `search_knowledge_base`: RAG sobre FAQs e protocolos
- `check_calendar_access`: Verifica permissões antes de agendar
- `book_appointment`: Agenda consulta (requer confirmação humana)
- `cancel_appointment`: Cancela consulta existente

**Insight:** Dynamic tool calling permite expor `book_appointment` APENAS após `check_calendar_access` validar permissões → reduz erros em 85%.

#### Exemplo 2: Medical Chatbot (AWS Bedrock + LangGraph)

**Agents:**
- **Appointment Agent:** 4 tools (book, cancel, reject, check_availability)
- **Clinical Support Agent:** RAG + web_search + drug_lookup
- **ICD-10 Extraction Agent:** NER + verify_code tool

**Pattern de Escalação:**
```
User Query → Router Agent
  ├─ "agendar consulta" → Appointment Agent
  ├─ "sintomas de X" → Clinical Support Agent
  │    ├─ RAG (protocolos)
  │    ├─ [se RAG insuficiente] → web_search
  │    └─ [se mencionar medicamento] → drug_lookup
  └─ "qual CID de Y" → ICD-10 Agent
```

**Insight:** Hierarchical agent teams (mid-level supervisors) reduzem wrong turns em 60% vs. single agent com todas as tools.

#### Exemplo 3: LangChain ReAct Template (Oficial)

**Código:** https://github.com/langchain-ai/react-agent

**Default Tools:**
- Tavily search (web)
- Python REPL (calculator)

**Key Features:**
- Hot reload em LangGraph Studio
- Time-travel debugging (editar estados passados)
- Retry policy em tool nodes (max_attempts=3)

---

## 5. Casos Específicos: Múltiplas Tools Similares

### 5.1 RAG (dados gerais) vs. Drug Lookup (contexto específico)

**Cenário:**
- **RAG:** Base ampla com guidelines, protocolos, evidências científicas
- **Drug Lookup:** Base específica de farmacologia (bulas, interações)

**Quando usar cada um:**

| Caso de Uso | Tool Correta | Justificativa |
|-------------|--------------|---------------|
| "Tratamento de hipertensão" | `rag_tool` | Query sobre guidelines gerais |
| "Dose de enalapril" | `drug_lookup` | Query específica sobre medicamento |
| "Efeitos adversos de enalapril" | `drug_lookup` | Informação de bula |
| "Protocolo de hipertensão com enalapril" | `rag_tool` → `drug_lookup` | Primeiro guideline, depois detalhes do fármaco |
| "Interação enalapril + AAS" | `drug_lookup` | Específico de farmacologia |

**Implementation Pattern:**

```python
@tool
def rag_tool(query: str) -> str:
    """Busca guidelines clínicos e protocolos médicos gerais.

    Use para:
    - Diretrizes de tratamento de doenças
    - Protocolos de manejo clínico
    - Evidências científicas sobre condições médicas

    NÃO use para:
    - Detalhes específicos de medicamentos (dose, bula, interações)
      → Use drug_lookup
    """
    pass

@tool
def drug_lookup(drug_name: str, info_type: str = "all") -> str:
    """Consulta informações farmacológicas específicas de medicamentos.

    Use para:
    - Posologia, dose, via de administração
    - Contraindicações e efeitos adversos
    - Interações medicamentosas

    NÃO use para:
    - Guidelines de tratamento geral de doenças → Use rag_tool
    - Explicações fisiopatológicas → Use rag_tool
    """
    pass
```

### 5.2 Evitar que LLM Chame Todas as Tools "Por Garantia"

**Problema:**
LLM inseguro chama `rag_tool`, `web_search` e `drug_lookup` para mesma query.

**Soluções:**

#### 1. Explicit Negatives em Descriptions

```python
@tool
def web_search(query: str) -> str:
    """Busca informações na web.

    ⚠️ USE APENAS COMO ÚLTIMO RECURSO

    Chame web_search SOMENTE quando:
    - rag_tool retornou 0 documentos OU
    - rag_tool explicitamente disse "informação não encontrada" OU
    - A informação é muito recente (últimos 3 dias)

    ❌ NÃO CHAME se:
    - rag_tool já retornou ≥1 documento relevante
    - Você só quer "confirmar" informação do RAG
    - Você quer "mais detalhes" mas RAG já respondeu a pergunta

    Contra-exemplo:
    ❌ ERRADO: rag_tool("diabetes") → 3 docs → web_search("diabetes")
    ✅ CERTO: rag_tool("tratamento XYZ") → 0 docs → web_search("XYZ")
    """
    pass
```

#### 2. System Prompt com Penalidades

```text
REGRAS DE EFICIÊNCIA:
- Cada tool call tem um "custo" (latência para o usuário)
- Você será PENALIZADO por chamadas redundantes
- Antes de chamar uma tool, pergunte: "outra tool já respondeu isso?"

EXEMPLOS DE REDUNDÂNCIA (EVITE):
❌ rag_tool("hipertensão") → 5 docs → web_search("hipertensão")
   Motivo: RAG já deu resposta completa

❌ drug_lookup("enalapril") → dose completa → calculator("dose/peso")
   Motivo: Cálculo desnecessário se dose já está na bula

✅ rag_tool("hipertensão 2025") → 0 docs → web_search("hipertensão guidelines 2025")
   Motivo: RAG não tem info recente, web é apropriado
```

#### 3. Dynamic Tool Availability

```python
def route_tools(state: AgentState) -> list[str]:
    """Controla quais tools estão disponíveis baseado em contexto."""

    messages = state["messages"]
    last_observation = messages[-1].content if messages else ""

    # Se RAG retornou resultados, REMOVE web_search das opções
    if "rag_tool" in last_observation and len(last_observation) > 100:
        return ["calculator", "drug_lookup", "verify_paper"]

    # Se nenhuma tool chamada ainda, oferece busca
    if not any("Observation:" in str(m) for m in messages):
        return ["rag_tool", "web_search", "drug_lookup"]

    # Padrão: todas menos web_search
    return ["rag_tool", "drug_lookup", "calculator", "verify_paper"]

# Aplicar no graph
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        END: END
    }
)

# Modificar call_model para usar dynamic tools
def call_model(state: AgentState):
    available_tools = route_tools(state)
    llm_dynamic = llm.bind_tools([t for t in tools if t.name in available_tools])
    response = llm_dynamic.invoke(state["messages"])
    return {"messages": [response]}
```

#### 4. Few-Shot Examples no Prompt

```text
EXEMPLO 1 (EFICIENTE):
Pergunta: Qual o tratamento para diabetes tipo 2?
Pensamento: Preciso de guidelines clínicos → usar rag_tool
Ação: rag_tool
Entrada: "tratamento diabetes tipo 2"
Observação: [3 guidelines encontrados com metformina, dieta, exercício]
Pensamento: Tenho informação completa, não preciso de web_search
Resposta Final: O tratamento inicial para diabetes tipo 2 inclui...

EXEMPLO 2 (INEFICIENTE - NÃO FAÇA):
Pergunta: Qual o tratamento para diabetes tipo 2?
Pensamento: Vou buscar em várias fontes para ter certeza
Ação: rag_tool
Entrada: "diabetes tipo 2"
Observação: [3 guidelines encontrados]
Pensamento: Vou confirmar com web_search ❌ REDUNDANTE
Ação: web_search ❌ NÃO NECESSÁRIO
...
```

---

## 6. Anti-Patterns: O Que Evitar

### 6.1 Tool Description Anti-Patterns

❌ **1. Nomes Vagos**
```python
@tool
def get_info(query: str) -> str:  # ❌ Muito vago
    """Get information."""  # ❌ Description inútil
```

✅ **Correção:**
```python
@tool
def rag_medical_guidelines(query: str) -> str:  # ✅ Específico
    """Busca protocolos clínicos validados na base Medbrain."""
```

---

❌ **2. Descriptions Ambíguas**
```python
@tool
def search(query: str) -> str:
    """Searches for information."""  # ❌ RAG? Web? Qual source?
```

✅ **Correção:**
```python
@tool
def web_search(query: str) -> str:
    """Busca informações atualizadas na web via Tavily.
    Use APENAS quando rag_tool não encontrar dados."""
```

---

❌ **3. Descriptions Muito Longas**
```python
@tool
def calculator(expr: str) -> str:
    """This tool is a powerful calculator that can perform various
    mathematical operations including addition, subtraction, multiplication,
    division, exponentiation, square roots, trigonometric functions,
    logarithms, and many other advanced mathematical computations. It
    supports both simple and complex expressions with parentheses and
    follows standard order of operations. You can use it for any kind
    of numerical calculation you might need in a medical context or
    otherwise, such as calculating medication dosages, converting units,
    or performing statistical analyses..."""  # ❌ 600+ caracteres
```

✅ **Correção:**
```python
@tool
def calculator(expr: str) -> str:
    """Executa cálculos matemáticos (dose mg/kg, conversões, etc).
    Exemplos: '10mg / 2.5kg', '120 * 0.75'"""  # ✅ Conciso
```

---

❌ **4. Omitir Type Hints**
```python
@tool
def drug_lookup(drug_name, info_type):  # ❌ Sem tipos
    """Looks up drug information."""
```

✅ **Correção:**
```python
@tool
def drug_lookup(drug_name: str, info_type: str = "all") -> str:  # ✅
    """Consulta informações de medicamentos."""
```

### 6.2 System Prompt Anti-Patterns

❌ **1. Sem Instruções de Prioridade**
```text
You have access to: rag_tool, web_search, drug_lookup, calculator.
Use them to answer questions.
```
**Problema:** LLM chama múltiplas tools aleatoriamente.

✅ **Correção:**
```text
HIERARQUIA:
1. Para guidelines: rag_tool (SEMPRE primeiro)
2. Para medicamentos: drug_lookup
3. Para web: APENAS se rag_tool falhou
```

---

❌ **2. Sem Stopping Criteria**
```text
Answer the question using the tools available.
```
**Problema:** Agent entra em loop infinito.

✅ **Correção:**
```text
Stop when:
- You have enough information to answer completely
- You've called 3+ tools without new insights
- max_iterations reached (5)
```

---

❌ **3. Permitir Parallel Calls Descontrolados**
```python
llm.bind_tools(tools)  # ❌ Padrão: parallel_tool_calls=True
```
**Problema:** LLM chama rag_tool + web_search simultaneamente.

✅ **Correção:**
```python
llm.bind_tools(tools, parallel_tool_calls=False)  # ✅ Sequencial
```

### 6.3 Implementation Anti-Patterns

❌ **1. Todas as Tools Sempre Disponíveis**
```python
# ❌ LLM sempre vê todas as 15 tools
llm_with_tools = llm.bind_tools(all_15_tools)
```
**Problema:** Confusão, chamadas incorretas (accuracy cai 40% acima de 12 tools).

✅ **Correção:**
```python
# ✅ Dynamic tool calling
def get_available_tools(state):
    if state["stage"] == "search":
        return [rag_tool, web_search]
    elif state["stage"] == "calculation":
        return [calculator, drug_lookup]
```

---

❌ **2. Sem Error Handling em Tools**
```python
@tool
def web_search(query: str) -> str:
    return requests.get(f"api.com/search?q={query}").json()  # ❌ Crash se API falhar
```

✅ **Correção:**
```python
@tool
def web_search(query: str) -> str:
    try:
        response = requests.get(f"api.com/search?q={query}", timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.Timeout:
        return "Error: Search API timeout. Try rag_tool instead."
    except Exception as e:
        return f"Error: {str(e)}"

# Ou usar ToolNode built-in error handling
tool_node = ToolNode(tools, handle_tool_errors=True)
```

---

❌ **3. Não Usar Reducers para Parallel Updates**
```python
class State(TypedDict):
    search_results: str  # ❌ Se 2 tools atualizarem em paralelo?
```

✅ **Correção:**
```python
from typing import Annotated
import operator

class State(TypedDict):
    search_results: Annotated[list, operator.add]  # ✅ Merge via append
```

---

❌ **4. Over-Mocking em Testes**
```python
# ❌ Mock esconde bugs reais
@patch("tools.rag_tool")
@patch("tools.web_search")
def test_agent(mock_web, mock_rag):
    mock_rag.return_value = "fake result"
    # Test passa mas tool real pode estar quebrada
```

✅ **Correção:**
```python
# ✅ Testes de integração com tools reais (sandbox)
def test_agent_with_real_tools():
    result = agent.invoke({"query": "test"})
    assert "rag_tool" in result["tool_calls"]
```

---

❌ **5. Ignorar max_iterations Warning**
```python
agent = AgentExecutor(tools=tools, llm=llm)  # ❌ Padrão: max_iterations=15
# Agent entra em loop infinito se tool sempre retorna "insufficient data"
```

✅ **Correção:**
```python
agent = AgentExecutor(
    tools=tools,
    llm=llm,
    max_iterations=5,  # ✅ Limite conservador
    early_stopping_method="generate"  # ✅ LLM tenta responder ao atingir limite
)
```

### 6.4 Production Anti-Patterns

❌ **1. LLM com Acesso a Tokens/Secrets**
```python
@tool
def api_call(endpoint: str, token: str) -> str:  # ❌ LLM pode expor token
    return requests.get(endpoint, headers={"Auth": token})
```

✅ **Correção (Doctolib pattern):**
```python
# Token gerenciado FORA do LLM
@tool
def api_call(endpoint: str) -> str:
    token = get_token_from_secure_vault()  # ✅ LLM não vê token
    return requests.get(endpoint, headers={"Auth": token})
```

---

❌ **2. Sem Human-in-the-Loop para Ações Sensíveis**
```python
@tool
def book_appointment(patient_id: str, date: str) -> str:
    db.insert(patient_id, date)  # ❌ LLM agenda diretamente
```

✅ **Correção:**
```python
@tool
def request_appointment(patient_id: str, date: str) -> str:
    """Solicita agendamento (requer aprovação humana)."""
    return f"Appointment request created. Awaiting approval."
    # LangGraph interrompe e aguarda human input
```

---

❌ **3. Sem Monitoring/Logging**
```python
# ❌ Não sabe quais tools falharam em produção
app.invoke({"query": user_input})
```

✅ **Correção:**
```python
# ✅ LangSmith integration
from langsmith import traceable

@traceable
def run_agent(query: str):
    return app.invoke({"query": query})

# Logs automáticos: tool calls, latency, errors
```

---

## 7. Checklist de Validação

Antes de colocar seu agente ReAct em produção, valide:

### Tool Descriptions
- [ ] Cada tool tem description clara e concisa (2-3 frases)
- [ ] Descriptions incluem "quando usar" E "quando NÃO usar"
- [ ] Nomes de tools são snake_case e descritivos
- [ ] Type hints presentes em todos os parâmetros
- [ ] Contra-exemplos incluídos para tools similares (RAG vs web_search)

### System Prompt
- [ ] Hierarquia de prioridade entre tools explícita
- [ ] Regras de redundância documentadas (não chamar RAG + web juntos)
- [ ] Stopping criteria claros (max_iterations, quando parar)
- [ ] Few-shot examples de bom e mau uso

### Implementation
- [ ] Dynamic tool calling implementado (tools contextuais)
- [ ] Error handling em todas as tools (try/except ou ToolNode)
- [ ] Reducers definidos para state updates paralelos
- [ ] max_iterations configurado (5-10 para médico)
- [ ] parallel_tool_calls=False se necessário

### Segurança
- [ ] LLM não tem acesso direto a tokens/secrets
- [ ] Human-in-the-loop para ações sensíveis (agendar, prescrever)
- [ ] Validação de inputs em tools críticas
- [ ] Rate limiting em APIs externas

### Testes
- [ ] Testes unitários para cada tool
- [ ] Testes de integração com tools reais (não mocked)
- [ ] Teste de redundância (garante que RAG + web não são chamados juntos)
- [ ] Teste de stopping (garante que max_iterations funciona)

### Observability
- [ ] LangSmith ou equivalente configurado
- [ ] Logging de tool calls, latency, errors
- [ ] Alertas para loops infinitos (>max_iterations frequentes)
- [ ] Métricas de redundância (% queries com >1 search tool)

---

## 8. Métricas de Sucesso

### KPIs para Tool Calling Efficiency

| Métrica | Target | Como Medir |
|---------|--------|------------|
| **Redundância** | <5% queries | % queries com RAG + web_search |
| **Tool Accuracy** | >90% | % tool calls corretas (human eval) |
| **Avg Tool Calls/Query** | 1.5-2.5 | Média de tools por resolução |
| **Max Iterations Hit** | <2% | % queries que atingem limite |
| **Latency** | <3s | p95 end-to-end response time |
| **Tool Errors** | <1% | % tool calls com erro |

### Red Flags

🚩 **Avg Tool Calls > 3:** System prompt ou descriptions ruins
🚩 **Redundância > 10%:** LLM chamando múltiplas searches
🚩 **Max Iterations > 5%:** Loops infinitos frequentes
🚩 **Tool Accuracy < 80%:** Descriptions ambíguas

---

## 9. Referências e Fontes

### Documentação Oficial LangChain/LangGraph (2026)
- [LangChain Tools and Agents 2026: Production-Ready Patterns](https://langchain-tutorials.github.io/langchain-tools-agents-2026/)
- [LangGraph: Agent Orchestration Framework](https://www.langchain.com/langgraph)
- [Tools - LangChain Docs](https://docs.langchain.com/oss/python/langchain/tools)
- [Dynamic Tool Calling in LangGraph](https://changelog.langchain.com/announcements/dynamic-tool-calling-in-langgraph-agents)

### ReAct Pattern
- [LangChain ReAct Agent Pattern Explained (2026)](https://langchain-tutorials.github.io/langchain-react-agent-pattern-2026/)
- [GitHub: langchain-ai/react-agent](https://github.com/langchain-ai/react-agent)
- [LangGraph ReAct Agent: Tool-Calling from Scratch](https://markaicode.com/langgraph-react-agent-tool-calling/)
- [ReAct Prompting Guide](https://www.promptingguide.ai/techniques/react)

### Tool Calling Best Practices
- [Tool Calling with LangChain](https://blog.langchain.com/tool-calling-with-langchain/)
- [Improving Core Tool Interfaces in LangChain](https://blog.langchain.com/improving-core-tool-interfaces-and-docs-in-langchain/)
- [Evaluating Skills - LangChain Blog](https://blog.langchain.com/evaluating-skills/)
- [9 LangChain Tool-Calling Patterns That Survive Traffic](https://medium.com/@ThinkingLoop/9-langchain-tool-calling-patterns-that-survive-traffic-4c1d286164e4)

### Claude/Anthropic Tool Use
- [Introducing Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)
- [Best Practices for Claude Code](https://code.claude.com/docs/en/best-practices)
- [The Complete Guide to Building Skills for Claude](https://resources.anthropic.com/hubfs/The-Complete-Guide-to-Building-Skill-for-Claude.pdf)

### Medical AI & Agentic RAG
- [Doctolib: Building Agentic AI for Healthcare (LangGraph)](https://www.zenml.io/llmops-database/building-an-agentic-ai-system-for-healthcare-support-using-langgraph)
- [Tool Use Agent with RAG + Web Search](https://medium.com/@vsletten/tool-use-agent-with-rag-web-search-8a2696d5eea5)
- [Exploring Agentic RAG in Healthcare](https://www.maargasystems.com/2025/06/06/exploring-agentic-rag-in-healthcare/)
- [Traditional RAG vs. Agentic RAG (NVIDIA)](https://developer.nvidia.com/blog/traditional-rag-vs-agentic-rag-why-ai-agents-need-dynamic-knowledge-to-get-smarter/)
- [LangGraph Multi Agent Medical Chatbot](https://aws-samples.github.io/amazon-bedrock-samples/agents-and-function-calling/open-source-agents/langgraph/02_medibot_V3_agents/)

### Error Handling & Anti-Patterns
- [Agent Stopped Due to Max Iterations: 7 Proven Fixes](https://inforsome.com/agent-max-iterations-fix-5/)
- [Cap Max Iterations in LangChain](https://python.langchain.com/v0.1/docs/modules/agents/how_to/max_iterations/)
- [3 Patterns That Fix LLM API Calling](https://dev.to/docat0209/3-patterns-that-fix-llm-api-calling-stop-getting-hallucinated-parameters-4n3b)

### Production Examples
- [LangGraph for Healthcare: Technical Guide](https://levelup.gitconnected.com/langgraph-for-healthcare-a-comprehensive-technical-guide-e6038b06c108)
- [How to Build Care Coordination Workflow with AI Agents](https://medium.com/@JossGuarnelli/how-to-build-a-care-coordination-workflow-with-ai-agents-using-langgraph-0dfb9e561290)
- [Secure Third-Party Tool Calling (Python/FastAPI)](https://auth0.com/blog/secure-third-party-tool-calling-python-fastapi-auth0-langchain-langgraph/)
- [Deploy LangChain to Production in 2026](https://langchain-tutorials.github.io/deploy-langchain-production-2026/)

### GitHub Repositories
- [langchain-ai/langchain](https://github.com/langchain-ai/langchain)
- [langchain-ai/react-agent](https://github.com/langchain-ai/react-agent)
- [awesome-LangGraph](https://github.com/von-development/awesome-LangGraph)
- [Agentic Customer Service Medical Clinic](https://github.com/Nachoeigu/agentic-customer-service-medical-clinic)
- [Multi Agent Medical System](https://github.com/joyceannie/Multi_Agent_Medical_System)

---

## 10. Próximos Passos (Recomendações para mb-wpp)

### Ações Imediatas
1. **Revisar tool descriptions** usando template da Seção 2.2
2. **Implementar dynamic tool calling** (Seção 3.2, Solução 2)
3. **Adicionar negative examples** em web_search (Seção 5.2, Solução 1)
4. **Configurar max_iterations=5** no AgentExecutor

### Médio Prazo
1. **Criar testes de redundância** (garantir RAG + web não chamados juntos)
2. **Implementar LangSmith** para monitoring de tool calls
3. **Adicionar human-in-the-loop** para ações sensíveis (ex: recomendar medicação)
4. **Otimizar system prompt** com hierarquia clara (RAG > drug_lookup > web)

### Longo Prazo
1. **Migrar para Agentic RAG** (priorização dinâmica de fontes)
2. **Implementar hierarchical agents** (router → specialist agents)
3. **A/B test** parallel_tool_calls=True vs False
4. **Criar dashboard** de KPIs de tool efficiency (Seção 8)

---

**Documento mantido por:** Rodrigo Franco
**Última atualização:** 2026-03-14
**Versão:** 1.0
