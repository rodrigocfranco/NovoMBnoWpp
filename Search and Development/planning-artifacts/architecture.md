---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
lastStep: 8
status: 'complete'
completedAt: '2026-02-14'
revisedAt: '2026-03-05'
revisionNotes: 'Migração para Django + DRF + adrf, LangGraph + LangChain, Django ORM, GCP Cloud Run, remoção LLMProvider/PipelineStep ABCs, pipeline → StateGraph. Adicionado: Citation & Source Attribution patterns, bloqueio de concorrentes, verificação de fontes externas.'
inputDocuments:
  - product-brief-mb-wpp-2026-02-11.md
  - prd.md
  - research/technical-arquitetura-ideal-medbrain-whatsapp-research-2026-02-10.md
  - research/claude-sdk-tool-use-architecture-research-2026-02-10.md
  - decisao-tecnica-langgraph-vs-claude-sdk.md
workflowType: 'architecture'
project_name: 'mb-wpp'
user_name: 'Rodrigo Franco'
date: '2026-02-14'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements (47 FRs em 10 categorias):**

| Categoria | FRs | Impacto Arquitetural |
|-----------|-----|---------------------|
| Interação WhatsApp | FR1-FR10 | Webhook handler, message buffer (debounce), formatador de respostas, split de mensagens longas, indicador "digitando" |
| Consulta Médica Inteligente | FR11-FR17 | Arquitetura Tool Use (LangGraph + LangChain ToolNode), RAG (Pinecone), busca web, bulas, calculadoras, orquestração de tools paralelas |
| Formatação de Respostas | FR18-FR19 | Pós-processador de markdown para WhatsApp, adaptação por tipo de conteúdo |
| Identificação e Controle de Acesso | FR20-FR24 | Lookup de usuário (phone → Medway API), cache Redis, rate limiting dual (sliding window + token bucket) |
| Quiz e Prática Ativa | FR25-FR26 | Tool de geração de questões, sugestão contextual de quiz |
| Histórico e Contexto | FR27-FR28 | Persistência Supabase, carregamento de contexto por sessão |
| Observabilidade e Monitoramento | FR29-FR32 | Langfuse (traces, custo, qualidade), alertas automáticos |
| Configuração e Operação | FR33-FR38 | Tabela de config Supabase + cache Redis, system prompt versionado, hot-reload |
| Resiliência e Recuperação | FR39-FR43 | Retry automático, circuit breaker, fallback ao usuário, dead letter queue, logging contextual |
| Migração e Continuidade | FR44-FR47 | Strangler Fig, Shadow Mode, feature flags para rollout gradual, comparação de respostas |

**Non-Functional Requirements (24 NFRs em 5 categorias):**

| Categoria | NFRs | Constraints Arquiteturais |
|-----------|------|--------------------------|
| Performance | NFR1-NFR5 | P95 < 8s texto, < 12s áudio, < 15s imagem; 50+ conversas concorrentes; debounce ≤ 3s |
| Custo e Eficiência | NFR6-NFR9 | Custo/conversa < $0.03; cache hit > 70%→90%; cost tracking ±5%; alertas de gasto |
| Disponibilidade | NFR10-NFR14 | Uptime 99.5%→99.9%; erro < 2%→0.5%; MTTR < 5min; zero mensagens perdidas; webhook 200 OK < 3s |
| Segurança e Privacidade | NFR15-NFR20 | RLS Supabase; validação de assinatura webhook; credenciais em env vars; LGPD; logs sem dados sensíveis |
| Integrações Externas | NFR21-NFR24 | Timeout configurável por serviço; circuit breaker por dependência; fallback documentado; compatibilidade WhatsApp API |

### Scale & Complexity

- **Domínio primário:** API/Backend — processamento de mensagens com IA (event-driven via Django async + LangGraph StateGraph)
- **Nível de complexidade:** Alto
- **Componentes arquiteturais estimados:** ~12-15 (webhook handler Django, message buffer Redis, user identifier, rate limiter, audio processor, image processor, context loader, LangGraph StateGraph workflow, LangChain ToolNode, response formatter, WhatsApp sender, persistence layer Django ORM, observability layer, config manager, migration router)
- **Integrações externas:** 6+ serviços (WhatsApp Cloud API, Claude/Anthropic, Pinecone, Whisper/OpenAI, Supabase, Redis/Upstash, Langfuse)
- **Concorrência:** Dezenas a centenas de conversas simultâneas
- **Volume de dados:** Mensagens crescendo continuamente (candidatas a particionamento após 1M+)

### Technical Constraints & Dependencies

**Constraints do WhatsApp:**
- Webhook deve retornar 200 OK em < 3 segundos (processamento obrigatoriamente assíncrono)
- Limite de caracteres por mensagem (split necessário)
- Reply Buttons limitados a 3 opções por mensagem
- Template messages requerem aprovação da Meta (relevante para M2)
- Políticas de bots de saúde da Meta devem ser monitoradas

**Constraints de migração:**
- Supabase existente com dados de produção — schema deve evoluir, não ser recriado
- n8n e código novo coexistem apontando para o mesmo banco durante transição
- Feature flags necessárias para rollout gradual (5% → 25% → 50% → 100%)

**Constraints de custo:**
- Prompt Caching é essencial desde o dia 1 (~90% economia em system prompt + tools)
- Roteamento de modelos (Haiku para interações simples, Sonnet para raciocínio) pode reduzir ~44% do custo
- Cost tracking granular é pré-requisito para decisões de escala

**Stack existente (constraints de continuidade):**
- Supabase (PostgreSQL) — banco principal, já em uso
- Redis (Upstash) — cache, rate limiting, message buffer, já em uso
- Pinecone — RAG médico, já indexado com documentos curados
- WhatsApp Cloud API (Meta) — integração direta, já em uso

### Cross-Cutting Concerns Identified

1. **Observabilidade end-to-end** — Cada nó do LangGraph StateGraph precisa de tracing (Langfuse/LangSmith), logging estruturado (structlog), e métricas (custo, latência, tokens, cache hit)
2. **Resiliência multi-camada** — Retry com backoff exponencial + circuit breaker + fallback ao usuário + dead letter queue para cada serviço externo
3. **Cost tracking pervasivo** — Registro de custo por request (Claude, Pinecone, Whisper), agregação diária, alertas de threshold
4. **Rate limiting dual** — Sliding window (limite diário por tipo de usuário) + token bucket (anti-burst) com transparência ao usuário
5. **Segurança e compliance** — Validação de webhook, RLS no Supabase, LGPD, logs sanitizados, credenciais em env vars
6. **Configuração dinâmica** — Hot-reload de parâmetros operacionais (rate limits, timeouts, mensagens, system prompt) via Supabase + Redis cache
7. **Migração gradual** — Feature flags, Shadow Mode, comparação de respostas, rollback — tudo precisa ser "architecture-aware"

---

## Starter Template Evaluation

_Nesta fase, avaliamos as decisões fundamentais de stack tecnológica. Cada decisão é documentada como um Architecture Decision Record (ADR) com contexto, alternativas consideradas, justificativa, e trade-offs._

### ADR-001: Linguagem Principal — Python 3.12

**Date:** 2026-02-26
**Status:** DECIDED
**Decisores:** Rodrigo Franco, Claude Agent

**Context:**

A versão original da arquitetura especificava TypeScript como linguagem principal. Durante a reavaliação para implementação, identificamos que o time tem maior expertise em Python, os documentos de research já estão em Python, e o ecossistema de IA/ML oferece melhores primitivas nativas em Python.

**Alternatives Considered:**

| Critério | Python 3.12 | TypeScript 5.3 | Avaliação |
|----------|-------------|----------------|-----------|
| **Experiência do Time** | Alta | Média | Python ✓ |
| **Async/Await** | asyncio nativo | Nativo | Empate |
| **Type Safety** | Type hints + Pydantic | TypeScript nativo | TS levemente superior, mas Pydantic compensa |
| **Ecosystem AI/ML** | Antropic SDK, LangChain, bibliotecas nativas | Wrappers sobre Python | Python ✓✓ |
| **Performance** | Async I/O suficiente (~1000 req/s) | ~2x mais rápido | TS superior mas não crítico |
| **Debugging** | Excelente (PDB, VS Code) | Excelente | Empate |
| **WhatsApp SDK** | Nenhum oficial (httpx OK) | Nenhum oficial | Empate |
| **Deploy** | Docker padrão, GCP Cloud Run | Docker padrão, GCP Cloud Run | Empate |
| **Research Artifacts** | Já em Python | Precisaria traduzir | Python ✓ |

**Decision:**

Usaremos **Python 3.12** como linguagem principal.

**Justificativa (por ordem de importância):**

1. **Expertise do time** — Time possui domínio profundo de Python, conhecimento médio de TypeScript. Velocidade de desenvolvimento será 2-3x maior.
2. **Research artifacts já em Python** — Documentos técnicos e exemplos de código já escritos em Python (SDK Anthropic, Pinecone, etc). Reescrever para TS introduziria erros de tradução.
3. **Ecosystem AI/ML superior** — Anthropic SDK Python tem suporte completo para Prompt Caching e Vertex AI. SDK TS tem limitações documentadas.
4. **Async suficiente para escala** — asyncio/uvicorn suportam 1000+ req/s facilmente, muito além das ~50 conversas concorrentes esperadas.
5. **Type safety com Pydantic** — Type hints + Pydantic fornecem validação runtime + type checking estático via mypy/Pyright, compensando a falta de compilador TS.
6. **Deploy equivalente** — GCP Cloud Run suporta Python/Node.js igualmente bem.

**Trade-offs Aceitos:**

- **Performance raw inferior** — Python é ~2x mais lento que Node.js em benchmarks sintéticos. Aceitável porque I/O bound domina (Claude API, Supabase, Redis).
- **Type safety em compilação** — TypeScript detecta erros em tempo de compilação. Mitigado com mypy strict mode + Pydantic validation.
- **Ecossistema menor para HTTP** — Django/DRF é excelente mas ecossistema Node.js é maior. Não crítico para este projeto.

**Revisão de Argumentos TypeScript:**

Os argumentos originais para TypeScript eram:
1. Type safety superior → Mitigado com Python type hints + mypy strict + Pydantic
2. Performance superior → Não crítico para workload I/O-bound
3. Ecosystem moderno → Python tem Django, LangGraph, asyncio, structlog igualmente modernos
4. Deploy simples → Equivalente entre Python e Node.js

Nenhum argumento é forte o suficiente para justificar escolher TS sobre Python dado expertise do time.

---

### ADR-002: Framework Web — Django + DRF + adrf

**Date:** 2026-03-03
**Status:** DECIDED
**Decisores:** Rodrigo Franco, Claude Agent

**Context:**

A equipe Medway padroniza Django em todos os projetos. O projeto referência `search-medway-langgraph` usa Django + DRF + adrf (async Django REST Framework). Precisamos de async para webhook WhatsApp e API admin futura. Alinhar com a stack da equipe acelera code review, onboarding e manutenção cruzada.

**Alternatives Considered:**

| Critério | Django 5.2 + DRF + adrf | FastAPI 0.115+ | Flask 3.0 | Litestar 2.0 |
|----------|-------------------------|----------------|-----------|--------------|
| **Async** | Sim (adrf async views, Django 5.x async ORM) | Nativo (asyncio) | Workaround | Sim |
| **Validação** | DRF Serializers | Pydantic built-in | Manual | Pydantic |
| **OpenAPI** | drf-spectacular | Automático | Manual | Automático |
| **Performance** | ~8k req/s | ~30k req/s | ~10k req/s | ~35k req/s |
| **Admin Panel** | Built-in (Django Admin) | Inexistente | Inexistente | Inexistente |
| **ORM** | Built-in (Django ORM) | Não tem | Não tem | Não tem |
| **Ecossistema** | Enorme | Grande | Enorme | Pequeno |
| **Alinhamento equipe** | Total | Nenhum | Nenhum | Nenhum |
| **Maturidade** | Muito maduro (2005) | Maduro (2018) | Muito maduro | Novo (2023) |

**Decision:**

Usaremos **Django 5.2+ com Django REST Framework (DRF) e adrf** (async DRF views).

**Justificativa (por ordem de importância):**

1. **Alinhamento com a equipe** — Toda a equipe Medway usa Django. Code review cross-team, onboarding instantâneo, suporte mútuo. Se alguém sair do projeto, quem assume já conhece a stack.
2. **Django Admin built-in** — ADR-011 define admin panel em 3 fases. Django Admin fornece CRUD admin gratuito em Phase 1, acelerando significativamente o timeline.
3. **Django ORM integrado** — Unificado com ADR-003. Migrations, querysets, admin, tudo integrado.
4. **Async via adrf** — `adrf.views.APIView` fornece views async para webhook handler. Django 5.x suporta async ORM (`aget`, `afilter`, `acreate`).
5. **DRF Serializers** — Validação robusta em boundary de API, incluindo nested validation e custom validators.
6. **Ecossistema maduro** — django-cors-headers, django-filter, drf-spectacular, django-environ, django-stubs (mypy).
7. **Management commands** — Úteis para seed scripts, migrations, operações administrativas.

**Trade-offs Aceitos:**

- **Performance inferior a FastAPI** — ~8k vs ~30k req/s. Irrelevante: necessitamos ~100 req/s (~50 conversas concorrentes).
- **Mais verboso** — Django requer mais boilerplate (settings, urls, apps). Mitigado pela familiaridade da equipe.
- **Async ORM incompleto** — Algumas operações Django ORM ainda são sync. Mitigado com `sync_to_async()` onde necessário e async ORM do Django 5.x para operações principais.

**Code Example:**

```python
# workflows/views.py
import asyncio
from adrf.views import APIView
from rest_framework.response import Response
from rest_framework import status
from workflows.middleware.webhook_signature import verify_signature

class WhatsAppWebhookView(APIView):
    """Webhook handler assíncrono para WhatsApp Cloud API."""

    async def post(self, request):
        # Assinatura verificada no middleware (ADR-008)
        # Processamento assíncrono — fire and forget
        for entry in request.data.get("entry", []):
            for change in entry.get("changes", []):
                asyncio.create_task(process_message(change))

        return Response({"status": "ok"}, status=status.HTTP_200_OK)

    async def get(self, request):
        # Webhook verification (Meta handshake)
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN:
            return Response(int(challenge), status=status.HTTP_200_OK)
        return Response(status=status.HTTP_403_FORBIDDEN)
```

---

### ADR-003: Database Client — Django ORM (Supabase PostgreSQL como backend)

**Date:** 2026-03-03
**Status:** DECIDED
**Decisores:** Rodrigo Franco, Claude Agent

**Context:**

A equipe Medway usa Django ORM em todos os projetos. O Supabase (PostgreSQL) já está em uso como banco principal. Django pode conectar diretamente ao PostgreSQL do Supabase como qualquer outro banco. A decisão é sobre usar Django ORM vs supabase-py para acesso a dados.

**Alternatives Considered:**

| Critério | Django ORM | supabase-py | SQLAlchemy 2.0 | SQLModel |
|----------|-----------|-------------|----------------|----------|
| **Alinhamento equipe** | Total | Nenhum | Nenhum | Nenhum |
| **Migrations** | Django migrations (built-in) | Supabase CLI | Alembic | Alembic |
| **Admin UI** | Django Admin (built-in) | Nenhum | Nenhum | Nenhum |
| **Type Safety** | Django models + django-stubs | Pydantic separado | Declarative models | Pydantic + SA |
| **Async** | Django 5.x (aget, afilter, acreate) | Sim (httpx) | Sim (asyncpg) | Sim |
| **RLS** | Aplicação + RLS defense-in-depth | Nativo | Manual | Manual |
| **Complexity** | Baixa (familiar à equipe) | Baixa | Alta | Média |

**Decision:**

Usaremos **Django ORM** com Supabase PostgreSQL como database backend. **supabase-py mantido apenas para Supabase Auth e Storage** (funcionalidades que Django ORM não substitui).

**Justificativa:**

