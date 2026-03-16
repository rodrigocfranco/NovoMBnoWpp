# Medbrain WhatsApp (mb-wpp)

Tutor médico com IA acessível via WhatsApp Business API. Responde dúvidas médicas com **citações verificáveis** de fontes curadas (livros-texto, guidelines brasileiros, artigos PubMed) e busca web filtrada — diferencial direto frente ao ChatGPT, que não cita fontes.

Construído sobre o WhatsApp — a ferramenta que estudantes de medicina já usam no dia a dia.

---

## Índice

- [Visão Geral](#visão-geral)
- [Tech Stack](#tech-stack)
- [Arquitetura](#arquitetura)
- [Funcionalidades](#funcionalidades)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Setup Local](#setup-local)
- [Variáveis de Ambiente](#variáveis-de-ambiente)
- [Testes](#testes)
- [Deploy](#deploy)
- [Observabilidade](#observabilidade)
- [Métricas e Metas](#métricas-e-metas)

---

## Visão Geral

### Problema

Estudantes de medicina precisam de respostas rápidas e confiáveis durante plantões, estudos e preparação para provas — mas as IAs generalistas não citam fontes, e as ferramentas dedicadas exigem sair do WhatsApp.

### Solução

Um assistente médico no WhatsApp que:
- Responde com **citações Gold** (base de conhecimento curada — Harrison, guidelines SUS) e **citações Silver** (busca web verificada)
- Bloqueia automaticamente fontes de concorrentes (Medcurso, Medgrupo, etc.)
- Processa **texto, áudio e imagens**
- Gera **quizzes contextuais** para prática ativa
- Oferece **feedback por botões** (👍/👎) para melhoria contínua

### Personas

| Persona | Descrição | Tier |
|---------|-----------|------|
| **Lucas** | Estudante Medway — usa para dúvidas de estudo, plantão e provas | Premium |
| **Camila** | Profissional não-aluna — descobre o serviço organicamente | Free |
| **Ana** | Time Medway — monitora métricas, cura conteúdo, gerencia operações | Admin |

---

## Tech Stack

| Camada | Tecnologia |
|--------|-----------|
| Runtime | Python 3.12+ (asyncio) |
| Framework | Django 5.1 + DRF + adrf |
| Orquestração LLM | LangGraph 1.0 + LangChain 1.0 |
| LLM Primário | Claude Haiku 4.5 via GCP Vertex AI |
| LLM Fallback | Claude Haiku 4.5 via Anthropic Direct |
| Banco de Dados | Supabase PostgreSQL (Django ORM) |
| Cache | Redis 7 (Upstash) |
| Vector DB | Pinecone (RAG médico) |
| Observabilidade | Langfuse + structlog (JSON) |
| Hospedagem | GCP Cloud Run |
| Package Manager | uv |

---

## Arquitetura

Pipeline LangGraph StateGraph com 9 nós:

```
START → identify_user → rate_limit → process_media → load_context
     → orchestrate_llm ⇄ [tools loop] → collect_sources
     → format_response → send_whatsapp → persist → END
```

### Decisões Arquiteturais (ADRs)

| ADR | Decisão | Motivo |
|-----|---------|--------|
| 001 | Python 3.12 | Expertise do time + ecossistema AI |
| 002 | Django + DRF + adrf | Alinhamento com time Medway, Admin built-in |
| 003 | Django ORM | Migrations, admin, padrão do time |
| 005 | GCP Cloud Run | Proximidade com Vertex AI, mesmo VPC |
| 006 | Vertex AI + Anthropic fallback | 70% redução de custo vs Sonnet |
| 007 | Redis 4 camadas | Buffer, sessões, config, rate limiting |
| 010 | LangGraph + LangChain | State management, tools paralelas, prompt caching |
| 012 | `get_model(tools=)` | Nunca chamar `.bind_tools()` no retorno |
| 013 | Haiku 4.5 + prompt caching | 71% redução custo, 20% redução latência |

---

## Funcionalidades

### Core (Epic 1)
- Perguntas médicas via texto → respostas formatadas com citações
- Identificação de usuário (aluno Medway vs não-aluno)
- Mensagem de boas-vindas automática
- Debounce de mensagens rápidas
- Split de respostas longas (limite WhatsApp 4096 chars)
- Indicador de digitação durante processamento
- Contexto conversacional (últimas 20 mensagens)
- Persistência via LangGraph AsyncPostgresSaver

### Tools Médicas (Epic 2)
- **RAG médico** (Pinecone) — citações Gold `[N]`
- **Busca web** (Tavily) — citações Silver `[W-N]` com bloqueio de concorrentes
- **Verificação de artigos** via PubMed
- **Bulas de medicamentos** + interações
- **Calculadoras médicas** (CHA₂DS₂-VASc, clearance, etc.)
- Execução paralela de tools (ToolNode)

### Áudio e Imagem (Epic 3)
- Transcrição de áudio via Whisper (ambiente de plantão)
- Análise de imagens via Claude Vision

### Rate Limiting (Epic 4)
- Dual: Sliding Window (limite diário) + Token Bucket (anti-burst)
- Configurável por tier (free: 20/dia, premium: configurável)
- Transparente: usuário vê perguntas restantes + horário de reset

### Resiliência (Epic 5)
- Retry automático com backoff exponencial (LangGraph RetryPolicy)
- Fallback LLM: Vertex → Anthropic (seamless via `with_fallbacks()`)
- Mensagens amigáveis de erro + respostas parciais

### Feedback (Epic 6)
- Reply Buttons (👍/👎) — North Star Metric
- Comentário opcional no feedback
- Integração com Django Admin

### Observabilidade (Epic 7)
- CostTrackingCallback (custo por request: input, output, cache)
- Langfuse traces end-to-end
- structlog JSON com sanitização de PII
- MetricsService + AlertingService

### Configuração Dinâmica (Epic 8)
- ConfigService com hot-reload via Redis (TTL 5min)
- System prompt versionado com histórico e rollback
- Lista de concorrentes editável sem deploy

### Quiz (Epic 9)
- Geração de quiz contextual (5 alternativas)
- Sugestão automática após respostas relevantes

### Migração Gradual (Epic 10)
- Feature flags com hash-based bucketing (determinístico por usuário)
- Rollout gradual: 5% → 25% → 50% → 100%
- Shadow Mode: comparação n8n vs novo código

---

## Estrutura do Projeto

```
mb-wpp/
├── config/                          # Configurações Django
│   ├── settings/
│   │   ├── base.py                 # Config base (env vars, apps, middleware)
│   │   ├── development.py          # Overrides desenvolvimento
│   │   ├── production.py           # Overrides produção
│   │   └── test.py                 # Overrides testes
│   ├── asgi.py                     # ASGI (uvicorn)
│   └── urls.py                     # Roteamento
├── workflows/                       # App Django principal
│   ├── models.py                   # User, Message, Config, CostLog, etc.
│   ├── admin.py                    # Django Admin
│   ├── views.py                    # Webhook handler WhatsApp
│   ├── middleware/
│   │   ├── webhook_signature.py   # Validação HMAC
│   │   └── trace_id.py            # Propagação de trace ID
│   ├── services/
│   │   ├── config_service.py      # Hot-reload config
│   │   ├── feature_flags.py       # Rollout gradual
│   │   ├── cost_tracker.py        # Cálculo de custos
│   │   ├── rate_limiter.py        # Sliding window + token bucket
│   │   ├── cache_service.py       # Cache Redis com graceful degradation
│   │   ├── alerting.py            # Alertas de qualidade
│   │   └── metrics.py             # Métricas de negócio
│   ├── providers/                  # Clientes de serviços externos
│   │   ├── llm.py                 # Vertex AI + Anthropic fallback
│   │   ├── checkpointer.py        # AsyncPostgresSaver singleton
│   │   ├── redis.py               # Connection pool Redis
│   │   ├── pinecone.py            # Vector DB
│   │   ├── whatsapp.py            # Meta Cloud API
│   │   ├── langfuse.py            # Observabilidade
│   │   └── whisper.py             # Transcrição de áudio
│   ├── whatsapp/                   # Pipeline WhatsApp
│   │   ├── graph.py               # StateGraph definition
│   │   ├── state.py               # TypedDict WhatsAppState
│   │   ├── nodes/                 # 9 nós do pipeline
│   │   ├── tools/                 # LangChain @tool definitions
│   │   └── prompts/               # System prompt management
│   └── utils/
│       ├── errors.py              # Hierarquia de exceções
│       ├── formatters.py          # Formatação WhatsApp
│       ├── message_splitter.py    # Split de mensagens longas
│       └── sanitization.py        # Sanitização de PII
├── tests/                          # Suite de testes (737 testes)
│   ├── test_whatsapp/             # Testes de nodes, tools, graph
│   ├── test_services/             # Testes de services
│   ├── test_providers/            # Testes de providers
│   ├── test_models/               # Testes de models
│   ├── e2e/                       # Testes end-to-end (requer credenciais)
│   └── integration/               # Testes de integração (requer credenciais)
├── search-medway-langgraph/        # Implementação de referência do time
├── Search and Development/         # Artefatos de planejamento e implementação
│   ├── planning-artifacts/        # PRD, arquitetura, epics, ADRs
│   └── implementation-artifacts/  # Stories, retros, guias
├── pyproject.toml                  # Dependências e config de ferramentas
├── uv.lock                         # Lock file
├── Dockerfile                      # Build multi-stage
├── docker-compose.yml              # Dev local (PostgreSQL + Redis)
└── .env.example                    # Template de variáveis de ambiente
```

---

## Setup Local

### Pré-requisitos

- Python 3.12+
- Docker & Docker Compose
- [uv](https://docs.astral.sh/uv/) (package manager)

### Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/rodrigocfranco/NovoMBnoWpp.git
cd NovoMBnoWpp

# 2. Instale o uv (se ainda não tiver)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Crie o virtualenv e instale dependências
uv venv
source .venv/bin/activate
uv sync

# 4. Configure as variáveis de ambiente
cp .env.example .env
# Edite .env com suas credenciais

# 5. Suba PostgreSQL e Redis locais
docker-compose up -d

# 6. Rode as migrations
python manage.py migrate

# 7. Crie um superuser (para Django Admin)
python manage.py createsuperuser

# 8. Inicie o servidor
uvicorn config.asgi:application --reload --host 0.0.0.0 --port 8000
```

### Django Admin

Acesse `http://localhost:8000/admin/` para gerenciar configurações, prompts, custos e feedback.

---

## Variáveis de Ambiente

Veja `.env.example` para o template completo. Principais:

| Variável | Descrição |
|----------|-----------|
| `SECRET_KEY` | Django secret key |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `WHATSAPP_WEBHOOK_SECRET` | Secret para validação HMAC |
| `WHATSAPP_ACCESS_TOKEN` | Token da Meta Cloud API |
| `WHATSAPP_PHONE_NUMBER_ID` | ID do número WhatsApp |
| `VERTEX_PROJECT_ID` | Projeto GCP para Vertex AI |
| `VERTEX_LOCATION` | Região Vertex AI (ex: us-east5) |
| `GCP_CREDENTIALS` | Service account JSON |
| `ANTHROPIC_API_KEY` | API key Anthropic (fallback) |
| `PINECONE_API_KEY` | Pinecone para RAG |
| `TAVILY_API_KEY` | Tavily para busca web |
| `OPENAI_API_KEY` | OpenAI para Whisper |
| `LANGFUSE_SECRET_KEY` | Langfuse para observabilidade |

---

## Testes

```bash
# Rodar testes unitários (sem credenciais externas)
pytest tests/ -v --tb=short --ignore=tests/e2e --ignore=tests/integration

# Rodar com cobertura
pytest tests/ --cov=workflows --cov-report=html --ignore=tests/e2e --ignore=tests/integration

# Lint e formatação
ruff check .
ruff format --check .
```

**737 testes** cobrindo nodes, tools, services, providers, models, views e middleware.

Testes em `tests/e2e/` e `tests/integration/` requerem credenciais reais (PostgreSQL, GCP, Redis) e são executados no CI.

---

## Deploy

### GCP Cloud Run

```bash
# Build e deploy
gcloud run deploy mb-wpp \
  --source . \
  --region us-east1 \
  --set-env-vars="DJANGO_SETTINGS_MODULE=config.settings.production" \
  --min-instances=1 \
  --max-instances=10 \
  --memory=1Gi \
  --cpu=2 \
  --allow-unauthenticated
```

### Docker

```bash
docker build -t mb-wpp:latest .
docker run -p 8080:8080 --env-file .env mb-wpp:latest
```

---

## Observabilidade

### Custo por Request

O `CostTrackingCallback` calcula custo real por request baseado no pricing Vertex AI:

| Token Type | Custo (por MTok) |
|-----------|-----------------|
| Input | $3.00 |
| Output | $15.00 |
| Cache Read | $0.30 |
| Cache Creation | $3.75 |

### Logging

structlog com JSON rendering, sanitização automática de PII (telefone, user_id) e propagação de trace ID.

### Tracing

Langfuse para traces end-to-end — latência, tokens, custo e qualidade por request (fire-and-forget, não bloqueia o pipeline).

---

## Métricas e Metas

| Métrica | Meta M1 | Meta 12 meses |
|---------|---------|---------------|
| Latência P95 (texto) | < 8s | < 5s |
| Latência P95 (áudio) | < 12s | < 10s |
| Uptime | 99.5% | 99.9% |
| Taxa de erro | < 2% | < 0.5% |
| Custo/conversa | < $0.03 | < $0.03 |
| Cache hit rate | > 70% | > 90% |
| Satisfação (👍/👎) | > 85% | > 90% |

---

## Licença

Projeto proprietário — Medway / Medbrain. Todos os direitos reservados.
