---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
inputDocuments:
  - prd.md
  - architecture.md
  - decisao-tecnica-langgraph-vs-claude-sdk.md
---

# mb-wpp - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for mb-wpp, decomposing the requirements from the PRD, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

**Interação com Usuário via WhatsApp (FR1-FR10):**

- FR1: Aluno pode enviar perguntas por texto pelo WhatsApp e receber respostas
- FR2: Aluno pode enviar mensagens de áudio e receber respostas baseadas na transcrição do áudio
- FR3: Aluno pode enviar imagens (fotos de questões, exames, casos) e receber análise baseada no conteúdo visual
- FR4: Aluno pode fornecer feedback sobre a qualidade da resposta recebida (positivo/negativo)
- FR5: Aluno pode adicionar um comentário opcional após fornecer feedback, explicando o motivo da avaliação
- FR6: O sistema pode acumular mensagens rápidas consecutivas antes de processar (debounce)
- FR7: O sistema pode responder de forma informativa quando recebe um tipo de mensagem não suportado (sticker, localização, documento, contato)
- FR8: O sistema pode dividir respostas que excedem o limite do WhatsApp em mensagens sequenciais, mantendo coerência e formatação
- FR9: O sistema pode indicar ao usuário que está processando sua mensagem enquanto elabora a resposta
- FR10: Novo usuário pode receber mensagem de boas-vindas na primeira interação, sem necessidade de cadastro ou formulário

**Consulta Médica Inteligente (FR11-FR17):**

- FR11: Aluno pode fazer perguntas médicas e receber respostas contextualizadas com citações de fontes verificáveis
- FR12: O sistema pode buscar informações na base de conhecimento médica e citar as fontes utilizadas
- FR13: O sistema pode buscar informações na web quando a base de conhecimento não tem cobertura, citando fontes
- FR14: Aluno pode consultar informações sobre bulas de medicamentos (indicações, dosagens, interações)
- FR15: Aluno pode utilizar calculadoras médicas fornecendo dados por texto ou áudio
- FR16: O sistema pode selecionar automaticamente as ferramentas adequadas para cada pergunta e utilizá-las (inclusive em paralelo) para compor a resposta
- FR17: O sistema pode incluir disclaimers médicos apropriados nas respostas, reforçando que é ferramenta de apoio e não substitui avaliação médica

**Formatação e Apresentação de Respostas (FR18-FR19):**

- FR18: O sistema pode formatar respostas de forma estruturada e otimizada para leitura no WhatsApp
- FR19: O sistema pode adaptar o formato da resposta ao tipo de conteúdo (explicação, cálculo, lista, comparação, questão)

**Identificação e Controle de Acesso (FR20-FR24):**

- FR20: O sistema pode identificar o tipo de usuário (aluno Medway, não-aluno) a partir do número de telefone
- FR21: O sistema pode disponibilizar funcionalidades diferenciadas conforme o tipo de usuário
- FR22: Aluno pode visualizar quantas perguntas restam no dia e quando o limite reseta
- FR23: O sistema pode limitar o número de interações diárias por tipo de usuário
- FR24: O sistema pode proteger contra burst de mensagens (anti-spam)

**Quiz e Prática Ativa (FR25-FR26):**

- FR25: Aluno pode participar de quiz e prática ativa sobre temas médicos
- FR26: O sistema pode sugerir quiz de prática ativa ao final de respostas relevantes, estimulando a adesão

**Histórico e Contexto (FR27-FR28):**

- FR27: Aluno pode ter suas conversas anteriores consideradas no contexto das novas respostas
- FR28: O sistema pode armazenar e recuperar histórico de conversas por usuário

**Observabilidade e Monitoramento (FR29-FR32):**

- FR29: Equipe Medway pode rastrear o custo por request e por conversa
- FR30: Equipe Medway pode monitorar métricas de qualidade (satisfação, latência, taxa de erro)
- FR31: Equipe Medway pode receber alertas automáticos quando thresholds de erro são ultrapassados
- FR32: Equipe Medway pode acessar traces completos de cada interação para debugging e análise de qualidade

**Configuração e Operação (FR33-FR38):**

- FR33: Equipe Medway pode modificar parâmetros operacionais sem deploy (rate limits, timeouts, retries, mensagens)
- FR34: Equipe Medway pode editar o system prompt do Medbrain sem deploy
- FR35: Equipe Medway pode visualizar histórico de alterações do system prompt com autor e timestamp
- FR36: Equipe Medway pode reverter o system prompt para uma versão anterior
- FR37: Equipe Medway pode visualizar histórico de alterações de configurações operacionais (quem alterou, quando, valor anterior e novo)
- FR38: O sistema pode refletir mudanças de configuração em minutos, sem restart

**Resiliência e Recuperação (FR39-FR43):**

- FR39: O sistema pode realizar retry automático em caso de falha de serviço externo
- FR40: O sistema pode enviar mensagem amigável ao usuário quando uma falha persiste após retries
- FR41: O sistema pode fornecer resposta parcial quando uma ferramenta específica falha, informando ao usuário quais fontes não estavam disponíveis
- FR42: O sistema pode interromper chamadas a serviços em falha recorrente (circuit breaker)
- FR43: O sistema pode registrar erros com contexto completo (usuário, mensagem, tipo de erro, timestamp) para análise

**Migração e Continuidade (FR44-FR47):**

- FR44: O sistema pode operar em paralelo com o n8n durante a migração (Shadow Mode / Strangler Fig)
- FR45: O sistema pode preservar todos os dados existentes no Supabase durante a migração
- FR46: Equipe Medway pode controlar o percentual de tráfego roteado para o código novo vs n8n
- FR47: Equipe Medway pode comparar respostas geradas pelo código novo vs n8n durante Shadow Mode para validação de qualidade

### NonFunctional Requirements

**Performance (NFR1-NFR5):**

- NFR1: Latência P95 para respostas de texto < 8 segundos (end-to-end: webhook recebido → resposta enviada)
- NFR2: Latência P95 para respostas de áudio < 12 segundos (inclui transcrição Whisper)
- NFR3: Latência P95 para respostas de imagem < 15 segundos (inclui processamento Vision)
- NFR4: O sistema deve suportar pelo menos 50 conversas concorrentes sem degradação de performance
- NFR5: Message debounce deve acumular mensagens por no máximo 3 segundos (valor configurável via config dinâmica)

**Custo e Eficiência (NFR6-NFR9):**

- NFR6: Custo médio por conversa < $0.03 em regime estável (após otimizações de Prompt Caching)
- NFR7: Prompt Cache hit rate > 70% no M1, evoluindo para > 90% em 12 meses
- NFR8: Cost tracking com granularidade por request (precisão de ±5% sobre custo real da API)
- NFR9: Alertas automáticos quando gasto diário exceder threshold configurável

**Disponibilidade e Confiabilidade (NFR10-NFR14):**

- NFR10: Uptime do serviço >= 99.5% (M1) evoluindo para >= 99.9% (M3)
- NFR11: Taxa de erro do sistema < 2% (M1) evoluindo para < 0.5% (12 meses)
- NFR12: Tempo de recuperação automática (MTTR) < 5 minutos para falhas de serviços externos
- NFR13: Nenhuma mensagem de usuário deve ser silenciosamente perdida — toda mensagem recebe resposta ou mensagem de erro explícita
- NFR14: Webhook deve responder com 200 OK em < 3 segundos (requisito da Meta Cloud API para evitar reenvios)

**Segurança e Privacidade (NFR15-NFR20):**

- NFR15: Dados de conversas protegidos com Row Level Security (RLS) no Supabase — isolamento por usuário
- NFR16: Validação de assinatura em todos os webhooks recebidos (prevenção de injeção de mensagens)
- NFR17: Chaves de API e credenciais armazenadas exclusivamente em variáveis de ambiente, nunca no código-fonte
- NFR18: Dados pessoais tratados conforme LGPD (consentimento, finalidade, minimização de dados)
- NFR19: Logs de observabilidade não devem conter dados sensíveis do usuário em texto plano
- NFR20: Acesso à configuração dinâmica e edição de system prompt restrito à equipe autorizada