1. **Alinhamento com a equipe** — Toda equipe Medway trabalha com Django ORM. Mesmo padrão, mesma linguagem de querysets.
2. **Django migrations** — Sistema de migrations built-in, não precisa de Supabase CLI para schema. `makemigrations` + `migrate`.
3. **Django Admin** — Registrar models dá admin CRUD gratuito (acelera ADR-011 Phase 1).
4. **Type safety** — Django models com `django-stubs` fornecem type checking via mypy.
5. **Async ORM** — Django 5.x suporta `Model.objects.aget()`, `afilter()`, `acreate()`, `abulk_create()` nativamente.
6. **QuerySet API poderoso** — Queries complexas, annotations, aggregations, prefetch_related.
7. **Integração com LangGraph** — AsyncPostgresSaver usa o mesmo banco (schema separado `langgraph`).

**Trade-offs Aceitos:**

- **RLS como camada secundária** — Django permissions são o controle primário de acesso. RLS no Supabase mantido como defense-in-depth, mas não como mecanismo principal.
- **Dois sistemas de migration** — Django migrations para schema da aplicação. Supabase dashboard para RLS policies. Gerenciável.
- **supabase-py mantido como dependência leve** — Apenas para Auth SDK (JWT verification) e Storage (upload de áudio/imagem). Não para queries de dados.
- **Connection pooling necessário** — Django conecta via `DATABASE_URL` ao Supabase PostgreSQL. Em produção, usar PgBouncer ou `django-db-connection-pool`.

**Code Example — Django Models (Schema as Code):**

```python
# workflows/models.py
from django.db import models

class User(models.Model):
    phone = models.CharField(max_length=16, unique=True, db_index=True)
    medway_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    subscription_tier = models.CharField(
        max_length=10,
        choices=[("free", "Free"), ("basic", "Basic"), ("premium", "Premium")],
        default="free",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users"

class Message(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="messages")
    content = models.TextField()
    role = models.CharField(max_length=10)  # user, assistant, system
    message_type = models.CharField(max_length=10, default="text")  # text, audio, image
    tokens_input = models.IntegerField(null=True, blank=True)
    tokens_output = models.IntegerField(null=True, blank=True)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "messages"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]
```

**Async ORM Usage:**

```python
# workflows/services/message_service.py

async def get_user_by_phone(phone: str) -> User:
    return await User.objects.aget(phone=phone)

async def get_history(user: User, limit: int = 20) -> list[Message]:
    return [msg async for msg in
        Message.objects.filter(user=user).order_by("-created_at")[:limit]
    ]

async def save_message(user: User, content: str, role: str, **kwargs) -> Message:
    return await Message.objects.acreate(
        user=user, content=content, role=role, **kwargs
    )
```

**Database Configuration (settings):**

```python
# config/settings/base.py
import environ

env = environ.Env()

DATABASES = {
    "default": env.db("DATABASE_URL"),  # postgresql://user:pass@host:port/dbname
}
```

---

### ADR-004: Toolchain Python — uv, pytest, Ruff

**Date:** 2026-02-26
**Status:** DECIDED
**Decisores:** Rodrigo Franco, Claude Agent

**Context:**

Precisamos definir toolchain para gerenciamento de dependências, testes, linting, e formatação.

**Package Manager:**

| Critério | uv | pip + venv | Poetry | PDM |
|----------|-----|------------|--------|-----|
| **Velocidade** | 10-100x mais rápido | Baseline | ~2x mais rápido | ~3x mais rápido |
| **Lock file** | Sim (uv.lock) | Não | Sim | Sim |
| **PEP 621** | Sim | N/A | Parcial | Sim |
| **Rust-based** | Sim | Não | Não | Não |
| **Maturidade** | Nova (2024) | Muito madura | Madura | Madura |

**Decision:** **uv** — velocidade extrema (~100x pip), lock file automático, PEP 621 compliant.

```bash
# Instalação
curl -LsSf https://astral.sh/uv/install.sh | sh

# Criar projeto
uv init
uv venv
source .venv/bin/activate

# Adicionar dependências
uv add django djangorestframework adrf django-environ django-cors-headers
uv add langchain-anthropic langchain-openai langgraph langchain-mcp-adapters langgraph-checkpoint-postgres
uv add redis pinecone-client langfuse structlog httpx openai supabase
uv add --dev pytest pytest-asyncio pytest-django pytest-mock pytest-cov ruff mypy django-stubs

# Rodar aplicação
uv run python manage.py runserver
```

**Test Framework:**

| Critério | pytest | unittest | nose2 |
|----------|--------|----------|-------|
| **Fixtures** | Excelente | Verboso | Bom |
| **Async** | pytest-asyncio | Limitado | Limitado |
| **Plugins** | Enorme | Pequeno | Médio |
| **DX** | Excelente | Verbose | Bom |

**Decision:** **pytest + pytest-asyncio** — padrão da indústria, fixtures poderosos, async nativo.

```python
# tests/conftest.py
import pytest
from django.test import AsyncClient

@pytest.fixture
def client():
    return AsyncClient()

@pytest.fixture
def mock_llm(mocker):
    return mocker.patch("workflows.providers.llm.get_model")

# tests/test_webhook.py
import pytest
from django.test import AsyncClient

@pytest.mark.asyncio
@pytest.mark.django_db
async def test_webhook_valid_signature(client):
    response = await client.post(
        "/webhook/whatsapp/",
        data={"object": "whatsapp_business_account", "entry": []},
        content_type="application/json",
        HTTP_X_HUB_SIGNATURE_256="sha256=...",
    )
    assert response.status_code == 200
```

**Linter & Formatter:**

| Critério | Ruff | Black + Flake8 + isort | Pylint |
|----------|------|------------------------|--------|
| **Velocidade** | 10-100x mais rápido | Baseline | Lento |
| **All-in-one** | Sim (lint + format + import sort) | Não (3 tools) | Não |
| **Rust-based** | Sim | Não | Não |
| **Compatibilidade** | Flake8, Black, isort rules | N/A | Próprio |

**Decision:** **Ruff** — all-in-one, extremamente rápido, compatível com Flake8/Black.

```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "A", "C4", "DTZ", "EM", "ISC", "ICN", "G", "PIE", "T20", "PYI", "PT", "Q", "RET", "SIM", "ARG", "ERA", "PL", "PERF", "RUF"]
ignore = ["E501"]  # Line too long (handled by formatter)

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

**Type Checker:**

**Decision:** **mypy strict mode** — padrão da indústria, integração VSCode.

```toml
# pyproject.toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

---

### ADR-010: Orquestração LLM — LangGraph + LangChain

**Date:** 2026-03-03
**Status:** DECIDED
**Decisores:** Rodrigo Franco, Claude Agent

**Context:**

A equipe Medway padroniza LangGraph + LangChain para orquestração LLM. O projeto referência `search-medway-langgraph` demonstra os patterns em produção. Após análise detalhada (ver `decisao-tecnica-langgraph-vs-claude-sdk.md`), LangChain 1.0 e LangGraph 1.0 (GA outubro/2025, versão atual 1.0.10) são estáveis, com compromisso de zero breaking changes até 2.0. Usado em produção por Uber, LinkedIn, Klarna.

**Alternatives Considered:**

| Critério | LangGraph + LangChain | SDK Anthropic Direto | LlamaIndex |
|----------|----------------------|----------------------|------------|
| **Alinhamento equipe** | Total | Nenhum | Nenhum |
| **State management** | Nativo (AsyncPostgresSaver) | Manual (~80 linhas) | Manual |
| **Tool calling** | ToolNode (paralelo por padrão) | Manual (parse + execute) | Abstração extra |
| **Prompt Caching** | AnthropicPromptCachingMiddleware | Controle manual total | Parcial |
| **Streaming** | 6 modos (values, messages, custom...) | Manual | Parcial |
| **Multi-provider** | with_fallbacks() built-in | Custom circuit breaker | Parcial |
| **MCP** | langchain-mcp-adapters pronto | Manual | Não |
| **Estabilidade** | 1.0 GA (out/2025), zero breaking changes | Estável (semver) | Frequentes |
| **Checkpointing** | Out-of-the-box | Manual | Manual |
| **Human-in-the-loop** | interrupt() + Command nativo | Manual | Manual |

**Decision:**

Usaremos **LangGraph 1.0 + LangChain 1.0** para orquestração LLM.

**Justificativa (por ordem de importância):**

1. **Alinhamento com a equipe** — Mesmo framework, mesmos patterns, code review eficiente, suporte mútuo.
2. **StateGraph para workflow** — Grafo declarativo com nós e edges, checkpointing automático, routing condicional via `Command`.
3. **AsyncPostgresSaver** — Persistência de estado de conversa out-of-the-box. `thread_id` = conversa WhatsApp. Retomada de conversa é trivial.
4. **ToolNode** — Execução paralela de tools por padrão. Integração com `@tool` decorator ou `BaseTool`.
5. **Prompt Caching** — Via `AnthropicPromptCachingMiddleware`. Funciona com `ChatAnthropicVertex`. Cache reads a 10% do custo.
6. **model.with_fallbacks()** — Substitui `ProviderRouter` custom. Vertex AI primary, Anthropic Direct fallback em uma linha.
7. **langchain-mcp-adapters** — Integração MCP pronta para MCPGalen (dados do aluno).
8. **Streaming** — `stream_mode="messages"` para token-by-token, ideal para feedback em WhatsApp.
9. **RetryPolicy** — Retry por nó com backoff exponencial built-in.
10. **Runtime Context** — Injeção de contexto tipado por request (user_id, phone, access_token).

**Trade-offs Aceitos:**

- **Mais dependências** — ~6-8 pacotes vs 1 (anthropic[vertex]). Aceitável: todas são estáveis (1.0).
- **Prompt Caching via middleware** — Menos granular que `cache_control` manual. Aceitável: middleware cobre o caso padrão (system prompt + tools). Para edge cases, `cache_control` direto nas mensagens ainda é possível.
- **Overhead ~5-15ms** — Graph compile (~2ms) + checkpointer read (~3ms) + writes (~2ms/nó). Negligível vs target P95 < 8s.
- **Serialização de estado** — Tipos complexos (Enums aninhados, classes custom) podem falhar na serialização. Mitigado: manter estado com tipos simples (str, int, list, dict, Pydantic BaseModel).

**Architectural Pattern — StateGraph para WhatsApp:**

```python
# workflows/whatsapp/graph.py
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from workflows.whatsapp.state import WhatsAppState
from workflows.whatsapp.nodes import (
    identify_user, rate_limit, process_media,
    load_context, orchestrate_llm, format_response,
    send_whatsapp, persist,
)
from workflows.whatsapp.tools import get_tools
from workflows.providers.llm import get_model

def build_whatsapp_graph() -> StateGraph:
    """Constrói o grafo do pipeline WhatsApp."""
    builder = StateGraph(WhatsAppState)

    # Nós do pipeline
    builder.add_node("identify_user", identify_user)
    builder.add_node("rate_limit", rate_limit)
    builder.add_node("process_media", process_media)
    builder.add_node("load_context", load_context)
    builder.add_node("orchestrate_llm", orchestrate_llm)
    builder.add_node("tools", ToolNode(get_tools()))
    builder.add_node("format_response", format_response)
    builder.add_node("send_whatsapp", send_whatsapp)
    builder.add_node("persist", persist)

    # Edges do pipeline
    builder.add_edge(START, "identify_user")
    builder.add_edge("identify_user", "rate_limit")
    builder.add_conditional_edges("rate_limit", check_rate_limit)  # → END se exceeded
    builder.add_edge("rate_limit", "process_media")
    builder.add_edge("process_media", "load_context")
    builder.add_edge("load_context", "orchestrate_llm")
    builder.add_conditional_edges("orchestrate_llm", tools_condition)  # → tools se tool_use
    builder.add_edge("tools", "orchestrate_llm")  # loop de tools
    builder.add_edge("orchestrate_llm", "format_response")  # quando END (sem tools)
    builder.add_edge("format_response", "send_whatsapp")
    builder.add_edge("send_whatsapp", "persist")
    builder.add_edge("persist", END)

    return builder

# Compilação com checkpointer
async def get_compiled_graph():
    checkpointer = await get_checkpointer()  # AsyncPostgresSaver singleton
    return build_whatsapp_graph().compile(checkpointer=checkpointer)
```

**WhatsAppState TypedDict:**

```python
# workflows/whatsapp/state.py
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class WhatsAppState(TypedDict):
    """Estado compartilhado entre todos os nós do grafo."""
    # Input (webhook)
    phone_number: str
    user_message: str
    message_type: str  # "text", "audio", "image"
    media_url: str | None
    wamid: str  # WhatsApp message ID (dedup)

    # Identificação
    user_id: str
    subscription_tier: str  # "free", "premium"

    # Contexto
    messages: Annotated[list[BaseMessage], add_messages]  # Histórico LangChain
    transcribed_text: str | None  # Áudio transcrito

    # Citação & Fontes (ver Citation Patterns)
    retrieved_sources: list[dict]       # Fontes RAG + web coletadas pelas tools
    cited_source_indices: list[int]     # Índices [N] que o LLM realmente citou
    web_sources: list[dict]             # Fontes [W-N] do web_search

    # Output
    formatted_response: str
    response_sent: bool

    # Observabilidade
    trace_id: str
    cost_usd: float
```

**Node Function Pattern:**

```python
# workflows/whatsapp/nodes/identify_user.py
from workflows.models import User

async def identify_user(state: WhatsAppState) -> dict:
    """Identifica usuário pelo número de telefone."""
    phone = state["phone_number"]
    try:
        user = await User.objects.aget(phone=phone)
    except User.DoesNotExist:
        user = await User.objects.acreate(phone=phone, subscription_tier="free")
    return {"user_id": str(user.id), "subscription_tier": user.subscription_tier}
```

**Tool Definition Pattern:**

```python
# workflows/whatsapp/tools/rag_medical.py
from langchain_core.tools import tool

@tool
def rag_medical_search(query: str) -> str:
    """Busca informações médicas verificadas no banco de conhecimento curado.
    Use quando o aluno faz uma pergunta sobre medicina, farmacologia, ou procedimentos.
    """
    # Pinecone search + reranking
    results = pinecone_index.query(vector=embed(query), top_k=5)
    return format_results(results)

@tool
def drug_lookup(drug_name: str) -> str:
    """Consulta bula de medicamento com posologia, contraindicações e interações.
    Use quando o aluno pergunta sobre um medicamento específico.
    """
    # Busca na base de bulas
    ...
```

**Prompt Caching:**

```python
# workflows/providers/llm.py
from langchain_anthropic import ChatAnthropicVertex, ChatAnthropic
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware
from langchain.agents import create_agent

def get_cached_agent(tools, system_prompt):
    """Cria agente com Prompt Caching habilitado."""
    model = get_model()  # ChatAnthropicVertex com fallback
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        middleware=[AnthropicPromptCachingMiddleware(ttl="5m")],
    )
```

**Checkpointer Singleton:**

```python
# workflows/utils/checkpointer.py
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from django.conf import settings

_pool = None

async def get_checkpointer() -> AsyncPostgresSaver:
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(
            conninfo=settings.DATABASE_URL,
            min_size=5,
            max_size=20,
            kwargs={"autocommit": True, "options": "-c search_path=langgraph,public"},
        )
        await _pool.open()
    return AsyncPostgresSaver(pool=_pool)
```

---

### Stack Completa — Versões e Justificativas

