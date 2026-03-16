# Decisão Técnica: Arquitetura do Medbrain WhatsApp

Fala! Tudo bem?

Estou organizando aqui os pontos técnicos que levantei sobre a arquitetura do mb-wpp para a gente discutir juntos e chegar na melhor decisão. Analisei com bastante profundidade tanto o projeto `search-medway-langgraph` que vocês montaram quanto a arquitetura que eu estava planejando com Claude SDK direto. Trouxe prós, contras e dados para cada abordagem — a ideia é que a gente avalie juntos o que faz mais sentido.

---

## 1. Contexto: os dois caminhos possíveis

**Caminho A — LangGraph + LangChain** (como no projeto search-medway-langgraph)
- Orquestração via LangGraph com StateGraph, nós e edges
- LangChain como wrapper para chamadas LLM (ChatOpenAI, ChatAnthropicVertex)
- Checkpointing nativo via AsyncPostgresSaver
- Padrão já adotado pela equipe em outros projetos
- LangChain 1.0 e LangGraph 1.0 lançados em outubro/2025 — ambos estáveis e com compromisso de zero breaking changes até 2.0
- Usado em produção por empresas como Uber, LinkedIn e Klarna

**Caminho B — Claude SDK Direto (anthropic[vertex])**
- Chamadas diretas à API do Claude via SDK oficial da Anthropic
- Pipeline de processamento implementado como funções async encadeadas
- Tool Use nativo do Claude (o modelo decide quais ferramentas usar)
- Persistência de estado manual via Supabase

---

## 2. O que o mb-wpp precisa resolver

Para contextualizar a decisão, o fluxo principal do WhatsApp é um pipeline de ~10 etapas:

```
Webhook → Message Buffer (debounce) → Identificação do Usuário →
Rate Limiting → Processamento de Áudio/Imagem → Carregamento de Contexto →
Orquestração Claude (Tool Use) → Execução de Tools → Formatação → Envio WhatsApp
```

Algumas características relevantes:
- O fluxo principal é **sequencial** (não tem bifurcações complexas entre agentes)
- O "roteamento inteligente" acontece **dentro do Claude** via Tool Use — o modelo decide quais ferramentas chamar (RAG, bulas, calculadoras, quiz)
- Precisamos de **Prompt Caching** porque system prompt + definições de tools são grandes e repetitivos
- Target de latência: P95 < 8s para texto
- Target de custo: < $0.03 por conversa

---

## 3. Análise comparativa

### 3.1 Orquestração e fluxo de trabalho

**LangGraph**
- Projetado para fluxos com **múltiplas ramificações dinâmicas** e **múltiplos agentes** que se comunicam entre si
- O StateGraph permite definir nós e transições condicionais de forma declarativa — ótimo para cenários complexos
- Funciona muito bem no cenário do `search-medway-langgraph`, onde o Router classifica intent e direciona para medical/search/stats
- Para pipelines mais lineares, a abstração pode não agregar tanto — mas não atrapalha, é apenas mais estrutura do que o necessário

Uma observação: no próprio projeto de vocês, o `medbrain_responds/graph.py` e o `medbrain_insights/graph.py` implementam fluxos sequenciais diretos, sem usar a estrutura de grafo do LangGraph. Só o `conversational_medbrain/graph.py` de fato usa o grafo com routing. Isso indica que o próprio time já identifica cenários onde o pipeline linear é mais natural — o que é totalmente válido.

**Claude SDK Direto**
- O Tool Use nativo do Claude já resolve a questão de "para onde rotear" — o modelo analisa a mensagem e decide chamar `rag_search`, `drug_lookup`, `quiz_generate`, etc.
- Para um pipeline sequencial como o do WhatsApp, funções async encadeadas são mais diretas
- Menos abstração = menos camadas para debugar quando algo dá errado

**Ponto para discussão:** O mb-wpp precisa de orquestração multi-agente complexa ou o Tool Use nativo do Claude é suficiente para o roteamento? Se no futuro precisarmos de múltiplos agentes especializados (como vocês já fazem no conversational_medbrain com router → medical/search/stats), LangGraph teria vantagem clara.