**Integrações e Dependências Externas (NFR21-NFR24):**

- NFR21: Timeout configurável individualmente por serviço externo (Claude, Pinecone, Whisper, Meta API)
- NFR22: Circuit breaker com threshold configurável para cada dependência externa
- NFR23: Estratégia de fallback documentada para cada dependência (comportamento quando cada serviço falha)
- NFR24: Compatibilidade com versão atual da WhatsApp Business API, com capacidade de migrar para novas versões

### Additional Requirements

**Da Arquitetura — Stack e Starter Template (ADR-001, ADR-002, ADR-004, ADR-009):**

- Python 3.12+ como linguagem principal (ADR-001)
- Django 5.1+ com DRF + adrf para async views (ADR-002) — alinhamento com equipe Medway
- App principal `workflows/` com sub-módulos: whatsapp/ (graph, nodes, tools), services/, providers/, middleware/, utils/
- ~55 arquivos mapeados em 4 camadas: Webhook (Django) → LangGraph StateGraph → Providers/Services → Data
- Toolchain: uv (package manager), pytest-django + pytest-asyncio (testes), Ruff (lint/format), mypy strict + django-stubs (types) (ADR-004)
- Dockerfile multi-stage com uv para GCP Cloud Run
- docker-compose.yml para desenvolvimento local (PostgreSQL 16 + Redis 7)
- CI/CD via GitHub Actions (Ruff, mypy, pytest) + GCP Cloud Build (cloudbuild.yaml) para deploy
- .env.example com todas as variáveis documentadas, django-environ para env management

**Da Arquitetura — LLM e Orquestração (ADR-010):**

- LangGraph 1.0 + LangChain 1.0 para orquestração (alinhamento com equipe, projeto referência search-medway-langgraph)
- StateGraph com 8 nós: identify_user → rate_limit → process_media → load_context → orchestrate_llm (+ tools loop) → format_response → send_whatsapp → persist
- ToolNode do LangChain para execução paralela de tools por padrão
- AsyncPostgresSaver para checkpointing automático (schema separado `langgraph`, AsyncConnectionPool singleton)
- AnthropicPromptCachingMiddleware para Prompt Caching (TTL 5min, cache reads a 10% do custo)
- CostTrackingCallback (LangChain AsyncCallbackHandler) para rastreamento granular de custo por request
- LangGraph RetryPolicy para nós com chamadas externas (backoff exponencial built-in)
- langchain-mcp-adapters para integração MCP pronta
- Streaming via stream_mode="messages" (token-by-token)

**Da Arquitetura — Multi-Provider LLM (ADR-006):**

- ChatAnthropicVertex como primary (70% menor custo, SLA 99.9%, same VPC)
- ChatAnthropic como fallback (mesmo modelo Claude, sem diferença de comportamento)
- model.with_fallbacks() do LangChain para switch automático (substitui circuit breaker custom)
- Sem OpenAI — apenas Claude em dois endpoints

**Da Arquitetura — Hosting e Infraestrutura (ADR-005):**

- GCP Cloud Run para todas as fases (mesma infra que Vertex AI)
- Mesma VPC — sem egress costs para Vertex AI
- GCP Secret Manager para credenciais (integrado com Cloud Run, rotação sem redeploy)
- Auto-scaling 0-to-N com --min-instances=1 (mitigar cold starts)
- Uvicorn como ASGI server (config/asgi.py)

**Da Arquitetura — Cache e Rate Limiting (ADR-007):**

- Redis (Upstash) com 4 camadas independentes via CacheManager:
  - Message Buffer: msg_buffer:{phone} (TTL 3s) — debounce de mensagens
  - Session Cache: session:{user_id} (TTL 1h) — histórico recente
  - Config Cache: config:{key} (TTL 5min) — hot-reload de configurações
  - Rate Limiting: ratelimit:{user_id}:{tier} (TTL 24h) — contadores sliding window + token bucket
- Rate limiting dual: sliding window (limite diário por tipo) + token bucket (anti-burst)
- redis-py 5.2+ com async support (aioredis merged)

**Da Arquitetura — Segurança (ADR-008):**

- 6 camadas de segurança:
  1. Webhook Validation: HMAC SHA-256 via Django middleware (WebhookSignatureMiddleware)
  2. Input Validation: DRF Serializers (WhatsAppMessageSerializer com regex, timestamp validation)
  3. Rate Limiting: Redis dual (sliding window + token bucket)
  4. Data Access Control: Django permissions + RLS no Supabase como defense-in-depth
  5. Secrets Management: GCP Secret Manager + django-environ (.env em dev, secrets montados em prod)
  6. Logging Sanitization: structlog processor sanitize_pii (redact phone, name, email, cpf, api_key)

**Da Arquitetura — Data Models e Django Admin (ADR-003, ADR-011):**

- Django ORM com Supabase PostgreSQL como backend (ADR-003) — supabase-py apenas para Auth/Storage
- 5 Django Models: User, Message, Config, CostLog, ToolExecution
- Django Admin como UI administrativa Phase 1 (zero frontend custom) — CRUD, filtros, search, date_hierarchy
- Django migrations para schema evolution (preservar dados existentes)
- LangGraph checkpoint em schema separado `langgraph` (gerenciado por AsyncPostgresSaver.setup())
- Django ORM async: aget(), acreate(), afilter(), abulk_create()

**Da Arquitetura — Observabilidade:**

- structlog com JSON rendering, PII sanitization, e log levels definidos (DEBUG/INFO/WARNING/ERROR/CRITICAL)
- Langfuse para traces end-to-end (fire-and-forget, não bloqueia pipeline)
- Trace ID propagation via Django middleware (trace_id.py) + structlog contextvars
- CostLog e ToolExecution persistidos via Django ORM em nó persist do grafo
- Event naming: snake_case, verbo no passado para eventos (message_received, tool_executed)

**Da Arquitetura — Padrões Obrigatórios (Enforcement Rules):**

- LangGraph node contract: funções async puras (async def node_name(state: WhatsAppState) -> dict)
- LangChain @tool decorator para definir tools (docstring usada pelo LLM para decisão)
- AppError hierarchy: AppError → ValidationError, AuthenticationError, RateLimitError, ExternalServiceError, GraphNodeError
- Message deduplication via Redis (msg_processed:{message_id}, TTL 1h)
- Concurrency control com asyncio.Semaphore(50)
- Feature flags com rollout gradual (hash-based bucketing via hashlib.md5)
- WhatsApp event filtering (ignorar status updates, mensagens de sistema)
- Graceful shutdown via ASGI server (Cloud Run SIGTERM → 10s grace period)
- Import order: Standard library → Third-party → Local (Django app-relative)
- Naming: snake_case (arquivos, funções, variáveis), PascalCase (classes), UPPER_SNAKE_CASE (constantes, env vars)
- PROIBIDO: print(), sync I/O, supabase-py para queries de dados, Tool ABC custom, camelCase, import *

**Da Arquitetura — Migração Strangler Fig:**

- Feature flags para rollout gradual (5% → 25% → 50% → 100%) via ConfigService + hash-based bucketing
- Shadow Mode para comparação de respostas (código novo vs n8n)
- n8n e código novo coexistem apontando para o mesmo Supabase durante transição

**Da Arquitetura — Citação e Fontes Verificáveis (rev. 2026-03-05):**

- Sistema de citação com 2 tiers: `[N]` para fontes RAG (Gold — conteúdo curado Medway) e `[W-N]` para fontes web (Silver — verificado em tempo real)
- Proibido citar da memória/treinamento da LLM — apenas fontes retornadas por tools
- Pipeline de citação em 4 etapas: Tools retornam fontes → LLM cita com `[N]`/`[W-N]` → format_response valida → WhatsApp renderiza rodapé
- `validate_citations()` no nó format_response: strip de marcadores `[N]` que não correspondem a fontes reais
- Rodapé de fontes formatado para WhatsApp (`📚 *Fontes:*`)
- WhatsAppState inclui campos: `retrieved_sources`, `cited_source_indices`, `web_sources`

**Da Arquitetura — Bloqueio de Concorrentes (rev. 2026-03-05):**