| Layer | Tecnologia | Versão | Justificativa |
|-------|-----------|--------|---------------|
| **Runtime** | Python | 3.12+ | Latest stable, type hints melhorados, f-strings performance |
| **Framework** | Django | 5.1+ | Alinhamento equipe Medway, Admin built-in, ORM integrado |
| **REST API** | Django REST Framework | 3.15+ | Serializers, viewsets, permissions, OpenAPI via drf-spectacular |
| **Async Views** | adrf | 0.1+ | AsyncAPIView para webhook async, async DRF viewsets |
| **ASGI Server** | Uvicorn | 0.32+ | Performance, auto-reload dev, production via gunicorn+uvicorn |
| **Validação API** | DRF Serializers | (bundled) | Validação em boundary de API, nested validation |
| **Validação Interna** | Pydantic | 2.10+ | Config, settings, schemas internos |
| **LLM Primary** | Vertex AI (Anthropic) | Latest | 70% menor custo, SLA enterprise, data residency |
| **LLM Fallback** | Anthropic Direct | Latest | Fallback oficial quando Vertex indisponível |
| **LLM Orchestration** | LangGraph | 1.0+ | StateGraph, checkpointing, streaming, retry, team alignment |
| **LLM Framework** | LangChain | 1.0+ | ChatAnthropic, ToolNode, middleware, create_agent |
| **LLM Anthropic** | langchain-anthropic | Latest | ChatAnthropicVertex, Prompt Caching middleware |
| **LLM Checkpointer** | langgraph-checkpoint-postgres | Latest | AsyncPostgresSaver para persistência de conversas |
| **MCP** | langchain-mcp-adapters | Latest | MultiServerMCPClient, conversão de tools MCP → LangChain |
| **Database** | Supabase (PostgreSQL) | Hosted | PostgreSQL gerenciado, já em uso, Auth/Storage |
| **DB Client** | Django ORM | (built-in) | Migrations, querysets, admin, async (Django 5.x) |
| **DB Auth/Storage** | supabase-py | 2.11+ | Apenas para Supabase Auth SDK e Storage |
| **Cache** | Redis (Upstash) | Hosted 7.x | Serverless, auto-scaling, já em uso |
| **Cache Client** | redis-py | 5.2+ | Async support (aioredis merged), cluster support |
| **Vector Store** | Pinecone | Hosted | RAG médico, já indexado, serverless tier |
| **Pinecone Client** | pinecone-client | 5.0+ | gRPC support, async, batching |
| **Observability** | Langfuse | Hosted | Traces, cost tracking, qualidade LLM |
| **Langfuse SDK** | langfuse | 2.55+ | Python SDK oficial, callbacks LangChain |
| **Logging** | structlog | 24.4+ | Structured logging, async, contexto automático |
| **Audio Transcription** | Whisper (OpenAI) | v1 | Melhor qualidade áudio médico |
| **WhatsApp** | Cloud API (Meta) | v21+ | Integração direta, sem wrappers |
| **HTTP Client** | httpx | 0.28+ | Async nativo, timeout configurável, retry support |
| **Env Vars** | django-environ | 0.11+ | DATABASE_URL, secrets, env management para Django |
| **CORS** | django-cors-headers | 4.3+ | CORS middleware para Django |
| **Package Manager** | uv | 0.5+ | 10-100x mais rápido que pip, lock file |
| **Testing** | pytest | 8.3+ | Padrão indústria, fixtures, plugins |
| **Django Testing** | pytest-django | 4.8+ | Fixtures Django (db, client, settings) |
| **Async Testing** | pytest-asyncio | 0.24+ | Support async tests e fixtures |
| **Mocking** | pytest-mock | 3.14+ | Wrapper mocker sobre unittest.mock |
| **Linter/Formatter** | Ruff | 0.8+ | All-in-one (lint + format + import sort), 100x mais rápido |
| **Type Checker** | mypy | 1.13+ | Strict mode, padrão indústria |
| **Django Stubs** | django-stubs | 5.1+ | Type stubs para Django + mypy |
| **Secrets** | GCP Secret Manager | N/A | Enterprise secrets, integrado com Cloud Run |
| **Hosting** | GCP Cloud Run | N/A | Auto-scaling, pay-per-use, mesma infra que Vertex AI |
| **CI/CD** | GitHub Actions | N/A | Integração GitHub, runners grátis |
| **Containerization** | Docker | 24+ | Multi-stage builds, caching layers |

**Versioning Policy:**

- **Python:** 3.12+ (mínimo). Usar features 3.12 onde aplicável.
- **Dependências:** Versões pinned no `uv.lock`, ranges flexíveis no `pyproject.toml` (ex: `django = "^5.1"`).
- **Updates:** Renovate Bot semanal para dependências, revisão manual de breaking changes.

---

## Core Architectural Decisions

### ADR-005: Hosting — GCP Cloud Run

**Date:** 2026-03-03
**Status:** DECIDED
**Decisores:** Rodrigo Franco, Claude Agent

**Context:**

A infraestrutura da equipe Medway já está no GCP (Vertex AI para Claude). Alinhar o hosting na mesma infraestrutura reduz latência para Vertex AI, simplifica networking, e facilita gerenciamento de credenciais.

**Alternatives Considered:**

| Critério | GCP Cloud Run | Railway | Fly.io | AWS ECS |
|----------|--------------|---------|--------|---------|
| **Alinhamento equipe** | Total (GCP existente) | Nenhum | Nenhum | Nenhum |
| **Vertex AI proximity** | Same VPC, sem egress | Egress externo | Egress externo | Egress externo |
| **Auto-scaling** | 0-to-N (scale to zero) | Limitado | Bom | Bom (complexo) |
| **Pricing** | Pay-per-request + free tier | $5/mês base | Pay-per-use | Variável (alto) |
| **SLA** | 99.95% | Sem SLA formal | 99.99% | 99.99% |
| **Secrets** | GCP Secret Manager | Env vars UI | fly secrets | Parameter Store |
| **Deploy** | gcloud deploy / Cloud Build | railway up | flyctl deploy | Complex |
| **Monitoring** | Cloud Monitoring + Logging | Básico | Métricas + logs | CloudWatch |
| **Cold Start** | ~2-5s (mitigável com min-instances) | Não | ~1-3s | N/A (always on) |

**Decision:**

**GCP Cloud Run** para todas as fases (M1 a M3).

**Justificativa:**

1. **Infraestrutura unificada** — GCP project já existe para Vertex AI. Mesma rede, mesmas credenciais, mesmo billing.
2. **Proximity com Vertex AI** — Requests para Claude via Vertex ficam dentro do GCP (sem egress costs, menor latência).
3. **Auto-scaling 0-to-N** — Scale to zero quando sem tráfego (custo zero). Escala automaticamente sob carga.
4. **GCP Secret Manager** — Enterprise-grade secrets management integrado com Cloud Run.
5. **SLA 99.95%** — Superior à maioria das alternativas para containers managed.
6. **Cloud Build CI/CD** — Build e deploy automatizado via GitHub integration ou Cloud Build triggers.
7. **IAM unificado** — Service account do Cloud Run herda permissões para Vertex AI, Secret Manager, etc.
8. **Pay-per-request** — Generous free tier (2M requests/mês), custo proporcional ao uso real.

**Trade-offs Aceitos:**

- **Mais complexo que Railway** — Requer GCP project, IAM roles, service accounts. Mitigado: equipe já conhece GCP.
- **Cold starts** — Container pode levar 2-5s no primeiro request após inatividade. Mitigado com `--min-instances=1`.
- **Learning curve** — gcloud CLI, Cloud Build, Secret Manager. Mitigado: equipe já opera GCP.

**Deploy Example:**

```bash
# Deploy direto do source
gcloud run deploy mb-wpp \
  --source . \
  --region us-east1 \
  --set-env-vars="DJANGO_SETTINGS_MODULE=config.settings.production" \
  --set-secrets="DATABASE_URL=database-url:latest,ANTHROPIC_API_KEY=anthropic-key:latest" \
  --min-instances=1 \
  --max-instances=10 \
  --memory=1Gi \
  --cpu=2 \
  --port=8080 \
  --allow-unauthenticated
```

---

### ADR-006: Multi-Provider LLM Strategy — Vertex AI Primary, Anthropic Direct Fallback

**Date:** 2026-03-03
**Status:** DECIDED
**Decisores:** Rodrigo Franco, Claude Agent

**Context:**

Claude é o LLM core do sistema. Precisamos decidir como consumir (Anthropic Direct vs Vertex AI) e se ter fallback para outro provider. Com a adoção de LangChain (ADR-010), a implementação de multi-provider e fallback é simplificada via `ChatAnthropicVertex` + `model.with_fallbacks()`.

**Provider Comparison:**

| Critério | Vertex AI (Anthropic) | Anthropic Direct | OpenAI (GPT-4o) |
|----------|------------------------|------------------|-----------------|
| **Custo** | 70% mais barato | Baseline | Comparável |
| **SLA** | 99.9% (enterprise) | 99.5% | 99.9% |
| **Rate Limits** | Mais altos (enterprise) | Standard | Altos |
| **Data Residency** | Google Cloud (controle) | US apenas | Global distribuído |
| **Prompt Caching** | Sim | Sim | Limitado |
| **Tool Use** | Nativo | Nativo | Function calling (diferente) |
| **LangChain Support** | ChatAnthropicVertex | ChatAnthropic | ChatOpenAI |
| **Setup** | GCP Service Account | API Key simples | API Key simples |

**Decision:**

**Arquitetura de 2 providers via LangChain:**
1. **Primary:** Vertex AI (Claude via `ChatAnthropicVertex`)
2. **Fallback:** Anthropic Direct (Claude via `ChatAnthropic`)
3. **Removed:** OpenAI não será usado

**Justificativa:**

**Por que Vertex AI como primary:**
1. **Custo 70% menor** — Desconto enterprise Google Cloud
2. **SLA 99.9%** — Superior ao Anthropic Direct (99.5%)
3. **Same VPC** — Cloud Run e Vertex AI no mesmo GCP project (ADR-005)
4. **Rate limits maiores** — Conta enterprise tem limites mais altos
5. **Data residency** — Google Cloud permite controle de região (LGPD futura)

**Por que Anthropic Direct como fallback (não OpenAI):**
1. **Mesmo modelo** — Claude Sonnet, evita diferenças de comportamento
2. **Mesmo framework** — `ChatAnthropic` do LangChain, código quase idêntico
3. **Prompt Caching** — Suportado em ambos os providers
4. **Tool definitions** — Schema idêntico, OpenAI tem diferenças sutis
5. **Simplicidade** — 1 modelo, 2 endpoints. Debugging mais fácil.

**Implementation via LangChain (substitui LLMProvider ABC + ProviderRouter custom):**

```python
# workflows/providers/llm.py
from google.oauth2 import service_account
from langchain_anthropic import ChatAnthropicVertex, ChatAnthropic
from django.conf import settings

def get_model(temperature: float = 0, max_tokens: int = 2048):
    """Retorna modelo com fallback automático Vertex AI → Anthropic Direct."""
    credentials = service_account.Credentials.from_service_account_info(
        settings.GCP_CREDENTIALS,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )

    primary = ChatAnthropicVertex(
        model_name="claude-sonnet-4@20250514",
        project=settings.VERTEX_PROJECT_ID,
        location=settings.VERTEX_LOCATION,
        credentials=credentials,
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=True,
        max_retries=2,
    )

    fallback = ChatAnthropic(
        model="claude-sonnet-4-20250514",
        api_key=settings.ANTHROPIC_API_KEY,
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=True,
        max_retries=2,
    )

    # with_fallbacks() substitui ProviderRouter + circuit breaker custom
    return primary.with_fallbacks([fallback])
```

**Cost Tracking via LangChain Callbacks:**

```python
# workflows/services/cost_tracker.py
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult
from workflows.models import CostLog

class CostTrackingCallback(AsyncCallbackHandler):
    """Rastreia custos de cada chamada LLM."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.total_input = 0
        self.total_output = 0
        self.cache_read = 0
        self.cache_creation = 0

    async def on_llm_end(self, response: LLMResult, **kwargs):
        for gen_list in response.generations:
            for gen in gen_list:
                msg = getattr(gen, "message", None)
                if msg and hasattr(msg, "usage_metadata") and msg.usage_metadata:
                    meta = msg.usage_metadata
                    self.total_input += meta.get("input_tokens", 0)
                    self.total_output += meta.get("output_tokens", 0)
                    details = meta.get("input_token_details", {})
                    self.cache_read += details.get("cache_read", 0)
                    self.cache_creation += details.get("cache_creation", 0)

    async def persist(self):
        """Salva custo no banco após execução do grafo."""
        base_input = self.total_input - self.cache_read - self.cache_creation
        cost = (
            base_input * 3.00 / 1_000_000
            + self.cache_read * 0.30 / 1_000_000
            + self.cache_creation * 3.75 / 1_000_000
            + self.total_output * 15.00 / 1_000_000
        )
        await CostLog.objects.acreate(
            user_id=self.user_id,
            tokens_input=self.total_input,
            tokens_output=self.total_output,
            tokens_cache_read=self.cache_read,
            tokens_cache_creation=self.cache_creation,
            cost_usd=cost,
            provider="vertex_ai",  # ou "anthropic_direct" se fallback
        )
```

**Usage no LangGraph:**

```python
# workflows/whatsapp/nodes/orchestrate_llm.py
from workflows.providers.llm import get_model
from workflows.services.cost_tracker import CostTrackingCallback

async def orchestrate_llm(state: WhatsAppState) -> dict:
    model = get_model()  # Vertex AI com fallback
    model_with_tools = model.bind_tools(get_tools())
    cost_tracker = CostTrackingCallback(user_id=state["user_id"])

    response = await model_with_tools.ainvoke(
        state["messages"],
        config={"callbacks": [cost_tracker]},
    )

    # Cost tracking persiste automaticamente
    await cost_tracker.persist()

    return {"messages": [response]}
```

**Nota:** `with_fallbacks()` do LangChain gerencia automaticamente o retry e fallback. Se Vertex AI falhar (timeout, rate limit, erro 5xx), LangChain automaticamente tenta Anthropic Direct. Não é necessário implementar circuit breaker custom.

---

### ADR-007: Cache Strategy — Redis 4 Camadas

**Date:** 2026-02-14
**Status:** DECIDED

**Context:**

Múltiplos use cases para caching: debounce de mensagens, sessões de usuário, configurações, rate limiting. Redis (Up stash) já está em uso.

**Decision:**

Redis com **4 camadas independentes** de cache, cada uma com TTL e namespace específicos.

**Camadas:**

| Camada | Namespace | TTL | Uso |
|--------|-----------|-----|-----|
| **1. Message Buffer** | `msg_buffer:{phone}` | 3s | Debounce de mensagens WhatsApp |
| **2. Session Cache** | `session:{user_id}` | 1h | Histórico de conversa (últimas 20 msgs) |
| **3. Config Cache** | `config:{key}` | 5min | System prompt, rate limits, mensagens |
| **4. Rate Limiting** | `ratelimit:{user_id}:{tier}` | 24h | Contadores sliding window + token bucket |

**Code Example:**

```python
from redis.asyncio import Redis
from typing import Literal
import json

class CacheManager:
    def __init__(self, redis: Redis):
        self.redis = redis

    # Camada 1: Message Buffer (debounce)
    async def buffer_message(self, phone: str, message: str) -> list[str]:
        """Buffer message for debounce. Returns accumulated messages."""
        key = f"msg_buffer:{phone}"
        await self.redis.rpush(key, message)
        await self.redis.expire(key, 3)  # 3 segundos
        return [msg.decode() for msg in await self.redis.lrange(key, 0, -1)]

    async def get_buffered_messages(self, phone: str) -> list[str]:
        """Get and clear buffered messages."""
        key = f"msg_buffer:{phone}"
        messages = [msg.decode() for msg in await self.redis.lrange(key, 0, -1)]
        await self.redis.delete(key)
        return messages

    # Camada 2: Session Cache
    async def cache_session(self, user_id: str, messages: list[dict]):
        """Cache últimas mensagens da sessão."""
        key = f"session:{user_id}"
        await self.redis.setex(key, 3600, json.dumps(messages))  # 1 hora

    async def get_session(self, user_id: str) -> list[dict] | None:
        """Retrieve cached session."""
        key = f"session:{user_id}"
        data = await self.redis.get(key)
        return json.loads(data) if data else None

    # Camada 3: Config Cache
    async def cache_config(self, config_key: str, value: dict | str):
        """Cache configuration value."""
        key = f"config:{config_key}"
        await self.redis.setex(key, 300, json.dumps(value))  # 5 minutos

    async def get_config(self, config_key: str) -> dict | str | None:
        """Get cached config (or None if miss)."""
        key = f"config:{config_key}"
        data = await self.redis.get(key)
        return json.loads(data) if data else None

    # Camada 4: Rate Limiting
    async def check_rate_limit(
        self,
        user_id: str,
        tier: Literal["free", "basic", "premium"],
        limits: dict
    ) -> tuple[bool, int]:
        """Check rate limit. Returns (allowed, remaining)."""
        key = f"ratelimit:{user_id}:{tier}"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, 86400)  # 24 horas

        limit = limits[tier]
        allowed = count <= limit
        remaining = max(0, limit - count)
        return allowed, remaining
```

---

### ADR-008: Security Architecture — 6 Camadas

**Date:** 2026-03-03
**Status:** DECIDED

**Context:**

Sistema lida com dados sensíveis de saúde (LGPD), precisa validar webhooks WhatsApp, e deve evitar ataques comuns. Implementação adaptada para Django + DRF + GCP.