---

### 3.2 Prompt Caching e custo

Esse é um ponto técnico relevante. O mb-wpp vai ter um system prompt extenso (~2000-3000 tokens) mais definições de tools (~1500-2000 tokens). Com Prompt Caching da Anthropic, cache reads custam apenas 10% do preço normal — uma economia de 90%.

**Dados de pricing atuais (Claude Sonnet, fev/2026):**
- Input normal: $3.00/MTok
- Cache write (5min TTL): $3.75/MTok (1.25x)
- Cache read: $0.30/MTok (0.10x) ← 90% de economia
- Fonte: https://platform.claude.com/docs/en/about-claude/pricing

**Estimativa de custo** (para ~1000 conversas/dia, ~5 turnos cada = 150k requests/mês):

Considerando ~4.500 tokens de system prompt + tools repetidos em cada request:

| Cenário | Custo mensal (só system prompt) | Economia |
|---------|------|----------|
| Sem Prompt Caching | ~$1.800 | — |
| Com Prompt Caching (~96% cache hit) | ~$260 | ~$1.540/mês |

Essa economia é relevante e vale para **ambas** as abordagens.

**Como cada abordagem implementa:**

**SDK direto** — controle explícito sobre exatamente o que é cacheado:
```python
response = await client.messages.create(
    model="claude-sonnet-4-20250514",
    system=[
        {
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"}  # posição exata do breakpoint
        }
    ],
    tools=TOOL_DEFINITIONS,
    messages=[...]
)
```

**LangChain** — via `AnthropicPromptCachingMiddleware`:
```python
from langchain_anthropic import ChatAnthropic
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware

agent = create_agent(
    model=ChatAnthropic(model="claude-sonnet-4-20250514"),
    system_prompt="...",
    middleware=[AnthropicPromptCachingMiddleware(ttl="5m")]
)
```

O middleware funciona e é suportado oficialmente. Ele coloca os breakpoints de cache automaticamente no prefixo da conversa. A diferença prática é:
- **SDK direto**: você escolhe manualmente onde colocar cada breakpoint de cache
- **Middleware LangChain**: os breakpoints são posicionados automaticamente pela estratégia do middleware