- `web_search` tool usa Tavily `search_depth="advanced"` + `exclude_domains` com lista de concorrentes
- Concorrentes bloqueados: Medcurso, Medgrupo, MedCof, Estratégia MED, Medcel, Sanar, Aristo, Yellowbook, O Residente, Afya
- Lista de concorrentes armazenada no Config model (editável via Django Admin sem deploy)
- `strip_competitor_citations()` no format_response como última camada de defesa
- System prompt inclui regra explícita: nunca recomendar ou citar conteúdo de concorrentes
- 3 camadas de proteção: web search (exclude_domains) → system prompt (regra) → format_response (strip)

**Da Arquitetura — Verificação de Artigos Acadêmicos (rev. 2026-03-05):**

- Nova tool `verify_medical_paper` via PubMed E-utilities API
- Valida se artigos/estudos mencionados pelo usuário realmente existem no PubMed antes de citar
- Se artigo não encontrado: "⚠️ ARTIGO NÃO ENCONTRADO no PubMed. NÃO cite este estudo."
- Se encontrado: retorna dados verificados (título, autores, journal, DOI, ano)
- Arquivo: `workflows/whatsapp/tools/verify_paper.py`

**Da Decisão Técnica (decisao-tecnica-langgraph-vs-claude-sdk.md):**

- Decisão por LangGraph + LangChain motivada principalmente por alinhamento com equipe Medway
- State management (checkpointing) out-of-the-box foi fator decisivo vs SDK direto
- Framework Django em vez de FastAPI — alinhamento com equipe
- GCP Cloud Run em vez de Railway — mesma infra que Vertex AI
- Opção 1 (LangGraph completo) escolhida sobre Opção 2 (SDK direto) e Opção 3 (híbrida)

### FR Coverage Map

| FR | Epic | Descrição |
|----|------|-----------|
| FR1 | Epic 1 | Enviar texto, receber resposta |
| FR2 | Epic 3 | Áudio → transcrição → resposta |
| FR3 | Epic 3 | Imagem → análise → resposta |
| FR4 | Epic 6 | Feedback positivo/negativo (Reply Buttons) |
| FR5 | Epic 6 | Comentário opcional no feedback |
| FR6 | Epic 1 | Debounce de mensagens rápidas |
| FR7 | Epic 1 | Resposta para mensagens não suportadas |
| FR8 | Epic 1 | Split de respostas longas |
| FR9 | Epic 1 | Indicador "processando" |
| FR10 | Epic 1 | Boas-vindas na primeira interação |
| FR11 | Epic 2 | Q&A médico com citações `[N]`/`[W-N]` |
| FR12 | Epic 2 | RAG com fontes verificáveis (Gold `[N]`) |
| FR13 | Epic 2 | Busca web com citações (Silver `[W-N]`) + exclude_domains |
| FR14 | Epic 2 | Bulas de medicamentos |
| FR15 | Epic 2 | Calculadoras médicas |
| FR16 | Epic 2 | Seleção automática de tools (ToolNode paralelo) |
| FR17 | Epic 1 | Disclaimers médicos |
| FR18 | Epic 1 | Formatação estruturada WhatsApp + validação de citações |
| FR19 | Epic 1 | Formato adaptativo por conteúdo |
| FR20 | Epic 1 | Identificação aluno/não-aluno |
| FR21 | Epic 1 | Features diferenciadas por tipo |
| FR22 | Epic 4 | Visualizar perguntas restantes |
| FR23 | Epic 4 | Limitar interações diárias |
| FR24 | Epic 4 | Anti-burst (anti-spam) |
| FR25 | Epic 9 | Quiz e prática ativa |
| FR26 | Epic 9 | Sugestão contextual de quiz |
| FR27 | Epic 1 | Contexto de conversas anteriores (checkpointing) |
| FR28 | Epic 1 | Armazenar/recuperar histórico (Django ORM) |
| FR29 | Epic 7 | Cost tracking por request (CostTrackingCallback) |
| FR30 | Epic 7 | Métricas de qualidade |
| FR31 | Epic 7 | Alertas automáticos |
| FR32 | Epic 7 | Traces completos (Langfuse) |
| FR33 | Epic 8 | Config sem deploy (Config model + Redis cache) |
| FR34 | Epic 8 | Editar system prompt sem deploy |
| FR35 | Epic 8 | Histórico de system prompt |
| FR36 | Epic 8 | Rollback de system prompt |
| FR37 | Epic 8 | Histórico de configs |
| FR38 | Epic 8 | Hot-reload de configs (TTL 5min) |
| FR39 | Epic 5 | Retry automático (LangGraph RetryPolicy) |
| FR40 | Epic 5 | Mensagem amigável de erro |
| FR41 | Epic 5 | Resposta parcial |
| FR42 | Epic 5 | Circuit breaker (with_fallbacks) |
| FR43 | Epic 5 | Logging de erros com contexto (structlog) |
| FR44 | Epic 10 | Operação paralela com n8n |
| FR45 | Epic 10 | Preservar dados Supabase |
| FR46 | Epic 10 | Controle de percentual de tráfego |
| FR47 | Epic 10 | Comparação Shadow Mode |

**Cobertura: 47/47 FRs → 100%**

## Implementation Order

Epic 1 é a fundação — todos os Epics 2-10 dependem dele. Os Epics 2-10 são paralelos entre si (sem dependências forward entre eles).

```
Epic 1 (fundação) → Epics 2-10 (paralelos entre si, todos dependem do Epic 1)
Ordem sugerida: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10
```

**Notas:**
- O Config model + ConfigHistory + ConfigService básico são criados no Epic 1 Story 1.1 (setup), pois são necessários nos Epics 2 (web search competitor blocking) e 4 (rate limits por tier) antes do Epic 8.
- O Epic 8 aprimora o ConfigService com hot-reload via Redis cache (TTL 5min) e adiciona SystemPromptVersion.
- O CostTrackingCallback é implementado no Epic 1 Story 1.4 com output via structlog; a persistência no banco (CostLog) e integração Langfuse são adicionadas no Epic 7 Story 7.1.

## Epic List

### Epic 1: Core Q&A — Perguntas por Texto via WhatsApp
O aluno envia pergunta por texto pelo WhatsApp e recebe resposta inteligente formatada, com contexto de conversas anteriores. Sistema identifica tipo de usuário e adapta experiência. Inclui todo o pipeline end-to-end: Django project setup, webhook handler, LangGraph StateGraph, identify_user, Claude via ChatAnthropicVertex + fallback, formatação WhatsApp (com validação de citações e strip de concorrentes), persistência Django ORM, debounce, typing indicator, boas-vindas, split de mensagens, disclaimer médico.
**FRs covered:** FR1, FR6, FR7, FR8, FR9, FR10, FR17, FR18, FR19, FR20, FR21, FR27, FR28
**Stories:** 1.1, 1.2, 1.3, 1.4, 1.5, 1.6

### Epic 2: Medical Knowledge Tools — Respostas com Fontes Verificáveis
Respostas enriquecidas com citações de fontes médicas verificáveis — o diferenciador #1 vs ChatGPT. RAG Pinecone com citações `[N]` (Gold), busca web Tavily com citações `[W-N]` (Silver) e exclude_domains de concorrentes, verificação de artigos via PubMed (verify_medical_paper), bulas de medicamentos, calculadoras médicas, orquestração de tools paralelas via ToolNode.
**FRs covered:** FR11, FR12, FR13, FR14, FR15, FR16
**Stories:** 2.1, 2.2, 2.3, 2.4, 2.5, 2.6

### Epic 3: Áudio e Imagem
Aluno pode mandar áudio (dúvida no plantão) ou foto (questão de prova) e receber resposta. Whisper para transcrição, Vision para imagens.
**FRs covered:** FR2, FR3
**Stories:** 3.1, 3.2

### Epic 4: Rate Limiting Transparente
Aluno sabe quantas perguntas restam, quando reseta, e nunca é bloqueado sem explicação. Sistema protegido contra abuso. Sliding window (diário) + token bucket (anti-burst) via Redis.
**FRs covered:** FR22, FR23, FR24
**Stories:** 4.1