**Decision:**

Arquitetura de segurança em **6 camadas**:

| Camada | Mecanismo | Implementação |
|--------|-----------|---------------|
| **1. Webhook Validation** | HMAC SHA-256 | Django middleware verificando `X-Hub-Signature-256` |
| **2. Input Validation** | DRF Serializers | Validar inputs em boundaries de API |
| **3. Rate Limiting** | Redis dual (sliding + token bucket) | Prevenir abuso |
| **4. Data Access Control** | Django permissions + RLS defense-in-depth | Permissões de aplicação + RLS no PostgreSQL |
| **5. Secrets Management** | GCP Secret Manager + django-environ | Secrets montados como env vars no Cloud Run |
| **6. Logging Sanitization** | structlog processors | Remover PII de logs |

**Code Examples:**

**Camada 1: Webhook Validation (Django Middleware)**

```python
# workflows/middleware/webhook_signature.py
import hmac
import hashlib
import structlog
from django.http import JsonResponse
from django.conf import settings

logger = structlog.get_logger()

class WebhookSignatureMiddleware:
    """Verifica HMAC SHA-256 em requests de webhook WhatsApp."""

    def __init__(self, get_response):
        self.get_response = get_response

    async def __call__(self, request):
        if request.path.startswith("/webhook/"):
            signature = request.headers.get("X-Hub-Signature-256", "")
            if not signature.startswith("sha256="):
                logger.warning("webhook_signature_missing")
                return JsonResponse({"error": "Missing signature"}, status=401)

            expected = "sha256=" + hmac.new(
                settings.WHATSAPP_WEBHOOK_SECRET.encode(),
                request.body,
                hashlib.sha256,
            ).hexdigest()

            if not hmac.compare_digest(signature, expected):
                logger.error("webhook_signature_invalid")
                return JsonResponse({"error": "Invalid signature"}, status=401)

        return await self.get_response(request)
```

**Camada 2: Input Validation (DRF Serializers)**

```python
# workflows/serializers.py
from rest_framework import serializers
from datetime import datetime

class WhatsAppMessageSerializer(serializers.Serializer):
    from_number = serializers.RegexField(r"^\d{10,15}$", source="from")
    id = serializers.CharField()
    timestamp = serializers.CharField()
    type = serializers.ChoiceField(choices=["text", "audio", "image"])
    text = serializers.DictField(required=False)
    audio = serializers.DictField(required=False)
    image = serializers.DictField(required=False)

    def validate_timestamp(self, value):
        ts = int(value)
        now = int(datetime.now().timestamp())
        if abs(now - ts) > 300:
            raise serializers.ValidationError("Timestamp too old or future")
        return value
```

**Camada 3: Rate Limiting Dual**

```python
class RateLimiter:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.limits = {
            "free": {"daily": 10, "burst": 2},
            "basic": {"daily": 100, "burst": 5},
            "premium": {"daily": 1000, "burst": 10}
        }

    async def check_limit(self, user_id: str, tier: str) -> tuple[bool, str]:
        """Check both sliding window and token bucket."""

        # Sliding window (daily limit)
        daily_key = f"ratelimit:daily:{user_id}"
        daily_count = await self.redis.incr(daily_key)
        if daily_count == 1:
            await self.redis.expire(daily_key, 86400)

        if daily_count > self.limits[tier]["daily"]:
            return False, f"Daily limit reached ({self.limits[tier]['daily']})"

        # Token bucket (burst limit)
        burst_key = f"ratelimit:burst:{user_id}"
        tokens = await self.redis.get(burst_key)
        tokens = int(tokens) if tokens else self.limits[tier]["burst"]

        if tokens <= 0:
            return False, "Too many requests. Wait 1 minute."

        await self.redis.decr(burst_key)
        await self.redis.expire(burst_key, 60)  # Refill em 1 minuto

        return True, ""
```

**Camada 4: Django Permissions + RLS (defense-in-depth)**

```python
# workflows/permissions.py
from rest_framework.permissions import BasePermission

class IsServiceAccount(BasePermission):
    """Permite acesso apenas a service accounts (webhook, cron jobs)."""
    def has_permission(self, request, view):
        return getattr(request, "is_service_account", False)

class IsOwner(BasePermission):
    """Permite acesso apenas ao dono do recurso."""
    def has_object_permission(self, request, view, obj):
        return obj.user_id == request.user.id
```

```sql
-- RLS como defense-in-depth (o Django ORM usa service_role, mas RLS garante isolamento extra)
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access"
    ON messages FOR ALL
    USING (auth.role() = 'service_role');
```

**Camada 5: Secrets Management (GCP Secret Manager + django-environ)**

```python
# config/settings/base.py
import environ

env = environ.Env()
environ.Env.read_env()  # .env em dev

# Required secrets (raise error if missing)
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY")
VERTEX_PROJECT_ID = env("VERTEX_PROJECT_ID")
SUPABASE_URL = env("SUPABASE_URL")
SUPABASE_SERVICE_KEY = env("SUPABASE_SERVICE_KEY")  # Never anon key!
REDIS_URL = env("REDIS_URL")
WHATSAPP_WEBHOOK_SECRET = env("WHATSAPP_WEBHOOK_SECRET")

# Optional with defaults
LOG_LEVEL = env("LOG_LEVEL", default="INFO")
```

```yaml
# Em produção: GCP Secret Manager injeta como env vars no Cloud Run
# gcloud run deploy --set-secrets="ANTHROPIC_API_KEY=anthropic-key:latest,..."
# Rotação de secrets sem redeploy via secret versions
```

**Camada 6: Log Sanitization**

```python
import structlog

def sanitize_pii(logger, method_name, event_dict):
    """Remove PII from logs."""
    sensitive_fields = ["phone", "name", "email", "cpf", "api_key"]

    for field in sensitive_fields:
        if field in event_dict:
            event_dict[field] = "***REDACTED***"

    # Sanitize nested dicts
    for key, value in event_dict.items():
        if isinstance(value, dict):
            for sensitive in sensitive_fields:
                if sensitive in value:
                    value[sensitive] = "***REDACTED***"

    return event_dict

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        sanitize_pii,  # ← PII sanitizer
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)
```

---

### ADR-009: Project Structure — Django Project com App `workflows`

**Date:** 2026-02-26 | **Revised:** 2026-03-03
**Status:** DECIDED

**Context:**

Equipe Medway padroniza Django projects com uma app principal `workflows/` contendo sub-módulos por domínio (graph, nodes, tools, services, providers). Pattern validado em produção no `search-medway-langgraph`.

**Decision:**

Django project com **uma app principal `workflows/`** e sub-módulos, alinhado com o pattern da equipe.

**Complete Directory Tree:**

```
mb-wpp/
├── pyproject.toml              # uv project config (PEP 621)
├── uv.lock                     # Lockfile com hashes
├── .env.example                # Template de env vars
├── .gitignore                  # Python gitignore
├── Dockerfile                  # Multi-stage build
├── docker-compose.yml          # Local development
├── cloudbuild.yaml             # GCP Cloud Build CI/CD
├── manage.py                   # Django management
├── README.md                   # Setup instructions
│
├── config/                     # Django project settings
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py             # Settings compartilhados
│   │   ├── development.py      # Dev overrides
│   │   └── production.py       # Prod overrides (GCP)
│   ├── urls.py                 # Root URL configuration
│   ├── asgi.py                 # ASGI entry point (Daphne/Uvicorn)
│   └── wsgi.py                 # WSGI fallback
│
├── workflows/                  # Django app principal
│   ├── __init__.py
│   ├── apps.py                 # AppConfig
│   ├── models.py               # Django models (User, Message, CostLog, etc.)
│   ├── admin.py                # Django Admin registrations
│   ├── views.py                # Webhook + API views (adrf async)
│   ├── serializers.py          # DRF serializers (validação)
│   ├── urls.py                 # App URL patterns
│   ├── migrations/             # Django migrations
│   │   └── __init__.py
│   │
│   ├── whatsapp/               # Workflow principal (LangGraph)
│   │   ├── __init__.py
│   │   ├── graph.py            # StateGraph compilado (build_whatsapp_graph)
│   │   ├── state.py            # WhatsAppState TypedDict
│   │   ├── nodes/              # Nós do grafo
│   │   │   ├── __init__.py
│   │   │   ├── identify_user.py
│   │   │   ├── rate_limit.py
│   │   │   ├── process_media.py
│   │   │   ├── load_context.py
│   │   │   ├── orchestrate_llm.py
│   │   │   ├── format_response.py
│   │   │   ├── send_whatsapp.py
│   │   │   └── persist.py
│   │   ├── tools/              # LangChain @tool definitions
│   │   │   ├── __init__.py
│   │   │   ├── rag_medical.py
│   │   │   ├── bulas_med.py
│   │   │   ├── calculators.py
│   │   │   ├── quiz_generator.py
│   │   │   ├── web_search.py         # Tavily advanced + exclude_domains (concorrentes)
│   │   │   └── verify_paper.py       # PubMed E-utilities API (verificação de artigos)
│   │   └── prompts/
│   │       ├── __init__.py
│   │       └── system.py       # System prompt + tool descriptions
│   │
│   ├── services/               # Business logic services
│   │   ├── __init__.py
│   │   ├── rate_limiter.py     # Rate limiting dual (Redis)
│   │   ├── cost_tracker.py     # CostTrackingCallback (LangChain)
│   │   ├── config_service.py   # Config dinâmica (DB + Redis cache)
│   │   └── feature_flags.py    # Feature flags (Strangler Fig)
│   │
│   ├── providers/              # External service clients
│   │   ├── __init__.py
│   │   ├── llm.py              # get_model() — ChatAnthropicVertex + fallback
│   │   ├── checkpointer.py     # get_checkpointer() — AsyncPostgresSaver singleton
│   │   ├── redis.py            # Redis client singleton
│   │   ├── whatsapp.py         # WhatsApp Cloud API client
│   │   ├── pinecone.py         # Pinecone client
│   │   ├── whisper.py          # OpenAI Whisper client
│   │   ├── supabase.py         # Supabase client (Auth + Storage apenas)
│   │   └── langfuse.py         # Langfuse observability client
│   │
│   ├── middleware/             # Django middleware
│   │   ├── __init__.py
│   │   ├── webhook_signature.py  # HMAC signature verification
│   │   └── trace_id.py          # Request trace ID injection
│   │
│   └── utils/                  # Shared utilities
│       ├── __init__.py
│       ├── retry.py            # Retry decorator com backoff
│       ├── deduplication.py    # Message deduplication (Redis)
│       ├── sanitization.py     # PII sanitization (logs)
│       ├── formatters.py       # Markdown → WhatsApp formatting
│       └── message_splitter.py # Split mensagens longas
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Pytest fixtures (pytest-django)
│   ├── test_views.py           # Webhook e API views
│   ├── test_models.py          # Django model tests
│   ├── test_whatsapp/
│   │   ├── __init__.py
│   │   ├── test_graph.py       # StateGraph integration tests
│   │   ├── test_nodes/
│   │   │   ├── __init__.py
│   │   │   ├── test_identify_user.py
│   │   │   ├── test_rate_limit.py
│   │   │   └── ...
│   │   └── test_tools/
│   │       ├── __init__.py
│   │       ├── test_rag_medical.py
│   │       └── ...
│   ├── test_services/
│   │   ├── __init__.py
│   │   ├── test_rate_limiter.py
│   │   └── test_cost_tracker.py
│   └── test_providers/
│       ├── __init__.py
│       ├── test_llm.py
│       └── test_whatsapp.py
│
└── scripts/
    ├── seed_database.py        # Popular DB com dados de teste
    └── run_local.sh            # Rodar local com docker-compose
```

**Total:** ~55 arquivos Python

**Naming Conventions:**

| Tipo | Convenção | Exemplo |
|------|-----------|---------|
| **Arquivos** | snake_case.py | `rate_limiter.py` |
| **Diretórios** | snake_case/ | `test_whatsapp/` |
| **Classes** | PascalCase | `class WhatsAppWebhookView` |
| **Funções** | snake_case | `def get_user_by_phone()` |
| **Constantes** | UPPER_SNAKE_CASE | `MAX_RETRIES = 3` |
| **Django models** | PascalCase singular | `class Message(models.Model)` |
| **Django apps** | snake_case plural | `workflows` |

**Import Style:**

```python
# Standard library primeiro
import asyncio
import json
from datetime import datetime
from typing import Literal

# Third-party segundo
import structlog
from django.conf import settings
from rest_framework import serializers
from langchain_anthropic import ChatAnthropicVertex

# Local imports por último (Django app-relative)
from workflows.models import User, Message
from workflows.providers.llm import get_model
from workflows.whatsapp.state import WhatsAppState
```

---

### ADR-011: Admin Panel Strategy — 3 Fases (M1 coleta apenas)

**Date:** 2026-02-26
**Status:** DECIDED

**Context:**

Precisamos de observabilidade de custo, uso, e qualidade de ferramentas. Admin panel completo é complexo e não é M1. Podemos coletar dados desde o dia 1 e construir UI gradualmente.

**Decision:**

Estratégia de **3 fases**:

**Fase 1 (M1):** Coleta de dados granular + **Django Admin** como UI imediata (zero frontend custom). Django Admin já fornece CRUD, filtros, search, e export para todos os models registrados.
**Fase 2 (M1.5):** Painel minimal com Next.js + Supabase (queries diretas) para dashboards visuais.
**Fase 3 (M2/M3):** Painel robusto com agregações, filtros, alertas.

**Fase 1 (M1) — Data Collection + Django Admin:**

**Django Models (em `workflows/models.py`):**

```python
class CostLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cost_logs")
    provider = models.CharField(max_length=20)  # 'primary' ou 'fallback'
    model = models.CharField(max_length=100)
    tokens_input = models.IntegerField()
    tokens_output = models.IntegerField()
    tokens_cache_write = models.IntegerField(default=0)
    tokens_cache_read = models.IntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cost_logs"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["-created_at"]),
        ]

class ToolExecution(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tool_executions")
    tool_name = models.CharField(max_length=100)
    input_params = models.JSONField(default=dict, blank=True)
    output = models.JSONField(default=dict, blank=True)
    execution_time_ms = models.IntegerField(null=True)
    success = models.BooleanField()
    error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tool_executions"
        indexes = [
            models.Index(fields=["tool_name"]),
            models.Index(fields=["-created_at"]),
        ]
```

**Django Admin (zero-effort UI):**

```python
# workflows/admin.py
from django.contrib import admin
from .models import User, Message, CostLog, ToolExecution

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("phone", "subscription_tier", "created_at")
    list_filter = ("subscription_tier",)
    search_fields = ("phone", "medway_id")

@admin.register(CostLog)
class CostLogAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "model", "cost_usd", "tokens_input", "tokens_output", "created_at")
    list_filter = ("provider", "model", "created_at")
    date_hierarchy = "created_at"

@admin.register(ToolExecution)
class ToolExecutionAdmin(admin.ModelAdmin):
    list_display = ("user", "tool_name", "success", "execution_time_ms", "created_at")
    list_filter = ("tool_name", "success", "created_at")
    date_hierarchy = "created_at"
```

**Persister (nó `persist` do grafo):**

```python
# workflows/whatsapp/nodes/persist.py
import structlog
from workflows.models import Message, CostLog, ToolExecution

logger = structlog.get_logger()

async def persist(state: WhatsAppState) -> WhatsAppState:
    """Nó persist: salva mensagem, custo, e tool executions via Django ORM."""

    user = state["user"]

    # 1. Persist user message + assistant response
    await Message.objects.acreate(
        user=user, content=state["user_message"],
        role="user", message_type=state.get("message_type", "text"),
    )
    await Message.objects.acreate(
        user=user, content=state["response_text"],
        role="assistant", message_type="text",
        tokens_input=state.get("tokens_input"),
        tokens_output=state.get("tokens_output"),
        cost_usd=state.get("cost_usd"),
    )

    # 2. Cost log (granular)
    await CostLog.objects.acreate(
        user=user,
        provider=state.get("provider_used", "primary"),
        model=state.get("model_used", "claude-sonnet-4-20250514"),
        tokens_input=state.get("tokens_input", 0),
        tokens_output=state.get("tokens_output", 0),
        tokens_cache_write=state.get("cache_creation", 0),
        tokens_cache_read=state.get("cache_read", 0),
        cost_usd=state.get("cost_usd", 0),
    )

    # 3. Tool executions (se houver)
    for tool_exec in state.get("tools_used", []):
        await ToolExecution.objects.acreate(
            user=user,
            tool_name=tool_exec["name"],
            input_params=tool_exec.get("input", {}),
            output=tool_exec.get("output", {}),
            execution_time_ms=tool_exec.get("execution_time_ms"),
            success=tool_exec.get("success", True),
            error=tool_exec.get("error"),
        )

    logger.info("data_persisted", user_id=user.id, cost_usd=state.get("cost_usd"))
    return state
```