Para o nosso caso, onde queremos cachear system prompt + tools, ambos devem funcionar bem. Há alguns issues abertos no GitHub do LangChain com edge cases do middleware (ex: issue #33709 sobre conflito com fallback para modelos não-Anthropic, e issue #34542 sobre interação com code_execution), mas para o cenário padrão de caching de system prompt, não devem ser um problema.

**Ponto para discussão:** Podemos fazer um teste rápido das duas abordagens e comparar se o custo real é equivalente? Seria o melhor jeito de tirar a dúvida.

---

### 3.3 State management e persistência de conversas

**LangGraph** tem vantagem aqui por resolver isso out-of-the-box:

```python
# Checkpointing automático — estado persiste entre mensagens
async with AsyncPostgresSaver.from_conn_string(DB_URI) as checkpointer:
    graph = workflow.compile(checkpointer=checkpointer)
    state = await graph.ainvoke(
        ConversationalState(messages=[new_message]),
        config={"configurable": {"thread_id": conversation_id}}
    )
```

Retomar uma conversa é trivial — o LangGraph carrega automaticamente o histórico de mensagens e o estado do grafo. Inclusive, o LangGraph 1.0 trouxe melhorias significativas nessa área: estado durável que sobrevive a restarts de servidor, padrões de human-in-the-loop nativos, e workflows que podem durar múltiplas sessões.

**Com SDK direto**, precisamos implementar manualmente:

```python
# Carregar histórico
messages = await supabase.table("messages") \
    .select("*").eq("conversation_id", conv_id) \
    .order("created_at").execute()

# Enviar para Claude com histórico
response = await client.messages.create(
    model="claude-sonnet-4-20250514",
    system=SYSTEM_PROMPT,
    messages=format_history(messages.data) + [new_message],
    tools=TOOLS
)

# Salvar resposta
await supabase.table("messages").insert({...}).execute()
```

Não é complexo (~50-80 linhas), mas é código que precisa ser escrito, testado e mantido. E o LangGraph resolve isso sem escrever uma linha.

---

### 3.4 Ecossistema e maturidade

**LangGraph/LangChain:**
- LangChain 1.0 e LangGraph 1.0 (outubro/2025) — estáveis, com compromisso de zero breaking changes até 2.0
- `langchain-mcp-adapters` — integração MCP pronta
- Suporte a múltiplos providers (OpenAI, Anthropic, Vertex, etc.)
- Structured output, message types, e utilidades diversas
- Comunidade grande e ativa
- Usado em produção por Uber, LinkedIn, Klarna
- Um ponto de atenção: o pacote `langchain-community` (0.4) ainda pode ter breaking changes em minor releases, por ser mantido pela comunidade — diferente dos pacotes core que são estáveis

**Claude SDK:**
- 1 dependência principal: `anthropic[vertex]`
- API estável com versionamento semântico
- Menos features "prontas", mais controle manual
- Escopo menor = menos superfície para breaking changes

---

### 3.5 Debugging e observabilidade

**LangChain/LangGraph:**
- Integração nativa com LangSmith para tracing end-to-end
- Quando o problema está dentro das abstrações do LangChain (ex: como o middleware monta o request), pode ser mais trabalhoso debugar
- Mas com LangSmith, a visibilidade de cada step é excelente

**SDK Direto:**
- httpx logging mostra exatamente o request/response enviado à API
- Integração com Langfuse/LangSmith via decorators (manual, mas funcional)
- Stack trace mais curto quando algo dá errado

Na prática, com as ferramentas certas de observabilidade (LangSmith no caso do LangGraph, Langfuse no caso do SDK direto), ambos permitem visibilidade adequada. A diferença é mais de ergonomia do que de capacidade.

---

### 3.6 Alinhamento com a equipe e manutenibilidade

Independente das comparações técnicas pontuais, o fator equipe é muito relevante:

- **Code review cross-team** — Se todo mundo conhece LangGraph, review é mais rápido e qualitativo
- **Onboarding** — Novo dev entra e já conhece os patterns
- **Manutenção** — Se eu sair do projeto, quem assume precisa conhecer a stack
- **Reutilização** — Agents, prompts, e patterns podem ser compartilhados entre projetos
- **Suporte mútuo** — Quando alguém trava num problema, outro do time pode ajudar se conhece o framework

Esse é um fator que não aparece em benchmark nenhum, mas impacta diretamente a velocidade e qualidade de entrega.

---

## 4. Resumo das diferenças

| Aspecto | LangGraph + LangChain | Claude SDK Direto |
|---------|----------------------|-------------------|
| **Orquestração** | Declarativa (grafo), ótima para fluxos complexos | Imperativa (funções), mais direta para fluxos lineares |
| **State/Checkpointing** | Nativo, out-of-the-box | Manual (~50-80 linhas) |
| **Prompt Caching** | Via middleware (funciona, com alguns edge cases documentados) | Controle explícito (manual, granular) |
| **Dependências** | ~6-8 pacotes (langchain, langgraph, adapters...) | 1 pacote (anthropic[vertex]) |
| **Estabilidade** | 1.0 estável desde out/2025 | Estável (semver) |
| **Debugging** | LangSmith integrado, mais camadas de abstração | httpx direto, stack trace curto |
| **Multi-provider** | Nativo (OpenAI, Anthropic, Vertex, etc.) | Apenas Anthropic |
| **MCP** | langchain-mcp-adapters pronto | Implementação manual |
| **Alinhamento equipe** | Total | Cria stack separada |
| **Maturidade em produção** | Uber, LinkedIn, Klarna | Anthropic Cookbook, projetos menores |

---

## 5. Possibilidades que vejo

### Opção 1: LangGraph completo
Alinhar 100% com o padrão da equipe. Usar LangGraph para tudo, incluindo o pipeline do WhatsApp.

- (+) Máximo alinhamento organizacional
- (+) Checkpointing e state management gratuitos
- (+) MCP adapters prontos
- (+) Ecossistema maduro (1.0, empresas grandes em produção)
- (-) Mais abstração do que um pipeline linear precisa — não é problema, mas é overhead conceitual

### Opção 2: Claude SDK direto completo
Seguir a arquitetura originalmente planejada, sem LangChain/LangGraph.

- (+) Controle granular total (Prompt Caching, Tool Use, streaming)
- (+) Pipeline mais enxuto, menos dependências
- (+) Debugging mais direto
- (-) State management manual (trabalho adicional)
- (-) MCP manual (trabalho adicional)
- (-) Desalinhado com a stack da equipe — impacta code review, onboarding, manutenção

### Opção 3: Abordagem híbrida
Usar LangGraph **onde ele agrega valor real** (gerenciamento de conversação stateful, retomada de sessões) e Claude SDK direto **no pipeline de processamento** (processamento de áudio, imagem, formatação).

- (+) Cada ferramenta onde ela brilha
- (+) Aproveitamos checkpointing e MCP do LangGraph
- (+) Mantemos controle direto onde precisamos
- (-) Dois patterns no mesmo projeto — pode gerar confusão na manutenção

---

## 6. Pontos complementares — Stack e infraestrutura

Além da questão LangGraph vs SDK, tem alguns pontos de infraestrutura que acho que vale a gente alinhar:

### Framework: FastAPI vs Django

A arquitetura que eu estava planejando usa FastAPI. Se a Medway padroniza Django, pode fazer sentido avaliarmos Django com `adrf` (async views) para manter coerência. Para o volume que esperamos (~100 req/s), a diferença de performance entre os dois não é relevante. O ganho de alinhar seria familiaridade e manutenibilidade.

### Hosting

O plano original coloca o mb-wpp em Railway. Se a infraestrutura da Medway já está em GCP (provável, dado o uso de Vertex AI), rodar na mesma infra facilita networking (acesso a services internos, MCP servers, etc.) e evita custos duplicados.

### RAG: Pinecone vs SmartContentService

Vi que vocês já têm o SmartContentService com busca vetorial + reranking. O plano do mb-wpp era usar Pinecone separado. Pode fazer sentido reutilizar o SmartContentService para evitar duplicação de índice e custo de embedding. O que acham?

---

## 7. Próximos passos sugeridos

1. **Testar Prompt Caching na prática** — Comparar um request via SDK direto com `cache_control` e outro via middleware do LangChain, verificar se os cache reads aparecem corretamente em ambos e se os custos são equivalentes.
2. **Avaliar juntos** qual opção (1, 2 ou 3) faz mais sentido considerando tanto a parte técnica quanto o contexto da equipe e da organização.
3. **Alinhar infraestrutura** — Definir framework (FastAPI vs Django), hosting (Railway vs infra Medway) e serviço de RAG.

Fico no aguardo para a gente discutir. Qualquer ponto que não ficou claro ou que eu tenha deixado de considerar, me avisa!

Abraço

---

### Referências consultadas

- [Pricing Claude API](https://platform.claude.com/docs/en/about-claude/pricing) — Preços atualizados de input, output e cache
- [Prompt Caching - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) — Documentação oficial de Prompt Caching
- [LangChain 1.0 e LangGraph 1.0 GA](https://blog.langchain.com/langchain-langgraph-1dot0/) — Anúncio de estabilidade
- [LangGraph 1.0 Release Notes](https://changelog.langchain.com/announcements/langgraph-1-0-is-now-generally-available) — Features de produção
- [AnthropicPromptCachingMiddleware](https://reference.langchain.com/python/langchain-anthropic/middleware/prompt_caching/AnthropicPromptCachingMiddleware) — Referência da API de middleware
- [LangChain Release Policy](https://docs.langchain.com/oss/python/release-policy) — Política de breaking changes
- [Issue #33709](https://github.com/langchain-ai/langchain/issues/33709) — Middleware + model fallback
- [Issue #33635](https://github.com/langchain-ai/langchain/issues/33635) — Prompt caching em create_agent