### Epic 5: Resiliência e Self-Healing
Aluno SEMPRE recebe uma resposta — nunca mais silêncio. Sistema se recupera sozinho de falhas. LangGraph RetryPolicy com backoff, with_fallbacks() para LLM, mensagem amigável de erro, resposta parcial quando tool falha, logging de erros com contexto completo via structlog.
**FRs covered:** FR39, FR40, FR41, FR42, FR43
**Stories:** 5.1, 5.2

### Epic 6: Feedback Loop (North Star Metric)
Aluno avalia respostas com positivo/negativo (Reply Buttons), podendo comentar. Alimenta a North Star Metric (satisfação >85%). Reply Buttons do WhatsApp (max 3), comentário opcional via follow-up.
**FRs covered:** FR4, FR5
**Stories:** 6.1

### Epic 7: Observabilidade e Cost Tracking
Equipe Medway tem visibilidade total — custo por request (CostTrackingCallback + CostLog), métricas de qualidade, alertas automáticos, traces completos via Langfuse para debugging. M1 = coleta de dados + Django Admin (sem dashboard custom).
**FRs covered:** FR29, FR30, FR31, FR32
**Stories:** 7.1, 7.2, 7.3

### Epic 8: Configuração Dinâmica e System Prompt
Equipe Medway gerencia rate limits, timeouts, mensagens, system prompt e lista de concorrentes sem deploy. Aprimora o ConfigService básico (criado no Epic 1 Story 1.1) com hot-reload via Redis cache (TTL 5min) e audit trail detalhado. Adiciona system prompt versionado com autor/timestamp, histórico e rollback via Django Admin.
**FRs covered:** FR33, FR34, FR35, FR36, FR37, FR38
**Stories:** 8.1, 8.2

### Epic 9: Quiz e Prática Ativa
Aluno pode praticar com quizzes interativos. Sistema sugere quiz após respostas relevantes. Tool de geração de questões, sugestão contextual de quiz ao final de respostas.
**FRs covered:** FR25, FR26
**Stories:** 9.1

### Epic 10: Migração Strangler Fig
Migração segura de n8n para código próprio com zero downtime. Equipe controla rollout gradual (5%→25%→50%→100%) e compara qualidade via Shadow Mode. Feature flags com hash-based bucketing, preservação de dados Supabase existentes.
**FRs covered:** FR44, FR45, FR46, FR47
**Stories:** 10.1, 10.2

---

## Epic 1: Core Q&A — Perguntas por Texto via WhatsApp

O aluno envia pergunta por texto pelo WhatsApp e recebe resposta inteligente formatada, com contexto de conversas anteriores. Sistema identifica tipo de usuário e adapta experiência.

### Story 1.1: Setup do Projeto Django + Estrutura Base

As a desenvolvedor,
I want o projeto Django configurado com a estrutura definida na arquitetura,
So that posso começar a implementar as features sobre uma base sólida e padronizada.

**Acceptance Criteria:**

**Given** o repositório vazio
**When** executo o setup do projeto
**Then** o projeto Django 5.1+ está configurado com `config/settings/{base,development,production}.py` usando django-environ
**And** a app `workflows/` existe com sub-módulos: `whatsapp/` (graph, nodes, tools, prompts), `services/`, `providers/`, `middleware/`, `utils/`
**And** `workflows/models.py` contém os models `User` (phone, medway_id, subscription_tier, metadata, created_at) e `Message` (user FK, content, role, message_type, tokens_input, tokens_output, cost_usd, created_at)
**And** `workflows/models.py` contém o model `Config` (key CharField unique, value JSONField, updated_by CharField, updated_at DateTimeField auto_now) para configurações dinâmicas
**And** `workflows/models.py` contém o model `ConfigHistory` (config FK, old_value JSONField, new_value JSONField, changed_by CharField, changed_at DateTimeField auto_now_add) para audit trail de configurações
**And** `workflows/services/config_service.py` implementa ConfigService básico com `get(key)` que busca Config via Django ORM async (`Config.objects.aget(key=key)`) — sem Redis cache nesta fase
**And** configs iniciais são populadas via data migration: `rate_limit:free`, `rate_limit:premium`, `blocked_competitors`, `message:welcome`, `message:rate_limit`, `message:unsupported_type`, `debounce_ttl`
**And** `workflows/admin.py` registra User, Message, Config e ConfigHistory no Django Admin
**And** `workflows/utils/errors.py` define hierarquia AppError → ValidationError, AuthenticationError, RateLimitError, ExternalServiceError, GraphNodeError
**And** structlog está configurado com JSON rendering e processor `sanitize_pii` (redact phone, name, email, cpf, api_key)
**And** `pyproject.toml` configura Ruff (line-length=100, target py312), mypy strict, pytest-django
**And** `docker-compose.yml` sobe PostgreSQL 16 + Redis 7 para dev local
**And** `Dockerfile` multi-stage com uv funciona (`docker build` passa)
**And** `.env.example` lista todas as variáveis necessárias
**And** `uv run ruff check .` e `uv run ruff format --check .` passam
**And** `uv run pytest` roda (mesmo sem testes ainda)
**And** Django migrations rodam com sucesso (`uv run python manage.py migrate`)

### Story 1.2: Webhook WhatsApp + Middleware de Segurança

As a sistema,
I want receber mensagens do WhatsApp via webhook com validação de segurança,
So that apenas mensagens legítimas são processadas e a Meta não reenvia por timeout.

**Acceptance Criteria:**

**Given** uma requisição POST no `/webhook/whatsapp/` com assinatura HMAC válida
**When** a Meta envia um payload de mensagem de texto
**Then** o middleware `WebhookSignatureMiddleware` valida a assinatura `X-Hub-Signature-256` via HMAC SHA-256
**And** o `WhatsAppMessageSerializer` (DRF) valida o payload (regex phone, timestamp ≤ 300s)
**And** a mensagem é deduplicada via Redis (`msg_processed:{message_id}`, TTL 1h)
**And** mensagens duplicadas são ignoradas silenciosamente
**And** o processamento é disparado via `asyncio.create_task` (fire-and-forget)
**And** o webhook retorna 200 OK em < 3 segundos (NFR14)
**And** status updates (delivered, read) são filtrados e ignorados
**And** mensagens do tipo "system" e "unknown" são filtradas e ignoradas

**Given** uma requisição POST sem assinatura ou com assinatura inválida
**When** a Meta envia o payload
**Then** o middleware retorna 401 e loga `webhook_signature_invalid`

**Given** uma requisição GET no `/webhook/whatsapp/`
**When** a Meta envia o handshake de verificação (`hub.mode=subscribe`, `hub.verify_token`)
**Then** o sistema retorna o `hub.challenge` com 200 OK se o token confere
**And** retorna 403 se o token não confere

**Given** o trace_id middleware
**When** qualquer request chega
**Then** um UUID trace_id é gerado e propagado via structlog contextvars

### Story 1.3: Identificação de Usuário + Carregamento de Contexto

As a aluno Medway ou não-aluno,
I want ser identificado automaticamente pelo meu número de telefone,
So that recebo experiência personalizada conforme meu tipo de usuário.

**Acceptance Criteria:**

**Given** uma mensagem de um número de telefone cadastrado como aluno Medway
**When** o nó `identify_user` do StateGraph processa o estado
**Then** o sistema busca o User via Django ORM async (`User.objects.aget(phone=phone)`)
**And** retorna `user_id` e `subscription_tier` no estado
**And** o resultado é cacheado no Redis (`session:{user_id}`, TTL 1h)

**Given** uma mensagem de um número desconhecido
**When** o nó `identify_user` processa
**Then** o sistema cria um novo User com `subscription_tier="free"` via `User.objects.acreate()`
**And** retorna o novo user no estado

**Given** um User já identificado
**When** o nó `load_context` processa
**Then** o sistema carrega as últimas 20 mensagens via Django ORM async (`Message.objects.filter(user=user).order_by("-created_at")[:20]`)
**And** formata como LangChain messages para o contexto do LLM
**And** verifica cache Redis antes do banco (session cache)

### Story 1.4: LLM Provider + Checkpointer + Orquestração Base