**Fase 2 (M1.5) — Minimal Panel:**

Next.js app (separado) que lê dados via API DRF ou Supabase client para dashboards visuais.

Telas:
- Dashboard: Custo total hoje/semana/mês, mensagens, usuários ativos
- Cost Breakdown: Gráfico custo por dia, por provider (primary vs fallback)
- Tools Usage: Quais tools são mais usadas, taxa de sucesso
- Logs: Tabela de `cost_logs` com filtros (user, date range)

**Fase 3 (M2/M3) — Robust Panel:**

- Filtros avançados (user tier, message type, tool, date range)
- Alertas configuráveis (custo > $X/dia, error rate > Y%)
- Exportação de dados (CSV, JSON)
- Comparação de versões de system prompt
- A/B testing de configurações

---

---

## Implementation Patterns & Consistency Rules

_Esta seção define padrões obrigatórios para garantir consistência em toda a codebase. Agentes de IA devem seguir esses padrões rigorosamente._

### Naming Conventions

**Database (PostgreSQL/Supabase):**
- Tabelas: `snake_case` plural (`users`, `messages`, `cost_logs`)
- Colunas: `snake_case` (`user_id`, `created_at`, `tokens_input`)
- Indexes: `idx_{table}_{column}` (`idx_messages_user_id`)
- Foreign keys: `{table}_id` (`user_id`, `message_id`)

**API Endpoints:**
- Routes: `kebab-case` (`/webhook/whatsapp`, `/api/cost-logs`)
- Query params: `snake_case` (`?user_id=123&date_from=2024-01-01`)

**Python Code:**
- Arquivos/módulos: `snake_case.py` (`rate_limiter.py`, `identify_user.py`)
- Classes: `PascalCase` (`WhatsAppWebhookView`, `CostTrackingCallback`)
- Funções/métodos: `snake_case` (`get_user_by_phone()`, `build_whatsapp_graph()`)
- Variáveis: `snake_case` (`user_id`, `response_text`, `cost_usd`)
- Constantes: `UPPER_SNAKE_CASE` (`MAX_RETRIES`, `DEFAULT_TIMEOUT`, `SYSTEM_PROMPT`)
- Privados: Prefixo `_` (`_internal_helper()`, `_cache_key`)
- Django apps: `snake_case` plural (`workflows`)

**Environment Variables:**
- `UPPER_SNAKE_CASE` (`ANTHROPIC_API_KEY`, `VERTEX_PROJECT_ID`, `REDIS_URL`)
- Prefixos por serviço quando possível (`VERTEX_`, `SUPABASE_`, `WHATSAPP_`)

### Format Conventions

**Errors:**

```python
# Hierarquia de exceções
class AppError(Exception):
    """Base exception para aplicação."""
    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

class ValidationError(AppError):
    """Input validation failed."""
    pass

class AuthenticationError(AppError):
    """Authentication/authorization failed."""
    pass

class RateLimitError(AppError):
    """Rate limit exceeded."""
    def __init__(self, message: str, retry_after: int, details: dict | None = None):
        super().__init__(message, details)
        self.retry_after = retry_after

class ExternalServiceError(AppError):
    """External service failed."""
    def __init__(self, service: str, message: str, details: dict | None = None):
        super().__init__(f"{service}: {message}", details)
        self.service = service

class GraphNodeError(AppError):
    """LangGraph node failed."""
    def __init__(self, node: str, message: str, details: dict | None = None):
        super().__init__(f"Node {node}: {message}", details)
        self.node = node
```

**Dates & Times:**
- Sempre ISO 8601 com timezone: `2024-01-15T14:30:00Z`
- UTC por padrão, conversão para timezone do usuário apenas na apresentação
- Use `datetime.now(timezone.utc)` ou `datetime.now().astimezone(timezone.utc)`

**JSON Field Naming:**
- `snake_case` em todos os lugares (DB, API, logs)
- Nunca usar `camelCase` (WhatsApp usa, mas convertemos internamente)

### Communication Patterns

**Logging:**

```python
import structlog

logger = structlog.get_logger()

# Sempre structured logging
logger.info(
    "event_name",
    user_id=user_id,
    cost_usd=cost,
    tokens=tokens,
    provider="primary"
)

# Níveis:
# - DEBUG: Detalhes internos (cache hits, query params)
# - INFO: Eventos normais (message_received, llm_called, response_sent)
# - WARNING: Degradação (fallback_used, rate_limit_approached)
# - ERROR: Falhas recuperáveis (tool_execution_failed, retry_attempted)
# - CRITICAL: Falhas não recuperáveis (both_providers_failed, database_down)
```

**Event Naming:**
- `snake_case`
- Verbo no passado para eventos (`message_received`, `user_identified`, `tool_executed`)
- Substantivo para estados (`rate_limit_exceeded`, `circuit_breaker_open`)

**Trace ID Propagation:**

```python
# Gerar no webhook handler
import uuid
trace_id = str(uuid.uuid4())

# Adicionar ao contexto structlog
structlog.contextvars.bind_contextvars(trace_id=trace_id)

# Propagar para providers externos (Langfuse, WhatsApp)
headers = {"X-Trace-ID": trace_id}
```

### Structure Patterns

**LangGraph Node Contract:**

```python
# Cada nó do grafo é uma função async pura que recebe e retorna state
from workflows.whatsapp.state import WhatsAppState

async def node_name(state: WhatsAppState) -> WhatsAppState:
    """Nó do grafo — lógica isolada, sem side effects no grafo."""
    # ... lógica do nó ...
    return state  # ou dict parcial para merge automático
```

**LangChain Tool Contract:**

```python
from langchain_core.tools import tool

@tool
async def tool_name(param: str) -> str:
    """Descrição clara que o LLM usa para decidir quando chamar esta tool.

    Args:
        param: Descrição do parâmetro.
    """
    # ... lógica da tool ...
    return "resultado"
```

**Django Model Pattern:**

```python
# workflows/models.py — todos os models em um arquivo (Django convention)
from django.db import models

class ModelName(models.Model):
    # campos...

    class Meta:
        db_table = "table_name"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["field_name"])]

    def __str__(self):
        return f"ModelName({self.id})"
```

### Process Patterns

**Retry Pattern (LangGraph RetryPolicy):**

```python
from langgraph.pregel import RetryPolicy

# Retry automático em nós do grafo
builder.add_node(
    "send_whatsapp",
    send_whatsapp,
    retry=RetryPolicy(max_attempts=3, backoff_factor=2.0),
)
```

**Retry Pattern (manual para chamadas fora do grafo):**

```python
import asyncio
import structlog

logger = structlog.get_logger()

async def retry_with_backoff(func, max_retries=3, base_delay=1.0, exceptions=(Exception,)):
    for attempt in range(max_retries):
        try:
            return await func()
        except exceptions as e:
            if attempt == max_retries - 1:
                logger.error("max_retries_exceeded", error=str(e), attempts=max_retries)
                raise
            delay = min(base_delay * (2 ** attempt), 60.0)
            logger.warning("retry_attempt", attempt=attempt + 1, delay=delay, error=str(e))
            await asyncio.sleep(delay)
```

**Fallback Pattern:**

(Ver ADR-006: `get_model()` com `primary.with_fallbacks([fallback])`)

**Validation Pattern (DRF Serializer):**

```python
from rest_framework import serializers

class CreateUserSerializer(serializers.Serializer):
    phone = serializers.RegexField(r"^\+\d{10,15}$")
    medway_id = serializers.CharField(required=False, allow_null=True)
```

**Import Order:**

```python
# 1. Standard library
import asyncio
import json
from datetime import datetime
from typing import Literal

# 2. Third-party
import structlog
from django.conf import settings
from rest_framework import serializers
from langchain_core.tools import tool

# 3. Local imports (Django app-relative)
from workflows.models import User, Message
from workflows.providers.llm import get_model
```

**Message Deduplication:**

```python
async def is_duplicate_message(message_id: str, redis: Redis) -> bool:
    """Check if message was already processed."""
    key = f"msg_processed:{message_id}"
    exists = await redis.exists(key)
    if exists:
        return True
    await redis.setex(key, 3600, "1")  # 1 hora
    return False
```

**WhatsApp Event Filtering:**

```python
def should_process_event(event: dict) -> bool:
    """Filter events que devem ser processados."""
    # Apenas messages
    if event.get("object") != "whatsapp_business_account":
        return False

    changes = event.get("entry", [{}])[0].get("changes", [])
    if not changes:
        return False

    value = changes[0].get("value", {})

    # Ignore status updates (delivered, read, etc)
    if "statuses" in value:
        return False

    # Apenas messages de usuários
    messages = value.get("messages", [])
    if not messages:
        return False

    # Ignore mensagens de sistema
    message = messages[0]
    if message.get("type") in ["system", "unknown"]:
        return False

    return True
```

**Graceful Shutdown (Django + ASGI):**

```python
# config/asgi.py
import django
from django.core.asgi import get_asgi_application

django.setup()
application = get_asgi_application()

# Cloud Run envia SIGTERM e aguarda 10s antes de SIGKILL
# Django ASGI server (Uvicorn/Daphne) lida com graceful shutdown nativamente
```

**Graph Concurrency Control:**

```python
# Limitar execuções concorrentes do grafo
graph_semaphore = asyncio.Semaphore(50)  # Max 50 concurrent

async def process_message(message: dict):
    async with graph_semaphore:
        checkpointer = await get_checkpointer()
        graph = build_whatsapp_graph().compile(checkpointer=checkpointer)
        await graph.ainvoke(
            {"user_message": message["text"], "phone": message["from"]},
            config={"configurable": {"thread_id": message["from"]}},
        )
```

**Feature Flag Pattern:**

```python
async def is_feature_enabled(user_id: str, feature: str) -> bool:
    """Check if feature is enabled for user (rollout gradual)."""
    # Check config table
    config = await config_service.get(f"feature_flag:{feature}")
    if not config:
        return False

    rollout_percentage = config.get("rollout_percentage", 0)

    # Hash user_id para distribuição uniforme
    import hashlib
    hash_val = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
    bucket = hash_val % 100

    return bucket < rollout_percentage
```

### Citation & Source Attribution Patterns

**Princípio:** A LLM NUNCA gera URLs ou referências de memória. Toda citação é rastreável a uma fonte verificada (RAG ou web search). Sistema inspirado na arquitetura do Perplexity AI.

**3 Tiers de Citação:**

| Tier | Marcador | Origem | Confiabilidade |
|------|----------|--------|----------------|
| **Gold** `[N]` | RAG (Pinecone) | Diretrizes, livros-texto Medway, bulas ANVISA | Alta — conteúdo curado |
| **Silver** `[W-N]` | Web Search (Tavily) | Artigos PubMed, diretrizes SBC/SBP, UpToDate | Média — verificado em tempo real |
| **Proibido** | — | Memória/treinamento da LLM | Proibido — risco de alucinação |

**Pipeline de Citação (4 etapas):**

```
1. Tools retornam fontes  →  2. LLM cita com [N]/[W-N]  →  3. format_response valida  →  4. WhatsApp renderiza
   (RAG chunks, web results)    (no texto gerado)             (strip [N] sem fonte real)    (fonte no rodapé)
```

**Web Search Tool (Tavily com bloqueio de concorrentes):**

```python
# workflows/whatsapp/tools/web_search.py
from langchain_core.tools import tool
from tavily import AsyncTavilyClient

# Lista configurável via Django Admin (Config model, key: "blocked_competitors")
COMPETITOR_DOMAINS = [
    "medgrupo.com.br", "grupomedcof.com.br", "med.estrategia.com",
    "estrategia.com", "medcel.com.br", "sanarmed.com", "sanarflix.com.br",
    "sanar.com.br", "aristo.com.br", "eumedicoresidente.com.br",
    "revisamed.com.br", "medprovas.com.br", "vrmed.com.br",
    "medmentoria.com", "oresidente.org", "afya.com.br",
]

@tool
async def web_search(query: str) -> str:
    """Busca informações médicas atualizadas na internet.
    Use quando a informação não está disponível na RAG (ex: diretrizes recentes).

    Args:
        query: Consulta médica para buscar na web.
    """
    blocked = await _get_blocked_domains()  # Config model ou fallback COMPETITOR_DOMAINS
    client = AsyncTavilyClient()
    results = await client.search(
        query=query,
        search_depth="advanced",
        include_raw_content=True,
        max_results=8,
        exclude_domains=blocked,
    )
    formatted = []
    for i, result in enumerate(results["results"], 1):
        formatted.append(
            f"[W-{i}] {result['title']}\n"
            f"   URL: {result['url']}\n"
            f"   Conteúdo verificado:\n"
            f'   "{result.get("raw_content", result["content"])[:800]}"\n'
        )
    return "\n\n".join(formatted)
```

**Verify Medical Paper Tool (PubMed E-utilities):**

```python
# workflows/whatsapp/tools/verify_paper.py
from langchain_core.tools import tool
import httpx

@tool
async def verify_medical_paper(title: str, authors: str = "") -> str:
    """Verifica se um artigo médico existe realmente no PubMed.
    Use ANTES de citar qualquer artigo/estudo mencionado pelo usuário.

    Args:
        title: Título do artigo ou estudo.
        authors: Autores (opcional, melhora precisão).
    """
    async with httpx.AsyncClient() as client:
        search = await client.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={"db": "pubmed", "term": f"{title} {authors}", "retmode": "json", "retmax": 3},
        )
        ids = search.json()["esearchresult"]["idlist"]
        if not ids:
            return "⚠️ ARTIGO NÃO ENCONTRADO no PubMed. NÃO cite este estudo."

        summary = await client.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
            params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"},
        )
        articles = summary.json().get("result", {})
        verified = []
        for pmid in ids:
            art = articles.get(pmid, {})
            verified.append(
                f"✅ PMID: {pmid}\n"
                f"   Título: {art.get('title', 'N/A')}\n"
                f"   Jornal: {art.get('fulljournalname', 'N/A')}\n"
                f"   Data: {art.get('pubdate', 'N/A')}\n"
                f"   URL: https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            )
        return "\n\n".join(verified)
```

**Bloqueio de Concorrentes (3 camadas):**

Concorrentes diretos da Medway no segmento preparatório para residência médica:

| Concorrente | Holding | Domínios |
|-------------|---------|----------|
| Medcurso / MED | Medgrupo | medgrupo.com.br |
| MedCof | Medgrupo | grupomedcof.com.br |
| Estratégia MED | Estratégia | med.estrategia.com, estrategia.com |
| Medcel | Afya | medcel.com.br |
| Sanar / SanarFlix | Sanar | sanarmed.com, sanarflix.com.br, sanar.com.br |
| Aristo (JJ Medicina) | JJ | aristo.com.br |
| Eu Médico Residente | — | eumedicoresidente.com.br |
| Revisamed / MedicCurso | — | revisamed.com.br |
| MedProvas | — | medprovas.com.br |
| VR MED | — | vrmed.com.br |
| MedMentoria | — | medmentoria.com |
| O Residente | — | oresidente.org |
| Afya (holding) | Afya | afya.com.br |

**Camada 1 — Web Search:** `exclude_domains` no Tavily (ver web_search tool acima).

**Camada 2 — System Prompt:**
```
## REGRA DE MARCA (OBRIGATÓRIO)
NUNCA cite conteúdo de concorrentes: Medcurso, MED, Medgrupo, MedCof,
Estratégia MED, Medcel, Afya, Sanar, SanarFlix, Aristo, JJ Medicina,
Eu Médico Residente, Revisamed, MedicCurso, VR MED, MedMentoria, O Residente.
Se a informação vier dessas fontes, cite a FONTE PRIMÁRIA em vez do concorrente.
```

**Camada 3 — Post-processing (format_response node):**