As a aluno,
I want fazer uma pergunta médica por texto e receber uma resposta contextualizada,
So that resolvo minha dúvida rapidamente sem sair do WhatsApp.

**Acceptance Criteria:**

**Given** `workflows/providers/llm.py` com `get_model()`
**When** o provider é inicializado
**Then** `ChatAnthropicVertex` é o primary (model `claude-sonnet-4@20250514`, streaming=True, max_retries=2)
**And** `ChatAnthropic` é o fallback com `model.with_fallbacks([fallback])`
**And** credenciais Vertex usam service_account.Credentials do GCP

**Given** `workflows/providers/checkpointer.py`
**When** `get_checkpointer()` é chamado
**Then** retorna `AsyncPostgresSaver` singleton com `AsyncConnectionPool` (min_size=5, max_size=20, schema=langgraph)

**Given** o nó `orchestrate_llm` do StateGraph
**When** processa uma mensagem de texto do aluno
**Then** invoca o modelo com system prompt + histórico da conversa
**And** `AnthropicPromptCachingMiddleware` (TTL 5min) é aplicado
**And** `CostTrackingCallback` registra tokens_input, tokens_output, cache_read, cache_creation via structlog (logs JSON) — persistência no banco (CostLog model) e integração Langfuse são adicionadas na Story 7.1
**And** a resposta do Claude é adicionada ao estado como `response_text`

**Given** o StateGraph completo (`build_whatsapp_graph()`)
**When** compilado com checkpointer
**Then** usa `thread_id = phone_number` para persistência automática de conversa
**And** concurrency é controlada por `asyncio.Semaphore(50)` (NFR4)

### Story 1.5: Formatação, Envio WhatsApp e Persistência

As a aluno,
I want receber respostas bem formatadas no WhatsApp com disclaimer médico,
So that a informação é fácil de ler e eu sei que é ferramenta de apoio.

**Acceptance Criteria:**

**Given** o nó `format_response` do StateGraph
**When** processa uma resposta do Claude
**Then** converte markdown para formato otimizado para WhatsApp (negrito, itálico, listas)
**And** aplica `validate_citations()` para strip de marcadores `[N]` sem fonte real correspondente (no-op quando não há ferramentas ativas — sem tools = sem citações para validar)
**And** aplica `strip_competitor_citations()` como última camada de defesa (no-op quando não há ferramentas ativas)
**And** adiciona disclaimer médico quando relevante (FR17)
**And** adapta formato ao tipo de conteúdo: explicação, cálculo, lista, comparação (FR19)

**Given** uma resposta que excede 4096 caracteres
**When** o format_response processa
**Then** divide em mensagens sequenciais mantendo coerência e formatação (FR8)

**Given** o nó `send_whatsapp` do StateGraph
**When** processa a resposta formatada
**Then** envia via WhatsApp Cloud API (POST) com `RetryPolicy(max_attempts=3, backoff_factor=2.0)`
**And** envia typing indicator ("digitando...") antes da resposta (FR9)
**And** loga delivery status

**Given** o nó `persist` do StateGraph
**When** processa após o envio
**Then** salva mensagem do usuário e resposta do assistente via `Message.objects.acreate()`
**And** loga `data_persisted` com user_id via structlog

### Story 1.6: Debounce, Boas-vindas e Mensagens Não Suportadas

As a aluno,
I want que o sistema acumule minhas mensagens rápidas e me receba bem na primeira vez,
So that não recebo respostas parciais e tenho uma boa primeira impressão.

**Acceptance Criteria:**

**Given** um aluno que envia 3 mensagens em 2 segundos
**When** as mensagens são recebidas pelo webhook
**Then** o sistema acumula via Redis message buffer (`msg_buffer:{phone}`, TTL 3s) (FR6)
**And** processa todas as mensagens acumuladas como uma única entrada após o debounce
**And** o TTL é configurável via config dinâmica (NFR5)

**Given** um número de telefone que nunca interagiu com o sistema
**When** envia a primeira mensagem
**Then** o sistema envia mensagem de boas-vindas antes da resposta (FR10)
**And** a boas-vindas é simples: "Olá! Sou o Medbrain, seu tutor médico pelo WhatsApp. Pode me perguntar qualquer dúvida médica — respondo com fontes verificáveis."

**Given** um aluno que envia sticker, localização, documento ou contato
**When** o webhook recebe o tipo não suportado
**Then** o sistema responde com mensagem informativa: "Desculpe, no momento só consigo processar mensagens de texto, áudio e imagem." (FR7)
**And** a mensagem informativa é configurável

---

## Epic 2: Medical Knowledge Tools — Respostas com Fontes Verificáveis

Respostas enriquecidas com citações de fontes médicas verificáveis — o diferenciador #1 vs ChatGPT.

### Story 2.1: RAG Médico — Busca na Base de Conhecimento com Citações `[N]`

As a aluno,
I want fazer perguntas médicas e receber respostas com citações da base de conhecimento curada Medway,
So that confio na resposta porque sei de onde vem a informação.

**Acceptance Criteria:**

**Given** o aluno pergunta "Quando usar carvedilol vs metoprolol na IC?"
**When** o ToolNode executa a tool `rag_medical_search`
**Then** a tool busca no Pinecone com o embedding da query (top_k=5)
**And** retorna resultados formatados com índice sequencial para citação `[N]`
**And** cada resultado inclui: título da fonte, trecho relevante, metadata (livro/diretriz, página/seção)
**And** os resultados são adicionados ao `retrieved_sources` do WhatsAppState com `type="rag"`
**And** o LLM usa os resultados para compor a resposta citando com marcadores `[N]`
**And** o rodapé inclui as fontes no formato `📚 *Fontes:* [1] Harrison, Cap. 252 — IC [2] Diretriz SBC 2023`

**Given** a query não retorna resultados no Pinecone (cobertura = 0)
**When** a tool executa
**Then** retorna mensagem indicando que não há conteúdo curado para o tema
**And** o LLM sabe que pode usar web search como alternativa

### Story 2.2: Web Search — Busca Web com Citações `[W-N]` e Bloqueio de Concorrentes

As a aluno,
I want receber informações da web quando a base de conhecimento não cobre minha dúvida,
So that tenho acesso a informações atualizadas com fontes verificáveis.

**Acceptance Criteria:**

**Given** o LLM decide que precisa de informações da web
**When** o ToolNode executa a tool `web_search`
**Then** a tool usa Tavily com `search_depth="advanced"`, `include_raw_content=True`, `max_results=8`
**And** `exclude_domains` contém a lista de concorrentes carregada do Config model (Medcurso, Medgrupo, MedCof, Estratégia MED, Medcel, Sanar, Aristo, Yellowbook, O Residente, Afya)
**And** resultados são formatados com índice `[W-N]` (ex: `[W-1]`, `[W-2]`)
**And** cada resultado inclui: título, URL, trecho relevante
**And** os resultados são adicionados ao `web_sources` do WhatsAppState com `type="web"`
**And** o rodapé inclui fontes web: `🌐 *Web:* [W-1] PubMed — doi:10.1000/xyz`

**Given** todos os resultados do Tavily são de domínios bloqueados
**When** a tool executa
**Then** retorna mensagem indicando que não encontrou fontes web confiáveis
**And** o LLM responde sem citação web

**Given** a lista de concorrentes no Config model é atualizada via Django Admin
**When** a próxima busca web é executada
**Then** usa a lista atualizada (via Redis config cache, TTL 5min)

### Story 2.3: Verificação de Artigos Acadêmicos via PubMed

As a aluno,
I want que artigos citados sejam verificados como reais,
So that não recebo referências inventadas (alucinações do LLM).

**Acceptance Criteria:**

**Given** o aluno menciona um estudo ou artigo específico (ex: "o estudo PARADIGM-HF")
**When** o LLM decide usar a tool `verify_medical_paper`
**Then** a tool busca no PubMed E-utilities API (`esearch.fcgi` + `esummary.fcgi`)
**And** busca por título e autores (quando disponíveis)

**Given** o artigo existe no PubMed
**When** a verificação retorna resultado
**Then** retorna dados verificados: título completo, autores, journal, DOI, ano de publicação
**And** o LLM pode citar o artigo com confiança

**Given** o artigo NÃO existe no PubMed
**When** a verificação retorna zero resultados
**Then** retorna "⚠️ ARTIGO NÃO ENCONTRADO no PubMed. NÃO cite este estudo."
**And** o LLM não cita o artigo na resposta

**Given** o PubMed API está indisponível (timeout 5s, 2 retries)
**When** a verificação falha
**Then** retorna mensagem indicando que a verificação não foi possível
**And** o LLM pode citar com ressalva ("verificação indisponível no momento")

### Story 2.4: Bulas de Medicamentos

As a aluno,
I want consultar informações sobre medicamentos (indicações, dosagens, interações),
So that tenho referência confiável sobre farmacologia durante estudos e plantões.

**Acceptance Criteria:**

**Given** o aluno pergunta "Qual a dose de amoxicilina pediátrica?"
**When** o LLM decide usar a tool `drug_lookup`
**Then** a tool busca na base de bulas (full-text search)
**And** retorna: indicações, posologia, contraindicações, interações medicamentosas
**And** cita a fonte (bula ANVISA ou base curada Medway)

**Given** o medicamento não é encontrado na base
**When** a tool executa
**Then** retorna mensagem indicando que o medicamento não foi encontrado
**And** sugere verificar o nome comercial/genérico

### Story 2.5: Calculadoras Médicas

As a aluno,
I want calcular scores médicos (CHA₂DS₂-VASc, Clearance de Creatinina, etc.) fornecendo dados por texto,
So that resolvo cálculos rapidamente no plantão.

**Acceptance Criteria:**

**Given** o aluno fornece dados para cálculo (ex: "Paciente 72 anos, hipertenso, diabético, sem AVC, sem IC. CHA₂DS₂-VASc?")
**When** o LLM decide usar a tool `medical_calculator`
**Then** a tool identifica a calculadora correta e extrai os parâmetros
**And** executa o cálculo (funções Python locais, sem chamada externa)
**And** retorna: score calculado, interpretação, conduta recomendada
**And** cita a diretriz fonte do score

**Given** dados insuficientes para o cálculo
**When** a tool executa
**Then** retorna quais dados estão faltando para completar o cálculo
**And** o LLM pergunta ao aluno os dados faltantes

### Story 2.6: Orquestração de Tools Paralelas via ToolNode

As a aluno,
I want que o sistema use múltiplas ferramentas ao mesmo tempo quando necessário,
So that recebo respostas completas sem esperar cada ferramenta sequencialmente.

**Acceptance Criteria:**

**Given** o aluno faz uma pergunta que requer RAG + calculadora (ex: "CHA₂DS₂-VASc de paciente 72a, HAS, DM + conduta de anticoagulação")
**When** o LLM gera múltiplos tool_calls na mesma resposta
**Then** o ToolNode do LangChain executa as tools em paralelo por padrão (FR16)
**And** os resultados de todas as tools são retornados ao LLM para composição da resposta final
**And** as fontes de todas as tools são unificadas no estado (`retrieved_sources` + `web_sources`)

**Given** uma das tools falha durante a execução paralela
**When** o ToolNode processa os resultados
**Then** as tools que sucederam retornam normalmente
**And** a tool que falhou retorna mensagem de erro
**And** o LLM compõe a resposta com os dados disponíveis, informando o que não pôde ser consultado

**Given** o system prompt em `workflows/whatsapp/prompts/system.py`
**When** carregado para o LLM
**Then** inclui regras de citação: usar `[N]` para fontes RAG e `[W-N]` para fontes web
**And** inclui regra: nunca citar da memória/treinamento — apenas fontes retornadas por tools
**And** inclui regra: nunca recomendar ou citar conteúdo de concorrentes
**And** inclui descrições claras de quando usar cada tool

---

## Epic 3: Áudio e Imagem

Aluno pode mandar áudio (dúvida no plantão) ou foto (questão de prova) e receber resposta.

### Story 3.1: Transcrição de Áudio via Whisper

As a aluno no plantão,
I want enviar mensagens de áudio e receber respostas baseadas na transcrição,
So that tiro dúvidas rapidamente mesmo quando não posso digitar.

**Acceptance Criteria:**

**Given** o aluno envia um áudio pelo WhatsApp
**When** o nó `process_media` do StateGraph detecta `message_type="audio"`
**Then** faz download do áudio via WhatsApp Cloud API (media endpoint)
**And** envia para Whisper API (OpenAI) para transcrição (timeout 20s, 2 retries)
**And** a transcrição é adicionada ao estado como texto de entrada para o LLM
**And** o pipeline continua normalmente (load_context → orchestrate_llm → ...)
**And** latência total P95 < 12 segundos (NFR2)

**Given** a transcrição do Whisper falha (timeout ou erro)
**When** o nó process_media processa
**Then** envia mensagem ao aluno: "Não consegui processar seu áudio. Pode enviar por texto?"
**And** loga o erro com contexto completo via structlog

#### Retro Watch Items

- **Error handler silencioso** — zero `except Exception` sem log (retros Epic 1, 2, 4). Flagar como RETRO WATCH no code review.
- **Over-mocking** — exigir ≥1 teste de integração real por story (pendente desde Epic 1).
- **Exceção raw para LLM** — tools SEMPRE retornam string, nunca raise exception (acordo do time).

### Story 3.2: Análise de Imagens via Vision

As a aluno,
I want enviar fotos de questões de prova ou exames e receber análise,
So that resolvo dúvidas visuais sem precisar transcrever manualmente.

**Acceptance Criteria:**

**Given** o aluno envia uma imagem pelo WhatsApp
**When** o nó `process_media` detecta `message_type="image"`
**Then** faz download da imagem via WhatsApp Cloud API
**And** envia a imagem junto com a mensagem para o Claude (Vision nativo do modelo)
**And** o LLM analisa o conteúdo visual e responde contextualmente
**And** latência total P95 < 15 segundos (NFR3)

**Given** a imagem é ilegível ou muito pequena
**When** o LLM processa
**Then** informa ao aluno que não conseguiu ler a imagem e sugere reenviar com melhor qualidade

#### Retro Watch Items

- **Error handler silencioso** — zero `except Exception` sem log (retros Epic 1, 2, 4). Flagar como RETRO WATCH no code review.
- **Over-mocking** — exigir ≥1 teste de integração real por story (pendente desde Epic 1).
- **Exceção raw para LLM** — tools SEMPRE retornam string, nunca raise exception (acordo do time).

---

## Epic 4: Rate Limiting Transparente

Aluno sabe quantas perguntas restam, quando reseta, e nunca é bloqueado sem explicação.

### Story 4.1: Rate Limiting Dual — Sliding Window + Token Bucket

As a aluno,
I want saber quantas perguntas tenho disponíveis e ser protegido contra bloqueio imprevisível,
So that nunca sou surpreendido por um limite invisível.

**Acceptance Criteria:**

**Given** o nó `rate_limit` do StateGraph
**When** verifica limites do aluno
**Then** aplica sliding window (limite diário por tier via Redis `ratelimit:daily:{user_id}`, TTL 24h) (FR23)
**And** aplica token bucket (anti-burst via Redis `ratelimit:burst:{user_id}`, refill 1min) (FR24)
**And** limites são carregados do Config model (configuráveis por tier: free, basic, premium)

**Given** o aluno está a 2 perguntas do limite diário
**When** recebe a resposta
**Then** a resposta inclui aviso: "Você ainda tem 2 perguntas disponíveis hoje. Seu limite reseta amanhã às 00h." (FR22)

**Given** o aluno atingiu o limite diário
**When** envia uma nova mensagem
**Then** o sistema responde: "Você atingiu seu limite de X interações por hoje. Seu limite reseta amanhã às 00h. Até lá!" (FR22)
**And** o grafo encerra no nó rate_limit (edge condicional → END)
**And** nenhuma chamada ao LLM é feita (economia de custo)