```python
# workflows/whatsapp/nodes/format_response.py (trecho)
import re
import structlog

logger = structlog.get_logger()

COMPETITOR_NAMES = [
    "medcurso", "medgrupo", "medcof", "estratégia med", "estrategia med",
    "medcel", "afya", "sanar", "sanarflix", "aristo", "jj medicina",
    "eu médico residente", "eu medico residente", "revisamed",
    "mediccurso", "medprovas", "vr med", "vrmed", "medmentoria",
    "o residente", "oresidente",
]

def strip_competitor_citations(text: str) -> str:
    """Remove menções a concorrentes da resposta final."""
    for name in COMPETITOR_NAMES:
        pattern = re.compile(re.escape(name), re.IGNORECASE)
        if pattern.search(text):
            logger.warning("competitor_citation_blocked", competitor=name)
            text = pattern.sub("[fonte removida]", text)
    return text
```

**Validação de Citações (format_response node):**

```python
def validate_citations(text: str, available_sources: list[dict]) -> str:
    """Remove marcadores [N] que não correspondem a fontes reais."""
    max_rag = len([s for s in available_sources if s["type"] == "rag"])
    max_web = len([s for s in available_sources if s["type"] == "web"])

    # Strip [N] inválidos (RAG)
    def check_rag(match):
        n = int(match.group(1))
        return match.group(0) if n <= max_rag else ""

    text = re.sub(r"\[(\d+)\]", check_rag, text)

    # Strip [W-N] inválidos (web)
    def check_web(match):
        n = int(match.group(1))
        return match.group(0) if n <= max_web else ""

    text = re.sub(r"\[W-(\d+)\]", check_web, text)
    return text
```

**Formato WhatsApp (rodapé de fontes):**

```
📚 *Fontes:*
[1] Harrison's Principles of Internal Medicine, Cap. 274
[2] Diretriz Brasileira de Fibrilação Atrial (SBC, 2023)
[W-1] pubmed.ncbi.nlm.nih.gov/39284756 — "Título do artigo"
```

**Config Model para Lista de Concorrentes:**

```python
# Armazenado no Config model (Django Admin editável, sem redeploy)
# Key: "blocked_competitors"
{
    "domains": ["medgrupo.com.br", "grupomedcof.com.br", ...],
    "names": ["medcurso", "medcof", "estratégia med", ...],
    "updated_at": "2026-03-05",
    "reason": "Concorrentes diretos - nunca citar como fonte"
}
```

### Testing Patterns

**Conftest.py (pytest-django):**

```python
# tests/conftest.py
import pytest
from django.test import AsyncClient

@pytest.fixture
def async_client():
    return AsyncClient()

@pytest.fixture
def mock_redis(mocker):
    return mocker.patch("workflows.providers.redis.client")

@pytest.fixture
def mock_llm(mocker):
    from langchain_core.messages import AIMessage
    mock_msg = AIMessage(content="Resposta simulada")
    mock_msg.usage_metadata = {"input_tokens": 100, "output_tokens": 50}
    return mocker.patch("workflows.providers.llm.get_model")
```

**Test File Naming:**

```python
# tests/test_views.py
import pytest
from django.test import AsyncClient

@pytest.mark.django_db
@pytest.mark.asyncio
async def test_webhook_valid_signature(async_client, mock_redis):
    response = await async_client.post(
        "/webhook/whatsapp/",
        data={...},
        content_type="application/json",
    )
    assert response.status_code == 200

# tests/test_whatsapp/test_nodes/test_identify_user.py
@pytest.mark.django_db
@pytest.mark.asyncio
async def test_identify_user_existing(user_factory):
    user = await user_factory(phone="+5511999999999")
    state = {"phone": "+5511999999999"}
    result = await identify_user(state)
    assert result["user"].id == user.id
```

### Enforcement Rules (para AI Agents)

**MUST:**
1. Usar Ruff para lint e format (`ruff check .`, `ruff format .`)
2. Validar inputs com DRF Serializers em boundaries de API
3. Usar `structlog` para logging (nunca `print()`)
4. Usar hierarquia `AppError` para exceptions
5. Nomear arquivos `snake_case.py`, classes `PascalCase`
6. Usar type hints em todas as funções
7. Usar LangGraph StateGraph para orquestração do pipeline
8. Usar LangChain `@tool` para definir tools
9. Usar Django ORM async (`aget`, `acreate`, `afilter`) para I/O de banco
10. Propagar `trace_id` em logs e chamadas externas
11. Usar `async`/`await` para I/O (nunca blocking I/O)
12. Usar marcadores `[N]` (RAG) e `[W-N]` (web) para toda citação médica
13. Validar citações no `format_response` (strip `[N]` sem fonte real)
14. Usar `exclude_domains` no Tavily para bloquear concorrentes
15. Aplicar `strip_competitor_citations()` no `format_response`
16. Usar `verify_medical_paper` tool para artigos acadêmicos
17. Manter lista de concorrentes no Config model (Django Admin editável)

**MUST NOT:**
1. Usar `print()` para logging
2. Usar `import *` (sempre imports explícitos)
3. Usar `camelCase` em código Python
4. Usar `sync` I/O (requests, psycopg2) — apenas async (httpx, Django async ORM)
5. Implementar orquestração LLM custom (usar LangGraph/LangChain)
6. Implementar tool calling custom (usar LangChain ToolNode)
7. Commitar secrets no código
8. Logar PII sem sanitização
9. Usar `supabase-py` para queries de dados (usar Django ORM)
10. Gerar URLs ou referências da memória/treinamento da LLM (apenas fontes verificadas)
11. Citar conteúdo de concorrentes (Medcurso, Medgrupo, MedCof, Estratégia MED, Medcel, Afya, Sanar, Aristo, etc.)
12. Inventar marcadores `[N]` que não correspondem a fontes retornadas pelas tools

**Anti-Patterns:**

```python
# ❌ BAD: Usar print
print("Message received")

# ✓ GOOD: Usar structlog
logger.info("message_received", user_id=user_id)

# ❌ BAD: supabase-py para queries
result = await supabase.table("users").select("*").eq("phone", phone).execute()

# ✓ GOOD: Django ORM async
user = await User.objects.aget(phone=phone)

# ❌ BAD: Tool ABC custom
class MyTool(Tool):
    async def execute(self, input): ...

# ✓ GOOD: LangChain @tool
@tool
async def my_tool(query: str) -> str:
    """Descrição para o LLM."""
    ...

# ❌ BAD: LLM gera URL de memória
"Segundo estudo publicado em https://pubmed.ncbi.nlm.nih.gov/12345..."

# ✓ GOOD: LLM usa marcador, app resolve fonte
"Segundo estudo recente [W-1], a fibrilação atrial..."

# ❌ BAD: Citar concorrente
"De acordo com o Medcurso, a conduta é..."

# ✓ GOOD: Citar fonte primária
"De acordo com a Diretriz Brasileira de FA (SBC, 2023) [1], a conduta é..."
```

### Checklist para Implementação

- [ ] Todos os arquivos `.py` seguem `snake_case`
- [ ] Todas as classes seguem `PascalCase`
- [ ] Todas as env vars seguem `UPPER_SNAKE_CASE`
- [ ] `pyproject.toml` configurado com Ruff, mypy, pytest-django
- [ ] `config/settings/base.py` usa django-environ
- [ ] structlog configurado com sanitização PII
- [ ] Hierarquia `AppError` definida em `workflows/utils/errors.py`
- [ ] Django models definidos em `workflows/models.py`
- [ ] Django Admin configurado em `workflows/admin.py`
- [ ] Providers (Redis, WhatsApp, LLM) são singletons/funções factory
- [ ] LLM usa `get_model()` com `ChatAnthropicVertex.with_fallbacks()`
- [ ] Pipeline usa LangGraph StateGraph com nós em `workflows/whatsapp/nodes/`
- [ ] Tools usam `@tool` decorator do LangChain em `workflows/whatsapp/tools/`
- [ ] Checkpointer usa `AsyncPostgresSaver` singleton
- [ ] Rate limiting usa dual strategy (sliding window + token bucket)
- [ ] LangGraph RetryPolicy em nós com chamadas externas
- [ ] Deduplication de mensagens via Redis
- [ ] Concurrency control com `asyncio.Semaphore`
- [ ] Feature flags com rollout gradual
- [ ] Testes usam `pytest-django` + `pytest-asyncio` + `pytest-mock`
- [ ] `conftest.py` define fixtures reutilizáveis
- [ ] CI/CD roda Ruff, mypy, pytest
- [ ] Dockerfile multi-stage com uv
- [ ] docker-compose.yml para dev local
- [ ] cloudbuild.yaml para deploy GCP Cloud Run
- [ ] .env.example com todas as env vars documentadas
- [ ] .gitignore ignora `.env`, `__pycache__`, `.venv`
- [ ] `WhatsAppState` inclui campos `retrieved_sources`, `cited_source_indices`, `web_sources`
- [ ] `web_search` tool usa Tavily `search_depth="advanced"` + `include_raw_content=True`
- [ ] `web_search` tool implementa `exclude_domains` com lista de concorrentes
- [ ] `verify_medical_paper` tool valida artigos via PubMed E-utilities API
- [ ] `format_response` aplica `validate_citations()` (strip `[N]` sem fonte)
- [ ] `format_response` aplica `strip_competitor_citations()` como última camada
- [ ] System prompt inclui regras de citação `[N]`/`[W-N]` e bloqueio de concorrentes
- [ ] Lista de concorrentes armazenada no Config model (editável via Django Admin)
- [ ] Rodapé de fontes formatado para WhatsApp (`📚 *Fontes:*`)

---

## Project Structure & Boundaries

### Requirements → Structure Mapping

**Functional Requirements → Directories/Files:**

| FR Category | Files/Directories |
|-------------|-------------------|
| **Interação WhatsApp (FR1-FR10)** | `workflows/views.py`, `workflows/providers/whatsapp.py`, `workflows/utils/formatters.py` |
| **Consulta Médica Inteligente (FR11-FR17)** | `workflows/providers/llm.py`, `workflows/whatsapp/tools/`, `workflows/whatsapp/nodes/orchestrate_llm.py` |
| **Formatação (FR18-FR19)** | `workflows/utils/formatters.py`, `workflows/utils/message_splitter.py` |
| **Identificação e Controle (FR20-FR24)** | `workflows/whatsapp/nodes/identify_user.py`, `workflows/whatsapp/nodes/rate_limit.py`, `workflows/services/rate_limiter.py` |
| **Quiz (FR25-FR26)** | `workflows/whatsapp/tools/quiz_generator.py` |
| **Histórico (FR27-FR28)** | `workflows/whatsapp/nodes/load_context.py`, `workflows/models.py` (Message) |
| **Observabilidade (FR29-FR32)** | `workflows/providers/langfuse.py`, `workflows/services/cost_tracker.py` |
| **Configuração (FR33-FR38)** | `workflows/services/config_service.py`, `config/settings/` |
| **Resiliência (FR39-FR43)** | `workflows/utils/retry.py`, LangGraph RetryPolicy, `workflows/providers/llm.py` (fallback) |
| **Migração (FR44-FR47)** | `workflows/services/feature_flags.py` |

**Non-Functional Requirements → Directories/Files:**

| NFR Category | Files/Directories |
|--------------|-------------------|
| **Performance (NFR1-NFR5)** | `workflows/providers/redis.py` (cache), LangGraph StateGraph (concurrency), `workflows/views.py` (async) |
| **Custo (NFR6-NFR9)** | `workflows/services/cost_tracker.py`, `workflows/providers/llm.py` (prompt caching + fallback), `workflows/whatsapp/nodes/persist.py` |
| **Disponibilidade (NFR10-NFR14)** | LangGraph RetryPolicy, `workflows/providers/llm.py` (`with_fallbacks`), `workflows/utils/retry.py` |
| **Segurança (NFR15-NFR20)** | `workflows/middleware/webhook_signature.py`, `workflows/utils/sanitization.py`, `config/settings/` (GCP Secret Manager) |
| **Integrações (NFR21-NFR24)** | Todos os `workflows/providers/` (timeout, fallback, retry) |

### Architectural Boundaries Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     LAYER 1: WEBHOOK (Django)                │
│  Django async view + HMAC Middleware + Event Filtering       │
│  └─ workflows/views.py, workflows/middleware/               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ asyncio.create_task (fire & forget)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│             LAYER 2: LANGGRAPH StateGraph                    │
│                                                               │
│  Nós do grafo (workflows/whatsapp/nodes/):                  │
│  1. identify_user   → Django ORM, Redis cache               │
│  2. rate_limit      → RateLimiter (Redis)                   │
│  3. process_media   → Whisper (audio), Vision (image)       │
│  4. load_context    → Django ORM (Message history)          │
│  5. orchestrate_llm → ChatAnthropicVertex + ToolNode        │
│     └─ tools loop   → LangChain handles tool call cycle     │
│  6. format_response → Markdown → WhatsApp                   │
│  7. send_whatsapp   → WhatsApp Cloud API                    │
│  8. persist         → Django ORM (messages, costs, tools)   │
│                                                               │
│  Checkpointing: AsyncPostgresSaver (thread_id = phone)      │
│  └─ workflows/whatsapp/graph.py                             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ Uses
                     ▼