**Given** o aluno envia 5 mensagens em 3 segundos (burst)
**When** o token bucket verifica
**Then** as mensagens excedentes recebem: "Muitas mensagens em sequência. Aguarde 1 minuto."
**And** o debounce (Story 1.6) acumula as mensagens restantes

---

## Epic 5: Resiliência e Self-Healing

Aluno SEMPRE recebe uma resposta — nunca mais silêncio. Sistema se recupera sozinho de falhas.

### Story 5.1: Retry Automático e Circuit Breaker

As a aluno,
I want que o sistema se recupere sozinho de falhas temporárias,
So that não preciso reenviar minha pergunta manualmente.

**Acceptance Criteria:**

**Given** uma chamada ao Claude via Vertex AI falha com timeout
**When** o LangGraph RetryPolicy detecta a falha
**Then** tenta novamente com backoff exponencial (max_attempts=3, backoff_factor=2.0) (FR39)
**And** se Vertex AI falha após retries, `with_fallbacks()` ativa Anthropic Direct automaticamente (FR42)
**And** o provider usado é registrado no estado (`provider_used`)

**Given** chamadas ao Pinecone, Whisper ou WhatsApp API falham
**When** o retry do nó correspondente é acionado
**Then** cada serviço tem `RetryPolicy` configurado no nó do StateGraph
**And** erros são logados com contexto completo: user_id, mensagem, tipo de erro, timestamp, trace_id (FR43)

#### Retro Watch Items

- **Error handler silencioso** — zero `except Exception` sem log (retros Epic 1, 2, 4). Flagar como RETRO WATCH no code review.
- **Over-mocking** — exigir ≥1 teste de integração real por story (pendente desde Epic 1).
- **Exceção raw para LLM** — tools SEMPRE retornam string, nunca raise exception (acordo do time).

### Story 5.2: Mensagem Amigável e Resposta Parcial

As a aluno,
I want sempre receber alguma resposta, mesmo quando há problemas técnicos,
So that nunca fico no escuro esperando uma resposta que não vem.

**Acceptance Criteria:**

**Given** o LLM falha após todos os retries e fallback
**When** o grafo detecta a falha irrecuperável
**Then** envia mensagem amigável: "Desculpe, tive uma instabilidade técnica ao processar sua pergunta. Pode enviar novamente?" (FR40)
**And** a mensagem é configurável via Config model

**Given** uma tool específica falha (ex: Pinecone timeout) mas o LLM funciona
**When** o ToolNode retorna erro para aquela tool
**Then** o LLM compõe resposta com os dados disponíveis das outras tools (FR41)
**And** informa: "Não consegui consultar a base de conhecimento neste momento, mas com base nas outras fontes..."
**And** indica quais fontes não estavam disponíveis

**Given** erro em qualquer etapa do pipeline
**When** o erro é capturado
**Then** é logado via structlog com: user_id, phone (redacted), mensagem original, nó que falhou, tipo de erro, stack trace, trace_id, timestamp (FR43)
**And** o log é estruturado (JSON) para consulta no Langfuse

#### Retro Watch Items

- **Error handler silencioso** — zero `except Exception` sem log (retros Epic 1, 2, 4). Flagar como RETRO WATCH no code review.
- **Over-mocking** — exigir ≥1 teste de integração real por story (pendente desde Epic 1).
- **Exceção raw para LLM** — tools SEMPRE retornam string, nunca raise exception (acordo do time).

---

## Epic 6: Feedback Loop (North Star Metric)

Aluno avalia respostas com positivo/negativo (Reply Buttons), podendo comentar. Alimenta a North Star Metric (satisfação >85%).

### Story 6.1: Reply Buttons para Feedback + Comentário Opcional

As a aluno,
I want avaliar as respostas do Medbrain com positivo/negativo,
So that contribuo para melhorar a qualidade do serviço.

**Acceptance Criteria:**

**Given** o sistema envia uma resposta ao aluno
**When** a resposta é enviada via WhatsApp
**Then** inclui Reply Buttons com 3 opções: "Útil", "Não útil", "Comentar" (FR4)
**And** Reply Buttons usam o formato interactive message da WhatsApp Cloud API (max 3 buttons)

**Given** o aluno clica em "Útil" ou "Não útil"
**When** o webhook recebe a interação (type="interactive", interactive.type="button_reply")
**Then** o feedback é salvo no banco: mensagem avaliada, tipo de feedback (positivo/negativo), user_id, timestamp
**And** o model `Feedback` é criado em `workflows/models.py` (message FK, rating, comment, created_at)
**And** o Django Admin registra Feedback com filtros por rating e date_hierarchy

**Given** o aluno clica em "Comentar"
**When** o webhook recebe a interação
**Then** o sistema responde: "Obrigado! Pode me contar o motivo da sua avaliação?" (FR5)
**And** a próxima mensagem de texto do aluno é salva como comentário do feedback
**And** o fluxo volta ao normal após o comentário

---

## Epic 7: Observabilidade e Cost Tracking

Equipe Medway tem visibilidade total — custo por request, métricas de qualidade, alertas automáticos, traces completos para debugging.

### Story 7.1: CostTrackingCallback + CostLog

As a equipe Medway,
I want rastrear o custo de cada request com granularidade de tokens,
So that controlo o orçamento e identifico otimizações.

**Acceptance Criteria:**

**Given** o nó `orchestrate_llm` invoca o LLM
**When** o `CostTrackingCallback` (AsyncCallbackHandler) processa a resposta
**Then** registra tokens_input, tokens_output, tokens_cache_read, tokens_cache_creation
**And** calcula `cost_usd` usando pricing Vertex AI: input $3.00/MTok, cache_read $0.30/MTok, cache_creation $3.75/MTok, output $15.00/MTok
**And** registra qual provider foi usado (`primary` ou `fallback`)

**Given** o nó `persist` executa após o envio
**When** salva os dados da interação
**Then** cria registro `CostLog` via `CostLog.objects.acreate()` com: user FK, provider, model, tokens (input/output/cache_write/cache_read), cost_usd, created_at
**And** cria registro `ToolExecution` para cada tool chamada: tool_name, latency_ms, success, created_at

**Given** o Django Admin
**When** a equipe acessa `/admin/workflows/costlog/`
**Then** `CostLogAdmin` mostra list_display com user, provider, model, cost_usd, created_at
**And** list_filter por provider, model, created_at
**And** date_hierarchy por created_at
**And** precisão de custo ±5% sobre custo real da API (NFR8)

### Story 7.2: Traces End-to-End via Langfuse + structlog

As a equipe Medway,
I want traces completos de cada interação para debugging e análise de qualidade,
So that identifico rapidamente a causa de problemas e monitoro qualidade.

**Acceptance Criteria:**

**Given** `workflows/providers/langfuse.py` com integração Langfuse
**When** uma interação é processada pelo pipeline
**Then** um trace end-to-end é criado no Langfuse com spans para cada nó do grafo (FR32)
**And** o trace inclui: input do usuário, output do LLM, tools chamadas, latência por nó
**And** o envio é fire-and-forget (não bloqueia o pipeline)

**Given** o middleware `trace_id.py`
**When** qualquer request chega
**Then** gera UUID `trace_id` propagado via structlog contextvars
**And** o trace_id aparece em todos os logs structlog E no trace Langfuse

**Given** qualquer log emitido pela aplicação
**When** structlog processa
**Then** renderiza em JSON com campos: timestamp, level, event, trace_id, contexto relevante
**And** o processor `sanitize_pii` redacta automaticamente phone, name, email, cpf, api_key (NFR19)

### Story 7.3: Métricas de Qualidade e Alertas

As a equipe Medway,
I want monitorar métricas de qualidade e receber alertas quando thresholds são ultrapassados,
So that reajo proativamente a problemas antes que impactem os alunos.

**Acceptance Criteria:**

**Given** o Django Admin com dados de CostLog, Feedback, Message
**When** a equipe acessa o admin
**Then** pode consultar: custo agregado por dia/semana/mês, taxa de satisfação (positivo/total), latência média (via ToolExecution), taxa de erro por nó (FR30)

**Given** o gasto diário excede threshold configurável (ex: $50/dia)
**When** o sistema detecta via checagem periódica
**Then** envia alerta (log CRITICAL + notificação configurável) (FR31, NFR9)

**Given** a taxa de erro excede threshold (ex: > 5%)
**When** o sistema detecta
**Then** emite alerta com: nó com mais falhas, tipo de erro mais frequente, últimos 5 trace_ids para investigação (FR31)

---

## Epic 8: Configuração Dinâmica e System Prompt

Aprimora o ConfigService básico (criado no Epic 1 Story 1.1) com hot-reload via Redis cache e audit trail detalhado. Equipe Medway gerencia parâmetros operacionais e system prompt sem deploy, com histórico e rollback.

### Story 8.1: ConfigService Aprimorado — Hot-Reload via Redis + Audit Trail

As a equipe Medway,
I want que alterações em parâmetros operacionais entrem em vigor em minutos sem deploy,
So that ajusto o sistema rapidamente em resposta a necessidades operacionais.

**Nota:** Os models Config, ConfigHistory e o ConfigService básico (sem cache) já foram criados na Story 1.1. Esta story adiciona a camada de cache Redis e aprimora o audit trail.

**Acceptance Criteria:**

**Given** o ConfigService existente (criado na Story 1.1)
**When** aprimorado com camada de cache Redis
**Then** `config_service.get("rate_limit:free")` verifica Redis primeiro (`config:{key}`, TTL 5min)
**And** se cache miss, busca no banco via `Config.objects.aget(key=key)` e popula cache
**And** mudanças no Config model são refletidas em até 5 minutos (TTL expira) (FR38)

**Given** a equipe edita um Config no Django Admin (ex: muda `rate_limit:free` de 10 para 15)
**When** a configuração é salva
**Then** o `updated_by` é preenchido automaticamente com o usuário admin
**And** o `updated_at` é atualizado
**And** a mudança entra em vigor em até 5 minutos (FR33)
**And** o ConfigHistory registra old_value e new_value automaticamente (FR37)

**Given** novas configs operacionais adicionadas nesta fase
**When** definidas
**Then** incluem: `timeout:whisper`, `timeout:pinecone`, `timeout:tavily` e outros timeouts por serviço externo (NFR21)

### Story 8.2: System Prompt Versionado com Histórico e Rollback

As a equipe Medway,
I want editar o system prompt do Medbrain sem deploy e poder reverter para versões anteriores,
So that itero rapidamente na qualidade das respostas sem risco de perder uma versão boa.

**Acceptance Criteria:**

**Given** o model `SystemPromptVersion` em `workflows/models.py`
**When** definido
**Then** tem campos: version (AutoField), content (TextField), author (CharField), created_at (DateTimeField auto_now_add), is_active (BooleanField default=False)
**And** apenas UMA versão pode ter `is_active=True` por vez

**Given** a equipe edita o system prompt no Django Admin
**When** salva uma nova versão
**Then** a versão anterior é marcada como `is_active=False`
**And** a nova versão é marcada como `is_active=True` (FR34)
**And** o `author` e `created_at` são registrados automaticamente (FR35)
**And** a mudança entra em vigor em até 5 minutos (cache Redis expira)

**Given** a equipe quer reverter o system prompt
**When** acessa o histórico de versões no Django Admin
**Then** vê todas as versões com: número, autor, data de criação, status (ativa/inativa) (FR35)
**And** pode clicar em "Ativar" em qualquer versão anterior para restaurá-la (FR36)
**And** a reversão é registrada como nova entrada no histórico

**Given** `workflows/whatsapp/prompts/system.py`
**When** `get_system_prompt()` é chamado
**Then** busca a versão ativa via ConfigService (com cache Redis TTL 5min)
**And** o `AnthropicPromptCachingMiddleware` cacheia o prompt para economia de custo

---

## Epic 9: Quiz e Prática Ativa

Aluno pode praticar com quizzes interativos. Sistema sugere quiz após respostas relevantes.

### Story 9.1: Geração de Quiz + Sugestão Contextual

As a aluno,
I want praticar com quizzes sobre o tema que estou estudando,
So that fixo o conteúdo de forma ativa e interativa.

**Acceptance Criteria:**

**Given** o aluno pede um quiz (ex: "Me faça uma questão sobre IC")
**When** o LLM decide usar a tool `quiz_generate` via ToolNode
**Then** a tool (`workflows/whatsapp/tools/quiz_generator.py`) gera uma questão no formato: enunciado, 5 alternativas (A-E), e resposta comentada
**And** a questão é formatada para WhatsApp com alternativas em linhas separadas (FR25)
**And** a resposta comentada só é enviada APÓS o aluno responder

**Given** o aluno responde a questão com uma alternativa (ex: "B" ou "alternativa B")
**When** o LLM processa a resposta
**Then** apresenta: acertou/errou, resposta correta, comentário explicativo com fontes
**And** pergunta se quer outra questão sobre o mesmo tema ou tema diferente

**Given** o LLM acaba de responder uma pergunta médica substantiva
**When** o tema é propício para quiz (ex: diagnóstico diferencial, farmacologia, condutas)
**Then** sugere ao final: "Quer testar seu conhecimento sobre esse tema? Posso fazer uma questão rápida!" (FR26)
**And** a sugestão é natural e não repetitiva (max 1 sugestão a cada 5 interações)

---

## Epic 10: Migração Strangler Fig

Migração segura de n8n para código próprio com zero downtime. Equipe controla rollout gradual e compara qualidade.

### Story 10.1: Feature Flags + Roteamento Gradual de Tráfego

As a equipe Medway,
I want controlar o percentual de tráfego roteado para o código novo vs n8n,
So that faço a migração de forma segura e gradual, podendo parar a qualquer momento.

**Acceptance Criteria:**

**Given** `workflows/services/feature_flags.py` com `is_feature_enabled(user_id, feature)`
**When** avalia se um usuário usa código novo
**Then** usa hash-based bucketing: `hashlib.md5(user_id.encode()).hexdigest()` → `int(hex, 16) % 100`
**And** compara com `rollout_percentage` do Config model (`feature_flag:new_pipeline`)
**And** o mesmo usuário SEMPRE recebe o mesmo tratamento (determinístico) (FR44)

**Given** a equipe altera `rollout_percentage` de 5 para 25 no Django Admin
**When** a config é recarregada (TTL 5min Redis)
**Then** ~25% dos usuários passam a usar o código novo
**And** os outros ~75% continuam usando n8n (FR46)
**And** ambos coexistem acessando o mesmo Supabase (FR45)

**Given** problemas são detectados no código novo
**When** a equipe reduz `rollout_percentage` para 0
**Then** 100% do tráfego volta para n8n em até 5 minutos
**And** nenhum dado é perdido (FR45)

**Given** Django migrations
**When** executadas sobre o Supabase existente
**Then** preservam todos os dados existentes — apenas adicionam novas tabelas/colunas (FR45)
**And** n8n continua funcionando normalmente durante a migração

### Story 10.2: Shadow Mode — Comparação de Respostas

As a equipe Medway,
I want comparar respostas do código novo vs n8n lado a lado,
So that valido que o novo sistema tem qualidade igual ou superior antes de migrar.

**Acceptance Criteria:**

**Given** Shadow Mode ativo (`feature_flag:shadow_mode`, rollout_percentage > 0)
**When** uma mensagem chega de um usuário no bucket do shadow mode
**Then** o sistema processa a mensagem pelo código novo E pelo n8n em paralelo (FR44)
**And** apenas a resposta do n8n é enviada ao aluno (código novo é silencioso)
**And** ambas as respostas são salvas para comparação

**Given** respostas salvas do shadow mode
**When** a equipe acessa via Django Admin
**Then** vê lado a lado: resposta n8n vs resposta código novo, latência de cada, custo de cada (FR47)
**And** pode filtrar por: data, user, diferença de qualidade
**And** métricas agregadas: % de respostas onde código novo é melhor/igual/pior

**Given** a equipe decide que o código novo está pronto
**When** desativa shadow mode e aumenta `rollout_percentage` do `new_pipeline`
**Then** o tráfego migra gradualmente (5% → 25% → 50% → 100%)
**And** a cada fase, métricas de custo, latência e satisfação são comparadas