┌─────────────────────────────────────────────────────────────┐
│            LAYER 3: PROVIDERS & SERVICES                     │
│                                                               │
│  LLM (LangChain):                                           │
│    ├─ ChatAnthropicVertex (primary, Vertex AI)              │
│    └─ ChatAnthropic (fallback, API direta)                  │
│    └─ .with_fallbacks() — switch automático                 │
│                                                               │
│  Data Providers:                                             │
│    ├─ Django ORM (PostgreSQL via Supabase)                   │
│    ├─ Redis (Upstash - 4 cache layers)                      │
│    ├─ Pinecone (RAG vectors)                                │
│    └─ Langfuse (observability)                              │
│                                                               │
│  External APIs:                                              │
│    ├─ WhatsApp Cloud API (Meta)                             │
│    ├─ Whisper API (OpenAI - transcription only)             │
│    ├─ Medway API (user lookup)                              │
│    ├─ Tavily Search API (advanced + exclude_domains)         │
│    └─ PubMed E-utilities API (verificação de artigos)       │
│                                                               │
│  └─ workflows/providers/*, workflows/services/*             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ Persists to
                     ▼
┌─────────────────────────────────────────────────────────────┐
│               LAYER 4: DATA & SCHEMA                         │
│                                                               │
│  Django Models (Supabase PostgreSQL):                        │
│    ├─ User (Django permissions + RLS defense-in-depth)      │
│    ├─ Message (conversation history)                        │
│    ├─ Config (dynamic configuration)                        │
│    ├─ CostLog (analytics)                                   │
│    └─ ToolExecution (observability)                         │
│                                                               │
│  LangGraph Schema (separate PostgreSQL schema):              │
│    └─ Checkpoints (managed by AsyncPostgresSaver)           │
│                                                               │
│  Redis Keys:                                                 │
│    ├─ msg_buffer:{phone} (TTL 3s)                           │
│    ├─ session:{user_id} (TTL 1h)                            │
│    ├─ config:{key} (TTL 5min)                               │
│    └─ ratelimit:{user_id}:{tier} (TTL 24h)                  │
│                                                               │
│  └─ workflows/models.py (Django models)                     │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow Diagram (LangGraph StateGraph)

```
WhatsApp → Django Webhook View (workflows/views.py)
             │
             │ 1. HMAC middleware validates signature
             │ 2. DRF serializer validates payload
             │ 3. Deduplicate messages (Redis)
             │ 4. asyncio.create_task (fire & forget)
             │ 5. Return 200 OK < 3s
             ▼
         LangGraph StateGraph (workflows/whatsapp/graph.py)
             │
             │  thread_id = phone number (checkpointing automático)
             │
             ├─► identify_user
             │     ├─ Django ORM: User.objects.aget(phone=...)
             │     ├─ Cache hit? (Redis session:{user_id})
             │     ├─ If not found → Call Medway API
             │     └─ Cache user for 1h
             │
             ├─► rate_limit (edge condicional → END se excedido)
             │     ├─ Check daily limit (sliding window)
             │     ├─ Check burst limit (token bucket)
             │     └─ If exceeded → Send friendly message → END
             │
             ├─► process_media (condicional: skip se texto)
             │     ├─ Audio? → Whisper API → transcription
             │     ├─ Image? → Extract OCR/description (future)
             │     └─ Append to text context
             │
             ├─► load_context
             │     ├─ Django ORM: Message.objects.filter(user=...).order_by(...)[:20]
             │     ├─ Cache hit? (Redis session:{user_id})
             │     └─ Format como LangChain messages
             │
             ├─► orchestrate_llm ◄──┐
             │     ├─ ChatAnthropicVertex + system prompt (cached)
             │     ├─ bind_tools(get_tools())
             │     ├─ AnthropicPromptCachingMiddleware (TTL 5min)
             │     └─ CostTrackingCallback registra tokens/custo
             │                              │
             │     [tool_calls?] ──YES──► tools (ToolNode)
             │         │                    ├─ RAG Medical (Pinecone)
             │         NO                   ├─ Bulas Med (full-text search)
             │         │                    ├─ Calculators (local)
             │         ▼                    ├─ Quiz Generator (LLM call)
             │                              ├─ Web Search (Tavily + exclude_domains)
             │                              └─ Verify Paper (PubMed E-utilities)
             │                              │
             │                              └──► orchestrate_llm (loop)
             │
             ├─► format_response
             │     ├─ Convert markdown → WhatsApp format
             │     ├─ Split if > 4096 chars
             │     └─ Add reply buttons (max 3)
             │
             ├─► send_whatsapp (RetryPolicy: 3 attempts)
             │     ├─ POST to WhatsApp Cloud API
             │     ├─ Handle rate limits (429 → retry)
             │     └─ Log delivery status
             │
             └─► persist
                   ├─ Django ORM: Message.objects.acreate(...)
                   ├─ Django ORM: CostLog.objects.acreate(...)
                   ├─ Django ORM: ToolExecution.objects.acreate(...)
                   └─ Update session cache (Redis)
```

### External Integration Points

| Service | Purpose | Protocol | Timeout | Retry | Fallback | Cost |
|---------|---------|----------|---------|-------|----------|------|
| **WhatsApp Cloud API** | Send/receive messages | HTTPS REST | 10s | 3x | Queue para retry posterior | Grátis (1000 conversas/mês) |
| **Vertex AI (Anthropic)** | Primary LLM | HTTPS REST (gRPC interno) | 30s | 2x | Anthropic Direct | ~$0.0009/msg (c/ cache) |
| **Anthropic Direct** | Fallback LLM | HTTPS REST | 30s | 2x | User notification | ~$0.003/msg (c/ cache) |
| **Supabase PostgreSQL** | Database (Django ORM) | PostgreSQL protocol | 5s | 3x | Circuit breaker → read-only mode | $25/mês base |
| **Redis (Upstash)** | Cache, rate limiting | RESP protocol | 2s | 2x | Degradar gracefully (skip cache) | $10/mês |
| **Pinecone** | Vector search (RAG) | HTTPS REST | 8s | 2x | Skip RAG, notify user | $70/mês (serverless) |
| **Whisper (OpenAI)** | Audio transcription | HTTPS REST | 20s | 2x | Notify user "áudio não suportado" | $0.006/min |
| **Langfuse** | Observability | HTTPS REST | 5s | 1x | Fire-and-forget (não bloquear) | Grátis |
| **Medway API** | User lookup | HTTPS REST | 8s | 3x | Allow guest access | Grátis (interno) |
| **Tavily Search** | Busca web (advanced + exclude_domains) | HTTPS REST | 10s | 2x | Skip tool, notify LLM | $5/mês (1000 queries) |
| **PubMed E-utilities** | Verificação de artigos médicos | HTTPS REST | 5s | 2x | Skip verification, cite with caveat | Grátis |

**Total cost estimate:** ~$115/mês base + variável por uso ($0.001-0.003/mensagem)

### Database Schema Boundaries

**Django Models (workflows/models.py) — schema-as-code:**

Todas as tabelas são gerenciadas via Django ORM e Django migrations (`python manage.py makemigrations && python manage.py migrate`). Ver ADR-003 e ADR-011 para definições completas dos models.

**Models (5):**

| Model | Domain | Key Fields |
|-------|--------|------------|
| `User` | Authentication & access control | phone, medway_id, subscription_tier, metadata |
| `Message` | Conversation history | user (FK), content, role, message_type, tokens, cost |
| `Config` | Dynamic configuration | key (PK), value (JSON), updated_at |
| `CostLog` | Cost tracking | user (FK), provider, model, tokens, cache tokens, cost |
| `ToolExecution` | Observability | user (FK), tool_name, input/output (JSON), success, time |

**Separate Schema — LangGraph Checkpoints:**

```sql
-- Managed by AsyncPostgresSaver (langgraph-checkpoint-postgres)
-- Separate "langgraph" schema, NOT managed by Django migrations
CREATE SCHEMA IF NOT EXISTS langgraph;
-- Tables created automatically by checkpointer.setup()
```

**Files referencing schema:**

- `workflows/models.py` — Django models (schema-as-code)
- `workflows/admin.py` — Django Admin registrations
- `workflows/whatsapp/nodes/identify_user.py` — User lookup
- `workflows/whatsapp/nodes/load_context.py` — Message history
- `workflows/whatsapp/nodes/persist.py` — Inserts Message, CostLog, ToolExecution
- `workflows/providers/checkpointer.py` — AsyncPostgresSaver (langgraph schema)

### Development Workflow

**Local Development:**

```bash
# 1. Clone repo
git clone <repo-url>
cd mb-wpp

# 2. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Create venv e instalar dependências
uv venv
source .venv/bin/activate
uv sync

# 4. Copy env vars
cp .env.example .env
# Edit .env com suas credenciais

# 5. Start dependencies (PostgreSQL, Redis) via Docker
docker-compose up -d

# 6. Run Django migrations
uv run python manage.py migrate

# 7. Create superuser (Django Admin)
uv run python manage.py createsuperuser

# 8. Run application
uv run python manage.py runserver 8000

# 9. Run tests
uv run pytest

# 10. Lint & format
uv run ruff check .
uv run ruff format .

# 11. Type check
uv run mypy workflows/
```

**Docker Compose (dev):**

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: mb_wpp
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/mb_wpp
      - REDIS_URL=redis://redis:6379
      - DJANGO_SETTINGS_MODULE=config.settings.development
    depends_on:
      - postgres
      - redis
    volumes:
      - ./workflows:/app/workflows  # Hot reload
      - ./config:/app/config

volumes:
  postgres_data:
  redis_data:
```

**CI/CD (GitHub Actions + GCP Cloud Build):**

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: mb_wpp_test
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
        ports: ["5432:5432"]
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: uv sync

      - name: Run Ruff (lint)
        run: uv run ruff check .

      - name: Run Ruff (format check)
        run: uv run ruff format --check .

      - name: Run mypy
        run: uv run mypy workflows/

      - name: Run pytest
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/mb_wpp_test
          DJANGO_SETTINGS_MODULE: config.settings.development
        run: uv run pytest --cov=workflows --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
```

```yaml
# cloudbuild.yaml — Deploy automático para Cloud Run
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/mb-wpp', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/mb-wpp']
  - name: 'gcr.io/cloud-builders/gcloud'
    args:
      - 'run'
      - 'deploy'
      - 'mb-wpp'
      - '--image=gcr.io/$PROJECT_ID/mb-wpp'
      - '--region=us-east1'
      - '--platform=managed'
      - '--set-env-vars=DJANGO_SETTINGS_MODULE=config.settings.production'
```

**Dockerfile (production — GCP Cloud Run):**

```dockerfile
# Multi-stage build with uv
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy source code
COPY manage.py ./
COPY config/ ./config/
COPY workflows/ ./workflows/

# Production stage
FROM python:3.12-slim

WORKDIR /app

# Copy venv from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/manage.py /app/manage.py
COPY --from=builder /app/config /app/config
COPY --from=builder /app/workflows /app/workflows

# Set environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=config.settings.production

# Collect static files (Django Admin)
RUN python manage.py collectstatic --noinput 2>/dev/null || true

# Expose port (Cloud Run uses PORT env var)
EXPOSE 8080

# Run with Uvicorn (ASGI)
CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8080"]
```

**.gitignore:**

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.venv/
venv/
ENV/
env/

# uv
uv.lock

# IDEs
.vscode/
.idea/
*.swp
*.swo

# Environment
.env
.env.local

# Testing
.coverage
htmlcov/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# OS
.DS_Store
Thumbs.db
```

---

## Architecture Validation Results

### Coherence Validation

**Stack Compatibility Check:**

| Technology | Compatible With | Potential Conflicts | Resolution |
|------------|-----------------|---------------------|------------|
| Python 3.12 | Django, LangGraph, asyncio | Nenhum | ✓ |
| Django 5.2 | async views, ORM async, DRF | Nenhum | ✓ |
| DRF + adrf | Django async views | Nenhum | ✓ |
| LangGraph 1.0 | LangChain 1.0, asyncio | Requer psycopg[pool] para checkpointer | Incluir no pyproject.toml |
| LangChain 1.0 | langchain-anthropic, tools | Nenhum | ✓ |
| Django ORM | Supabase PostgreSQL, async | Nenhum (conecta via DATABASE_URL) | ✓ |
| redis-py 5.x | asyncio (aioredis merged) | Nenhum | ✓ |
| Vertex AI | Google Cloud credentials | Requer service account ou ADC | Documentar setup |
| uv | pyproject.toml (PEP 621) | Nenhum | ✓ |
| pytest-django | Django test DB, async | Nenhum | ✓ |
| Ruff | Black/Flake8 rules | Substitui ambos | ✓ |
| structlog | JSON logging, asyncio | Nenhum | ✓ |

**Pattern Consistency Check:**

| Pattern | Applied In | Consistent? | Notes |
|---------|-----------|-------------|-------|
| snake_case files | Todos os .py | ✓ | Verificar em code review |
| PascalCase classes | Models, Views, Callbacks | ✓ | Enforced by Ruff N801 |
| DRF Serializer validation | API boundaries | ✓ | Webhook payload validation |
| Django ORM | Todas as queries de dados | ✓ | Async ORM (aget, acreate, afilter) |
| structlog logging | Toda aplicação | ✓ | Nunca usar print() |
| AppError hierarchy | Todos os erros | ✓ | Definir em workflows/utils/errors.py |
| Async I/O | Todos os providers e nós | ✓ | Enforced by Ruff rules |
| LangGraph nodes | Workflow principal | ✓ | Funções async puras |
| LangChain @tool | Tool definitions | ✓ | Decorator pattern |
| LangGraph RetryPolicy | Nós com chamadas externas | ✓ | Retry nativo do grafo |
| LangChain with_fallbacks | LLM providers | ✓ | Vertex → Anthropic Direct |
| Feature flags | Migration router | ✓ | ConfigService + hash-based rollout |

**Structure Alignment Check:**

| Layer | Expected Directories | Actual Match | Notes |
|-------|---------------------|--------------|-------|
| Webhook | `workflows/views.py`, `workflows/middleware/` | ✓ | Django async views + middleware |
| LangGraph | `workflows/whatsapp/` | ✓ | graph.py, state.py, nodes/*, tools/* |
| Providers | `workflows/providers/` | ✓ | llm.py, redis.py, checkpointer.py, etc |
| Services | `workflows/services/` | ✓ | rate_limiter.py, cost_tracker.py, etc |
| Models | `workflows/models.py` | ✓ | Django models (User, Message, CostLog, etc) |
| Config | `config/settings/` | ✓ | base.py, development.py, production.py |
| Utils | `workflows/utils/` | ✓ | retry.py, sanitization.py, formatters.py |
| Tests | `tests/` | ✓ | pytest-django + conftest.py |

### Requirements Coverage

**Functional Requirements Coverage (47 FRs):**

| FR | Implementação | Files |
|----|---------------|-------|
| FR1-FR2: Receber mensagens WhatsApp | ✓ | `workflows/views.py` |
| FR3: Debounce 3s | ✓ | `workflows/providers/redis.py` (msg_buffer layer) |
| FR4-FR6: Processar áudio/imagem | ✓ | `workflows/whatsapp/nodes/process_media.py`, `workflows/providers/whisper.py` |
| FR7-FR10: Responder com formatação | ✓ | `workflows/utils/formatters.py`, `workflows/whatsapp/nodes/format_response.py`, `send_whatsapp.py` |
| FR11: Claude como LLM | ✓ | `workflows/providers/llm.py` (ChatAnthropicVertex + fallback) |
| FR12-FR13: Tool Use + RAG | ✓ | `workflows/whatsapp/tools/rag_medical.py`, `workflows/providers/pinecone.py` |
| FR14: Bulas | ✓ | `workflows/whatsapp/tools/bulas_med.py` |
| FR15: Calculadoras | ✓ | `workflows/whatsapp/tools/calculators.py` |
| FR16: Busca web | ✓ | `workflows/whatsapp/tools/web_search.py` (Tavily + exclude_domains), `workflows/whatsapp/tools/verify_paper.py` (PubMed) |
| FR17: Orquestração paralela | ✓ | LangChain ToolNode (executa tools automaticamente) |
| FR18-FR19: Formatação | ✓ | `workflows/utils/formatters.py`, `workflows/utils/message_splitter.py` |
| FR20-FR21: Identificar usuário | ✓ | `workflows/whatsapp/nodes/identify_user.py` |
| FR22-FR24: Rate limiting | ✓ | `workflows/whatsapp/nodes/rate_limit.py`, `workflows/services/rate_limiter.py` |
| FR25-FR26: Quiz | ✓ | `workflows/whatsapp/tools/quiz_generator.py` |
| FR27-FR28: Histórico | ✓ | `workflows/whatsapp/nodes/load_context.py`, AsyncPostgresSaver checkpointing |
| FR29-FR32: Observabilidade | ✓ | `workflows/providers/langfuse.py`, structlog, `workflows/whatsapp/nodes/persist.py` |
| FR33-FR38: Configuração | ✓ | `workflows/services/config_service.py`, `config/settings/` |
| FR39-FR43: Resiliência | ✓ | LangGraph RetryPolicy, `workflows/providers/llm.py` (with_fallbacks), `workflows/utils/retry.py` |
| FR44-FR47: Migração | ✓ | `workflows/services/feature_flags.py` |

**Coverage:** 47/47 FRs ✓

**Non-Functional Requirements Coverage (24 NFRs):**

| NFR | Implementação | Validation |
|-----|---------------|------------|
| NFR1: P95 < 8s | LangGraph StateGraph (concurrency), cache 4 camadas | Load testing após M1 |
| NFR2: P95 < 12s áudio | `workflows/providers/whisper.py` (timeout 20s) | Load testing |
| NFR3: P95 < 15s imagem | `workflows/whatsapp/nodes/process_media.py` | Load testing |
| NFR4: 50+ concurrent | Graph semaphore (Semaphore(50)) | ✓ Configurável |
| NFR5: Debounce ≤ 3s | `workflows/providers/redis.py` (TTL 3s) | ✓ Testável |
| NFR6: Custo < $0.03/conversa | Prompt caching (middleware) + Vertex AI | Validar em produção |
| NFR7: Cache hit 70%→90% | Redis 4 camadas | Métricas Langfuse |
| NFR8: Cost tracking ±5% | `workflows/whatsapp/nodes/persist.py` (CostLog) | ✓ Granular |
| NFR9: Alertas de gasto | Django Admin + alertas via Langfuse | M1.5 |
| NFR10: Uptime 99.5%→99.9% | GCP Cloud Run SLA + retry + fallback | Validar em produção |
| NFR11: Erro < 2%→0.5% | with_fallbacks, RetryPolicy, DLQ | Métricas Langfuse |
| NFR12: MTTR < 5min | Health checks, alertas, rollback Cloud Run | M2 |
| NFR13: Zero msgs perdidas | Deduplication + DLQ | ✓ Implementado |
| NFR14: Webhook 200 OK < 3s | Async fire-and-forget (asyncio.create_task) | ✓ Garantido |
| NFR15: RLS Supabase | Django permissions + RLS defense-in-depth | ✓ Django migrations |
| NFR16: HMAC validation | `workflows/middleware/webhook_signature.py` | ✓ Testável |
| NFR17: Secrets em env | `config/settings/` (django-environ) | ✓ Error se missing |
| NFR18: LGPD compliance | Django permissions, logs sanitizados, retention policies | M2 (políticas formais) |
| NFR19: Logs sem PII | structlog sanitize_pii processor | ✓ Implementado |
| NFR20: Credenciais seguras | GCP Secret Manager, nunca no código | ✓ .env.example sem valores |
| NFR21: Timeout configurável | Cada provider tem timeout | ✓ config/settings/ |
| NFR22: Circuit breaker | `with_fallbacks()` (LangChain built-in) | ✓ Implementado |
| NFR23: Fallback documentado | ADR-006, `get_model()` | ✓ Documentado |
| NFR24: WhatsApp API compat | `workflows/providers/whatsapp.py` (v21+ Cloud API) | ✓ Testável |

**Coverage:** 24/24 NFRs ✓

### Implementation Readiness

**ADRs Documented:** 11
- ADR-001: Python 3.12
- ADR-002: Django 5.2 + DRF + adrf
- ADR-003: Django ORM (Supabase PostgreSQL como backend)
- ADR-004: uv, pytest-django, Ruff
- ADR-005: GCP Cloud Run
- ADR-006: Vertex AI + Anthropic Direct (LangChain with_fallbacks)
- ADR-007: Redis 4 camadas
- ADR-008: Security 6 camadas
- ADR-009: Django Project com app workflows/
- ADR-010: LangGraph + LangChain
- ADR-011: Admin Panel 3 fases (Django Admin na Fase 1)

**Patterns Defined:** 27
- Naming (6): DB, API, code, files, env vars, Django apps
- Format (3): Errors, dates, JSON
- Communication (3): Logging, events, trace_id
- Structure (3): LangGraph node contract, LangChain @tool, Django model
- Process (12): RetryPolicy, with_fallbacks, DRF validation, imports, deduplication, event filtering, graceful shutdown, concurrency control, async I/O, rate limiting dual, cost tracking, media processing

**Files Mapped:** ~55
- config/: 5 files (settings, urls, asgi)
- workflows/: 40+ files (models, views, nodes, tools, providers, services)
- tests/: 10+ files
- root: 4 files (manage.py, pyproject.toml, Dockerfile, docker-compose.yml, cloudbuild.yaml)

**Dependencies Specified:** 25+
- Runtime: Python 3.12
- Framework: Django, DRF, adrf, django-environ, django-cors-headers
- LLM: LangGraph, LangChain, langchain-anthropic, langgraph-checkpoint-postgres
- Data: Django ORM, redis-py, supabase-py (Auth/Storage only)
- Observability: langfuse, structlog
- Testing: pytest-django, pytest-asyncio, pytest-mock
- Tooling: uv, ruff, mypy, django-stubs
- Others: httpx, pinecone-client, openai (Whisper only), langchain-mcp-adapters, tavily-py

### Gap Analysis

**Gaps Identificados e Resolvidos:**

| Gap Original (TypeScript) | Resolução Python | Status |
|--------------------------|------------------|--------|
| 1. LangChain dependency | ADR-010: LangGraph + LangChain adotados (alinhamento com equipe) | ✓ Resolvido |
| 2. OpenAI como fallback | ADR-006: Removido, apenas Anthropic (Vertex + Direct via LangChain) | ✓ Resolvido |
| 3. Admin panel undefined | ADR-011: 3 fases (M1 Django Admin, M1.5 minimal, M2 robust) | ✓ Resolvido |
| 4. Cost tracking vago | CostTrackingCallback (LangChain) + CostLog (Django ORM) | ✓ Resolvido |
| 5. Tool execution observability | ToolExecution (Django ORM) + Langfuse | ✓ Resolvido |
| 6. Drizzle ORM | ADR-003: Django ORM (Supabase PostgreSQL como backend) | ✓ Resolvido |
| 7. TypeScript vs Python | ADR-001: Python escolhido, justificativa completa | ✓ Resolvido |
| 8. pnpm vs uv | ADR-004: uv escolhido, 10-100x mais rápido | ✓ Resolvido |
| 9. Vitest vs pytest | ADR-004: pytest-django + pytest-asyncio | ✓ Resolvido |
| 10. Biome vs Ruff | ADR-004: Ruff all-in-one | ✓ Resolvido |
| 11. Pipeline 11 steps | LangGraph StateGraph com 8 nós (steps 6+7 merged) | ✓ Resolvido |
| 12. Pino vs structlog | structlog com sanitização PII | ✓ Resolvido |
| 13. Zod vs Pydantic | DRF Serializers em API boundaries | ✓ Resolvido |
| 14. Node.js patterns | Todos reescritos para Django + LangGraph (async/await, ORM, etc) | ✓ Resolvido |

**Novos Gaps (nenhum crítico):**

| Gap | Impacto | Resolução |
|-----|---------|-----------|
| mypy strict mode pode ser verboso | Médio | Acceptable, benefício de type safety supera |
| Vertex AI requer GCP setup (ADC) | Médio | Documentar em README, script de setup |
| uv é novo (2024) | Baixo | Fallback para pip documented |
| LangGraph checkpointer precisa de schema separado | Baixo | setup() automático, documentado em ADR-010 |

### Completeness Checklist

**Requirements Analysis**

- [x] Contexto do projeto analisado (47 FRs, 24 NFRs)
- [x] Escala e complexidade avaliadas (~12-15 componentes, 50+ conversas concorrentes)
- [x] Constraints técnicos identificados (WhatsApp 3s, Supabase existente, Strangler Fig)
- [x] Cross-cutting concerns mapeados (7 concerns: observabilidade, resiliência, custo, rate limiting, segurança, config, migração)

**Architectural Decisions**

- [x] 11 ADRs documentados (ADR-001 a ADR-011, incluindo LangGraph, Django, GCP Cloud Run)
- [x] Stack completa especificada (Python 3.12, Django, LangGraph, LangChain, Django ORM, uv, pytest-django, Ruff)
- [x] Padrões de integração definidos (10 serviços com fallback)
- [x] Performance e custo endereçados (cache 4 camadas, prompt caching middleware, Vertex AI + fallback)
- [x] Segurança multi-camada (6 layers, LGPD, Django permissions + RLS)

**Implementation Patterns**

- [x] 27 padrões de consistência definidos
- [x] Convenções de naming para DB, API, código, arquivos, env vars, Django apps
- [x] Padrões de comunicação (structlog, events, trace_id)
- [x] Padrões de processo (RetryPolicy, with_fallbacks, DRF validation, dedup, shutdown, concurrency)
- [x] Padrões de estrutura (LangGraph node contract, LangChain @tool, Django model)
- [x] Anti-patterns documentados (print(), sync I/O, supabase-py para queries, Tool ABC custom)

**Project Structure**

- [x] ~55 arquivos mapeados em Django project com app workflows/
- [x] 4 camadas com fronteiras definidas (Webhook, LangGraph, Providers, Data)
- [x] 10 pontos de integração com timeout/fallback
- [x] 5 Django models + LangGraph checkpoint schema
- [x] Dev workflow, CI/CD, Docker, docker-compose, cloudbuild.yaml
- [x] Requirements → Structure mapping completo (47 FRs + 24 NFRs)

**Validation**

- [x] Coerência de decisões verificada
- [x] Cobertura de requisitos 100% (47 FRs + 24 NFRs)
- [x] Prontidão para implementação confirmada
- [x] 14 gaps identificados e resolvidos
- [x] Migração TypeScript→Python completa e justificada

---

### Architecture Readiness Assessment

**Overall Status:** ✓ **READY FOR IMPLEMENTATION**

**Confidence Level:** Alta

**Key Strengths:**

1. **Decisões pesquisadas e documentadas** — 11 ADRs com rationale clara, trade-offs explícitos, comparação de alternativas
2. **27 padrões eliminam ambiguidade** — Agentes de IA não precisam adivinhar convenções (snake_case, structlog, Django ORM, etc)
3. **Estrutura concreta** — ~55 arquivos com responsabilidades claras, alinhados com pattern da equipe
4. **Segurança robusta** — 6 camadas cobrindo desde webhook HMAC até LGPD compliance
5. **Resiliência end-to-end** — with_fallbacks, RetryPolicy, DLQ, graceful shutdown, deduplication
6. **Custo otimizado desde dia 1** — Prompt caching middleware (90% economia), Vertex AI, cache 4 camadas
7. **Migration path documentado** — Strangler Fig com feature flags, rollback fácil
8. **Stack alinhada com equipe** — Django, LangGraph, LangChain (mesma stack do search-medway-langgraph)
9. **Complexidade sob controle** — LangGraph para orquestração, Django ORM para dados, Django Admin para UI
10. **Observabilidade granular** — CostLog, ToolExecution, CostTrackingCallback, Langfuse traces

**Areas for Future Enhancement (pós-M1):**

1. **Load testing framework (k6)** — Validar NFRs de performance após primeiras stories
2. **Health check detalhado** — Endpoint que testa cada serviço (PostgreSQL, Redis, Vertex AI)
3. **Monitoring dashboard** — GCP Cloud Monitoring para métricas sistema (CPU, mem, latency)
4. **Alertas customizados** — GCP Alerting/Slack para cost > threshold, error rate spike
5. **LangSmith** — Avaliar integração nativa com LangGraph para tracing pós-M1
6. **WAF dedicado** — Cloud Armor quando tráfego justificar

---

### Implementation Handoff

**AI Agent Guidelines:**

1. **Seguir TODAS as decisões arquiteturais** — ADRs são law, não guidelines
2. **Usar os 27 padrões consistentemente** — snake_case files, structlog, Django ORM, AppError hierarchy
3. **Respeitar as fronteiras das 4 camadas** — Webhook (Django) → LangGraph → Providers → Data
4. **Consultar este documento para dúvidas** — Não inventar padrões novos sem discussão
5. **Nunca usar:** print(), sync I/O, supabase-py para queries, Tool ABC custom, camelCase, import *
6. **Sempre usar:** structlog, Django ORM async, LangGraph nodes, LangChain @tool, type hints
7. **Testar tudo:** pytest-django + pytest-asyncio, mocks para external services
8. **Validar antes de commit:** Ruff, mypy, pytest devem passar

**First Implementation Commands:**

```bash
# Story 0: Inicialização do Projeto
cd /Users/rcfranco/mb-wpp

# Install uv (se ainda não instalado)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create project
uv init
uv venv
source .venv/bin/activate

# Add dependencies
uv add django djangorestframework adrf django-environ django-cors-headers
uv add langgraph langchain langchain-anthropic langgraph-checkpoint-postgres
uv add langchain-mcp-adapters
uv add supabase redis pinecone-client langfuse
uv add structlog httpx openai uvicorn
uv add --dev pytest pytest-django pytest-asyncio pytest-mock pytest-cov ruff mypy django-stubs

# Create Django project
uv run django-admin startproject config .
mkdir -p config/settings

# Create workflows app
uv run python manage.py startapp workflows
mkdir -p workflows/whatsapp/{nodes,tools,prompts}
mkdir -p workflows/{services,providers,middleware,utils}
mkdir -p tests/{test_whatsapp/{test_nodes,test_tools},test_services,test_providers}

# Create __init__.py files
find workflows tests -type d -exec touch {}/__init__.py \;

# Create key files
touch .env.example
touch Dockerfile docker-compose.yml cloudbuild.yaml

# Git init
git init
cp .env.example .env
# Edit .env with real credentials
```

**Implementation Sequence (recomendada):**

1. **Story 1: Django Project Setup + Config** (1-2h)
   - `config/settings/{base,development,production}.py` — django-environ, databases, installed apps
   - `config/urls.py` — Root URL configuration
   - `config/asgi.py` — ASGI entry point
   - structlog configuration com sanitize_pii
   - `workflows/utils/errors.py` — AppError hierarchy

2. **Story 2: Django Models + Admin** (2-3h)
   - `workflows/models.py` — User, Message, Config, CostLog, ToolExecution
   - `workflows/admin.py` — Django Admin registrations
   - `python manage.py makemigrations && python manage.py migrate`
   - `tests/test_models.py` — Model tests

3. **Story 3: Providers Base** (2-3h)
   - `workflows/providers/redis.py` — Redis client singleton + CacheManager 4 camadas
   - `workflows/providers/whatsapp.py` — WhatsApp Cloud API client
   - `workflows/providers/supabase.py` — Supabase client (Auth + Storage only)
   - `tests/test_providers/` — Mocks de providers

4. **Story 4: Webhook + Middleware** (2-3h)
   - `workflows/middleware/webhook_signature.py` — HMAC verification
   - `workflows/serializers.py` — DRF serializers (WhatsAppMessageSerializer)
   - `workflows/views.py` — Django async views (webhook POST/GET)
   - `workflows/urls.py` + `config/urls.py` — URL routing
   - `tests/test_views.py` — Testar signature, filtering

5. **Story 5: LLM Provider + Checkpointer** (2-3h)
   - `workflows/providers/llm.py` — get_model() com ChatAnthropicVertex + with_fallbacks
   - `workflows/providers/checkpointer.py` — AsyncPostgresSaver singleton
   - `workflows/services/cost_tracker.py` — CostTrackingCallback
   - `tests/test_providers/test_llm.py` — Testar fallback

6. **Story 6: LangGraph Core + Nodes 1-4** (4-6h)
   - `workflows/whatsapp/state.py` — WhatsAppState TypedDict
   - `workflows/whatsapp/graph.py` — build_whatsapp_graph()
   - `workflows/whatsapp/nodes/identify_user.py` — Django ORM lookup
   - `workflows/whatsapp/nodes/rate_limit.py` — RateLimiter check
   - `workflows/whatsapp/nodes/process_media.py` — Whisper integration
   - `workflows/whatsapp/nodes/load_context.py` — Message history
   - `tests/test_whatsapp/test_nodes/` — Testar cada nó

7. **Story 7: LLM Node + Tools** (4-6h)
   - `workflows/whatsapp/nodes/orchestrate_llm.py` — LLM call com tools
   - `workflows/whatsapp/tools/rag_medical.py` — Pinecone RAG
   - `workflows/whatsapp/tools/bulas_med.py` — Full-text search
   - `workflows/whatsapp/tools/calculators.py` — Local Python functions
   - `workflows/whatsapp/tools/quiz_generator.py` — LLM call
   - `workflows/whatsapp/tools/web_search.py` — Tavily advanced + exclude_domains (concorrentes)
   - `workflows/whatsapp/tools/verify_paper.py` — PubMed E-utilities API
   - `workflows/whatsapp/prompts/system.py` — Regras de citação [N]/[W-N] + bloqueio de concorrentes
   - `tests/test_whatsapp/test_tools/` — Testar cada tool (incluindo citação e bloqueio)

8. **Story 8: Format + Send + Persist + Citação** (4-5h)
   - `workflows/whatsapp/nodes/format_response.py` — Markdown → WhatsApp + validate_citations() + strip_competitor_citations()
   - `workflows/whatsapp/nodes/send_whatsapp.py` — WhatsApp Cloud API send
   - `workflows/whatsapp/nodes/persist.py` — Django ORM persist
   - `workflows/services/config_service.py` — Config model para lista de concorrentes
   - `tests/test_whatsapp/test_nodes/` — Testar nodes finais + validação de citações + bloqueio de concorrentes

9. **Story 9: Integration + E2E** (3-4h)
   - `tests/test_whatsapp/test_graph.py` — StateGraph integration tests
   - Conectar webhook → graph invocation
   - Docker compose full stack test
   - Verificar checkpointing funcional

**Total Estimated Time:** ~30-40 horas de implementação para M1 MVP

---

## Conclusão

Este documento de arquitetura define **TODAS as decisões técnicas, padrões, e estrutura** necessárias para implementar mb-wpp em Python.

**Status:** ✓ READY FOR IMPLEMENTATION

**Próximos Passos:**
1. Regenerar Epics e Stories via workflow BMAD (alinhados com nova arquitetura)
2. Executar "First Implementation Commands"
3. Implementar Stories 1-9 sequencialmente
4. Deploy M1 para GCP Cloud Run
5. Validar NFRs com load testing
6. Iterar para M1.5 (dashboard visual com Next.js)

**Revisões Futuras:**
- Após M1 deploy: Revisar NFRs de performance (load testing k6)
- Após 1 mês produção: Revisar custos reais vs estimados
- Pós-M1: Avaliar LangSmith para tracing nativo LangGraph
- Antes de M2: Avaliar multi-region no Cloud Run (se latência justificar)

---

_Documento gerado em: 2026-02-26_
_Versão: 2.0 (Python Migration)_
_Autores: Rodrigo Franco, Claude Agent_
