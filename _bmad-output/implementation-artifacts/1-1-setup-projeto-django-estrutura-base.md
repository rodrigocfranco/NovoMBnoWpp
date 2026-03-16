# Story 1.1: Setup do Projeto Django + Estrutura Base

Status: done

<!-- Nota: Validação é opcional. Execute validate-create-story para verificação de qualidade antes de dev-story. -->

## Story

As a **desenvolvedor**,
I want **o projeto Django configurado com a estrutura definida na arquitetura**,
So that **posso começar a implementar as features sobre uma base sólida e padronizada**.

## Acceptance Criteria

1. **Given** o repositório vazio **When** executo o setup do projeto **Then** o projeto Django 5.2 LTS está configurado com `config/settings/{base,development,production}.py` usando django-environ
   - **NOTA:** A arquitetura especifica Django 5.1+, mas Django 5.1 atingiu end-of-life em dezembro/2025. Usar **Django 5.2 LTS** (suporte até abril/2028, versão atual 5.2.12).

2. **Given** o projeto configurado **When** verifico a estrutura de apps **Then** a app `workflows/` existe com sub-módulos: `whatsapp/` (graph, nodes, tools, prompts), `services/`, `providers/`, `middleware/`, `utils/`

3. **Given** a app workflows criada **When** verifico os models **Then** `workflows/models.py` contém o model `User` com campos: phone (CharField unique), medway_id (CharField unique nullable), subscription_tier (CharField choices free/basic/premium), metadata (JSONField), created_at (DateTimeField auto_now_add)

4. **Given** a app workflows criada **When** verifico os models **Then** `workflows/models.py` contém o model `Message` com campos: user (FK para User), content (TextField), role (CharField), message_type (CharField default="text"), tokens_input (IntegerField nullable), tokens_output (IntegerField nullable), cost_usd (DecimalField nullable), created_at (DateTimeField auto_now_add)

5. **Given** a app workflows criada **When** verifico os models **Then** `workflows/models.py` contém o model `Config` com campos: key (CharField unique), value (JSONField), updated_by (CharField), updated_at (DateTimeField auto_now)

6. **Given** a app workflows criada **When** verifico os models **Then** `workflows/models.py` contém o model `ConfigHistory` com campos: config (FK para Config), old_value (JSONField), new_value (JSONField), changed_by (CharField), changed_at (DateTimeField auto_now_add)

7. **Given** os models Config/ConfigHistory criados **When** verifico os services **Then** `workflows/services/config_service.py` implementa ConfigService básico com `get(key)` que busca Config via Django ORM async (`Config.objects.aget(key=key)`) — sem Redis cache nesta fase

8. **Given** o ConfigService criado **When** rodo as migrations **Then** configs iniciais são populadas via data migration: `rate_limit:free`, `rate_limit:premium`, `blocked_competitors`, `message:welcome`, `message:rate_limit`, `message:unsupported_type`, `debounce_ttl`

9. **Given** os models criados **When** verifico o admin **Then** `workflows/admin.py` registra User, Message, Config e ConfigHistory no Django Admin

10. **Given** o projeto configurado **When** verifico error handling **Then** `workflows/utils/errors.py` define hierarquia AppError → ValidationError, AuthenticationError, RateLimitError, ExternalServiceError, GraphNodeError

11. **Given** o projeto configurado **When** verifico logging **Then** structlog está configurado com JSON rendering e processor `sanitize_pii` (redact phone, name, email, cpf, api_key)

12. **Given** o projeto configurado **When** verifico o pyproject.toml **Then** `pyproject.toml` configura Ruff (line-length=100, target py312), mypy strict, pytest-django

13. **Given** o projeto configurado **When** verifico docker-compose **Then** `docker-compose.yml` sobe PostgreSQL 16 + Redis 7 para dev local

14. **Given** o projeto configurado **When** rodo docker build **Then** `Dockerfile` multi-stage com uv funciona (`docker build` passa)

15. **Given** o projeto configurado **When** verifico variáveis de ambiente **Then** `.env.example` lista todas as variáveis necessárias

16. **Given** o projeto configurado **When** rodo linting **Then** `uv run ruff check .` e `uv run ruff format --check .` passam

17. **Given** o projeto configurado **When** rodo testes **Then** `uv run pytest` roda (mesmo sem testes ainda)

18. **Given** o projeto configurado **When** rodo migrations **Then** Django migrations rodam com sucesso (`uv run python manage.py migrate`)

## Tasks / Subtasks

- [x] Task 1: Inicializar projeto Django com uv (AC: #1, #12, #15)
  - [x] 1.1 Criar `pyproject.toml` com todas as dependências e configuração de Ruff/mypy/pytest
  - [x] 1.2 Rodar `uv sync` para instalar dependências e gerar `uv.lock`
  - [x] 1.3 Criar estrutura Django: `manage.py`, `config/__init__.py`, `config/urls.py`, `config/asgi.py`, `config/wsgi.py`
  - [x] 1.4 Criar `config/settings/base.py` com django-environ, DATABASE_URL, SECRET_KEY, INSTALLED_APPS
  - [x] 1.5 Criar `config/settings/development.py` com DEBUG=True, CORS permissivo
  - [x] 1.6 Criar `config/settings/production.py` com segurança, GCP Secret Manager
  - [x] 1.7 Criar `.env.example` com todas as variáveis documentadas
  - [x] 1.8 Criar `.gitignore` para Python/Django/uv

- [x] Task 2: Criar app workflows com estrutura completa de diretórios (AC: #2)
  - [x] 2.1 Criar app `workflows/` com `apps.py`, `__init__.py`
  - [x] 2.2 Criar sub-módulo `workflows/whatsapp/` com `__init__.py`, `graph.py`, `state.py`
  - [x] 2.3 Criar `workflows/whatsapp/nodes/__init__.py` (diretório com __init__ vazio)
  - [x] 2.4 Criar `workflows/whatsapp/tools/__init__.py` (diretório com __init__ vazio)
  - [x] 2.5 Criar `workflows/whatsapp/prompts/__init__.py` (diretório com __init__ vazio)
  - [x] 2.6 Criar `workflows/services/__init__.py`
  - [x] 2.7 Criar `workflows/providers/__init__.py`
  - [x] 2.8 Criar `workflows/middleware/__init__.py`
  - [x] 2.9 Criar `workflows/utils/__init__.py`

- [x] Task 3: Implementar Django Models (AC: #3, #4, #5, #6)
  - [x] 3.1 Criar model `User` em `workflows/models.py` com Meta db_table="users"
  - [x] 3.2 Criar model `Message` com FK para User, Meta db_table="messages", indexes
  - [x] 3.3 Criar model `Config` com key unique, Meta db_table="configs"
  - [x] 3.4 Criar model `ConfigHistory` com FK para Config, Meta db_table="config_history"
  - [x] 3.5 Gerar e aplicar migrations (`python manage.py makemigrations workflows`)

- [x] Task 4: Implementar ConfigService básico (AC: #7)
  - [x] 4.1 Criar `workflows/services/config_service.py` com método async `get(key)`
  - [x] 4.2 Usar `Config.objects.aget(key=key)` — sem Redis cache nesta fase

- [x] Task 5: Data migration com configs iniciais (AC: #8)
  - [x] 5.1 Criar data migration em `workflows/migrations/` para popular 7 configs iniciais
  - [x] 5.2 Definir valores padrão sensatos para cada config key

- [x] Task 6: Registrar models no Django Admin (AC: #9)
  - [x] 6.1 Criar `workflows/admin.py` registrando User, Message, Config, ConfigHistory
  - [x] 6.2 Adicionar list_display, search_fields e list_filter relevantes

- [x] Task 7: Error hierarchy (AC: #10)
  - [x] 7.1 Criar `workflows/utils/errors.py` com AppError base e 5 subclasses
  - [x] 7.2 RateLimitError com `retry_after`, ExternalServiceError com `service`, GraphNodeError com `node`

- [x] Task 8: Configurar structlog com PII sanitization (AC: #11)
  - [x] 8.1 Criar `workflows/utils/sanitization.py` com processor `sanitize_pii`
  - [x] 8.2 Configurar structlog em `config/settings/base.py` com JSON rendering + sanitize_pii

- [x] Task 9: Docker setup (AC: #13, #14)
  - [x] 9.1 Criar `docker-compose.yml` com PostgreSQL 16 + Redis 7
  - [x] 9.2 Criar `Dockerfile` multi-stage com uv (builder → runtime)
  - [x] 9.3 Validar `docker build` passa com sucesso

- [x] Task 10: Criar estrutura de testes (AC: #17)
  - [x] 10.1 Criar `tests/__init__.py`, `tests/conftest.py` com fixtures Django
  - [x] 10.2 Criar diretórios de teste vazios: `test_whatsapp/`, `test_services/`, `test_providers/`
  - [x] 10.3 Validar `uv run pytest` roda sem erros

- [x] Task 11: Verificações finais (AC: #16, #17, #18)
  - [x] 11.1 Rodar `uv run ruff check .` e `uv run ruff format --check .` — corrigir se necessário
  - [x] 11.2 Rodar `uv run pytest` — confirmar que passa (32 testes passando)
  - [x] 11.3 Rodar `uv run python manage.py migrate` — todas as migrations passam no PostgreSQL 16
  - [x] 11.4 Rodar `docker build .` — imagem mb-wpp:dev criada com sucesso

## Dev Notes

### Contexto de Negócio

Esta é a **story fundacional** do projeto Medbrain WhatsApp (mb-wpp). É um tutor médico por WhatsApp para estudantes de medicina da Medway. O produto atual roda em n8n (116 nós) e está sendo migrado para código customizado via estratégia Strangler Fig.

**Tudo que vem depois depende desta story:**
- Story 1.2 (Webhook + Segurança) → precisa do projeto Django, models, structlog
- Story 1.3 (Identificação de Usuário) → precisa do model User, Django ORM async
- Story 1.4 (LLM Provider + Checkpointer) → precisa da estrutura de diretórios, providers/
- Story 1.5 (Formatação + Envio + Persistência) → precisa do model Message
- Story 1.6 (Debounce + Boas-vindas) → precisa do model Config, ConfigService
- Epic 2 Story 2.2 → precisa do Config para `blocked_competitors`
- Epic 4 Story 4.1 → precisa do Config para rate limits por tier
- Epic 8 Stories 8.1/8.2 → evoluem o Config/ConfigService criados aqui

### Decisões Arquiteturais Obrigatórias (ADRs)

| ADR | Decisão | Impacto nesta Story |
|-----|---------|---------------------|
| ADR-001 | Python 3.12+ | Runtime mínimo, type hints modernos |
| ADR-002 | Django 5.2 LTS + DRF + adrf | Framework web, Admin, API async |
| ADR-003 | Django ORM sobre Supabase PostgreSQL | supabase-py SOMENTE para Auth/Storage |
| ADR-004 | uv + pytest-django + Ruff + mypy strict | Toolchain completa |
| ADR-005 | GCP Cloud Run | Hosting alinhado com Vertex AI |
| ADR-009 | Estrutura com app `workflows/` | Convenção do time Medway |
| ADR-011 | Django Admin como UI Phase 1 | Admin para CostLog, User, Config |

### Padrões Obrigatórios

**Naming:**
- Tabelas DB: `snake_case` plural (`users`, `messages`, `configs`, `config_history`)
- Colunas DB: `snake_case` (`user_id`, `created_at`, `tokens_input`)
- Código Python: `snake_case` funções/variáveis, `PascalCase` classes
- Arquivos/módulos: `snake_case.py`
- Variáveis de ambiente: `UPPER_SNAKE_CASE` com prefixos de serviço (`VERTEX_`, `SUPABASE_`, `WHATSAPP_`)

**Código:**
- SEMPRE async/await para I/O (NUNCA I/O bloqueante)
- Django ORM async: `aget`, `acreate`, `afilter` (NUNCA versões sync)
- Type hints em TODAS as funções
- `structlog` para logging (NUNCA `print()`)
- `AppError` hierarchy para exceções
- Import order: Standard library → Third-party → Local
- NUNCA `import *`
- NUNCA sync I/O (`requests`, `psycopg2`) — somente async (`httpx`, Django async ORM)
- NUNCA commitar secrets no código
- NUNCA logar PII sem sanitização

### Estrutura Completa de Diretórios

```
mb-wpp/
├── pyproject.toml              # uv project config (PEP 621)
├── uv.lock                     # Lockfile com hashes
├── .env.example                # Template de variáveis de ambiente
├── .gitignore                  # Python/Django/uv gitignore
├── Dockerfile                  # Multi-stage build com uv
├── docker-compose.yml          # PostgreSQL 16 + Redis 7 local
├── manage.py                   # Django management
│
├── config/                     # Django project settings
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py             # Settings compartilhados (django-environ)
│   │   ├── development.py      # Dev overrides (DEBUG=True)
│   │   └── production.py       # Prod overrides (GCP)
│   ├── urls.py                 # Root URL configuration
│   ├── asgi.py                 # ASGI entry point (Uvicorn)
│   └── wsgi.py                 # WSGI fallback
│
├── workflows/                  # Main Django app
│   ├── __init__.py
│   ├── apps.py                 # AppConfig
│   ├── models.py               # User, Message, Config, ConfigHistory
│   ├── admin.py                # Django Admin registrations
│   ├── views.py                # (vazio nesta story)
│   ├── serializers.py          # (vazio nesta story)
│   ├── urls.py                 # (vazio nesta story)
│   ├── migrations/
│   │   └── __init__.py
│   │
│   ├── whatsapp/               # LangGraph workflow (estrutura apenas)
│   │   ├── __init__.py
│   │   ├── graph.py            # (vazio — implementado na Story 1.4)
│   │   ├── state.py            # (vazio — implementado na Story 1.4)
│   │   ├── nodes/
│   │   │   └── __init__.py
│   │   ├── tools/
│   │   │   └── __init__.py
│   │   └── prompts/
│   │       └── __init__.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   └── config_service.py   # ConfigService básico (get async)
│   │
│   ├── providers/
│   │   └── __init__.py
│   │
│   ├── middleware/
│   │   └── __init__.py
│   │
│   └── utils/
│       ├── __init__.py
│       ├── errors.py           # AppError hierarchy
│       └── sanitization.py     # PII sanitization processor
│
└── tests/
    ├── __init__.py
    ├── conftest.py             # Pytest fixtures (pytest-django)
    ├── test_whatsapp/
    │   └── __init__.py
    ├── test_services/
    │   └── __init__.py
    └── test_providers/
        └── __init__.py
```

### Dependências Principais (pyproject.toml)

```toml
[project]
name = "mb-wpp"
version = "0.1.0"
requires-python = ">=3.12"

dependencies = [
    "django>=5.2,<6.0",          # LTS até abril/2028
    "djangorestframework>=3.15",
    "adrf>=0.1",                  # Async DRF views
    "django-environ>=0.11",       # Variáveis de ambiente
    "django-cors-headers>=4.3",   # CORS
    "uvicorn>=0.32",              # ASGI server
    "structlog>=24.4",            # Structured logging
    "httpx>=0.28",                # HTTP client async
    "redis>=5.2",                 # Redis client async
    "pydantic>=2.10",             # Validação interna
    "langgraph>=1.0",             # Orquestração LLM
    "langchain>=1.0",             # Framework LLM
    "langchain-anthropic",        # ChatAnthropic
    "langchain-google-vertexai>=3.2", # ChatAnthropicVertex
    "langgraph-checkpoint-postgres>=3.0", # AsyncPostgresSaver
    "psycopg[binary]>=3.1",      # PostgreSQL driver async (para checkpointer)
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-django>=4.8",
    "pytest-asyncio>=0.24",
    "pytest-mock>=3.14",
    "pytest-cov",
    "ruff>=0.8",
    "mypy>=1.13",
    "django-stubs>=5.1",
]
```

### Configuração Django (base.py) — Referência

```python
import environ

env = environ.Env()
environ.Env.read_env()

DATABASES = {
    "default": env.db("DATABASE_URL"),
}

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "workflows",
]
```

### structlog — Referência de Configuração

```python
import structlog

def sanitize_pii(logger, method_name, event_dict):
    sensitive_fields = ["phone", "name", "email", "cpf", "api_key"]
    for field in sensitive_fields:
        if field in event_dict:
            event_dict[field] = "***REDACTED***"
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
        sanitize_pii,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)
```

### Error Hierarchy — Referência de Implementação

```python
class AppError(Exception):
    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

class ValidationError(AppError): ...
class AuthenticationError(AppError): ...

class RateLimitError(AppError):
    def __init__(self, message: str, retry_after: int, details: dict | None = None):
        super().__init__(message, details)
        self.retry_after = retry_after

class ExternalServiceError(AppError):
    def __init__(self, service: str, message: str, details: dict | None = None):
        super().__init__(f"{service}: {message}", details)
        self.service = service

class GraphNodeError(AppError):
    def __init__(self, node: str, message: str, details: dict | None = None):
        super().__init__(f"Node {node}: {message}", details)
        self.node = node
```

### ConfigService Básico — Referência

```python
from workflows.models import Config

class ConfigService:
    @staticmethod
    async def get(key: str):
        config = await Config.objects.aget(key=key)
        return config.value
```

### Docker — Referências

**docker-compose.yml:**
```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: mb_wpp
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports: ["5432:5432"]
    volumes: [postgres_data:/var/lib/postgresql/data]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

volumes:
  postgres_data:
```

**Dockerfile (multi-stage com uv):**
```dockerfile
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY manage.py ./
COPY config/ ./config/
COPY workflows/ ./workflows/

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/manage.py ./
COPY --from=builder /app/config ./config
COPY --from=builder /app/workflows ./workflows
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=config.settings.production
EXPOSE 8080
CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8080"]
```

### .env.example — Variáveis Necessárias

```env
# Django
SECRET_KEY=change-me-in-production
DJANGO_SETTINGS_MODULE=config.settings.development
DEBUG=True

# Database (Supabase PostgreSQL)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/mb_wpp

# Redis (Upstash ou local)
REDIS_URL=redis://localhost:6379

# WhatsApp Cloud API
WHATSAPP_WEBHOOK_SECRET=your-webhook-secret
WHATSAPP_VERIFY_TOKEN=your-verify-token
WHATSAPP_ACCESS_TOKEN=your-access-token
WHATSAPP_PHONE_NUMBER_ID=your-phone-number-id

# Anthropic (fallback LLM)
ANTHROPIC_API_KEY=your-anthropic-key

# GCP Vertex AI (primary LLM)
VERTEX_PROJECT_ID=your-gcp-project-id
VERTEX_LOCATION=us-east1

# Supabase (Auth + Storage only)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-key

# Logging
LOG_LEVEL=INFO
```

### Versões Atualizadas (Pesquisa Web — Março 2026)

| Tecnologia | Versão na Arquitetura | Versão Atual | Recomendação |
|------------|----------------------|--------------|--------------|
| Django | 5.1+ | **5.2.12 LTS** | Usar 5.2 LTS (5.1 é EOL desde dez/2025) |
| uv | 0.5+ | **0.10.8** | Usar >=0.5 no range |
| LangGraph | 1.0+ | **1.0 estável** | Manter >=1.0 |
| langgraph-checkpoint-postgres | Latest | **3.0.4** | Usar >=3.0 |
| langchain-google-vertexai | Latest | **3.2.2** | Usar >=3.2 |

**ALERTA CRÍTICO:** Django 5.1 atingiu end-of-life em dezembro/2025. A arquitetura diz "5.1+" então **usar Django 5.2 LTS** (suporte garantido até abril/2028).

### Data Migration — Valores Iniciais das Configs

| Key | Valor Sugerido | Usado por |
|-----|---------------|-----------|
| `rate_limit:free` | `{"requests_per_hour": 10, "tokens_per_day": 50000}` | Epic 4 (Rate Limiting) |
| `rate_limit:premium` | `{"requests_per_hour": 60, "tokens_per_day": 500000}` | Epic 4 (Rate Limiting) |
| `blocked_competitors` | `["chatgpt", "gemini", "copilot"]` | Story 2.2 (Web Search) |
| `message:welcome` | `"Olá! 👋 Sou o Medbrain..."` | Story 1.6 (Boas-vindas) |
| `message:rate_limit` | `"Você atingiu o limite..."` | Story 1.6 / Epic 4 |
| `message:unsupported_type` | `"Desculpe, ainda não..."` | Story 1.6 (Tipo não suportado) |
| `debounce_ttl` | `3` (segundos) | Story 1.6 (Debounce) |

### Project Structure Notes

- Estrutura alinhada 100% com o documento de arquitetura (~55 arquivos mapeados)
- App `workflows/` segue convenção do time Medway
- Sub-módulos `whatsapp/nodes/`, `whatsapp/tools/`, `whatsapp/prompts/` criados vazios — preenchidos nas Stories 1.2-1.6
- `providers/` criado vazio — preenchido nas Stories 1.4 (LLM, Checkpointer) e posteriores
- Schema `langgraph` no PostgreSQL NÃO é gerenciado por Django migrations — criado via `checkpointer.setup()` na Story 1.4

### References

- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-001 a ADR-011]
- [Source: _bmad-output/planning-artifacts/architecture.md — Seção 4: Source Tree]
- [Source: _bmad-output/planning-artifacts/architecture.md — Seção 5: Django Models]
- [Source: _bmad-output/planning-artifacts/architecture.md — Seção 7: structlog + PII]
- [Source: _bmad-output/planning-artifacts/architecture.md — Seção 8: Error Hierarchy]
- [Source: _bmad-output/planning-artifacts/architecture.md — Seção 9: Dockerfile + docker-compose]
- [Source: _bmad-output/planning-artifacts/architecture.md — Seção 10: pyproject.toml]
- [Source: _bmad-output/planning-artifacts/epics.md — Epic 1, Story 1.1]
- [Source: _bmad-output/planning-artifacts/prd.md — NFR15-NFR20 (Segurança/LGPD)]
- [Source: _bmad-output/planning-artifacts/prd.md — Seção de Stack Técnica]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Implementation Plan

- Criação bottom-up: pyproject.toml → uv sync → estrutura Django → app workflows → models → services → admin → errors → structlog → Docker → testes
- Testes usam SQLite in-memory via `config/settings/test.py` (PostgreSQL requer Docker)
- Ruff configurado para excluir `search-medway-langgraph` (projeto de referência) e migrations auto-geradas

### Completion Notes List

- Story 1.1 é a primeira story — sem story anterior para contexto de aprendizado
- Projeto não é um repositório git ainda — sem git intelligence disponível
- Django 5.1 atualizado para 5.2 LTS (end-of-life detectado via pesquisa web)
- Ultimate context engine analysis completed — comprehensive developer guide created
- ✅ Todas as 11 Tasks implementadas com sucesso
- ✅ 32 testes passando (models, errors, sanitization, config_service)
- ✅ `uv run ruff check .` e `uv run ruff format --check .` passam sem erros
- ✅ `uv run pytest` — 32 passed em 0.12s
- ✅ `docker build .` — imagem mb-wpp:dev criada com sucesso (multi-stage com uv)
- ✅ `manage.py migrate` — todas as migrations passam no PostgreSQL 16 (Docker)
- Adicionado `config/settings/test.py` com SQLite in-memory para testes unitários rápidos

### File List

**Novos arquivos criados:**

- `pyproject.toml` — Configuração do projeto, dependências, Ruff, mypy, pytest
- `uv.lock` — Lockfile gerado por `uv sync`
- `manage.py` — Django management command
- `.env.example` — Template de variáveis de ambiente
- `.env` — Variáveis de ambiente local (não commitado)
- `.gitignore` — Git ignore para Python/Django/uv
- `Dockerfile` — Multi-stage build com uv
- `docker-compose.yml` — PostgreSQL 16 + Redis 7
- `config/__init__.py`
- `config/urls.py` — Root URL configuration
- `config/asgi.py` — ASGI entry point
- `config/wsgi.py` — WSGI fallback
- `config/settings/__init__.py`
- `config/settings/base.py` — Settings base com django-environ
- `config/settings/development.py` — Dev overrides (DEBUG=True, CORS permissivo)
- `config/settings/production.py` — Prod overrides (segurança, HSTS, validação SECRET_KEY)
- `config/settings/test.py` — Test settings com SQLite in-memory
- `workflows/__init__.py`
- `workflows/apps.py` — AppConfig
- `workflows/models.py` — User, Message, Config, ConfigHistory
- `workflows/admin.py` — Django Admin registrations
- `workflows/views.py` — (vazio — placeholder)
- `workflows/serializers.py` — (vazio — placeholder)
- `workflows/urls.py` — (vazio — placeholder)
- `workflows/migrations/__init__.py`
- `workflows/migrations/0001_initial.py` — Schema migration (auto-gerada)
- `workflows/migrations/0002_initial_configs.py` — Data migration com 7 configs
- `workflows/services/__init__.py`
- `workflows/services/config_service.py` — ConfigService básico (async get)
- `workflows/providers/__init__.py`
- `workflows/middleware/__init__.py`
- `workflows/utils/__init__.py`
- `workflows/utils/errors.py` — AppError hierarchy (5 subclasses)
- `workflows/utils/sanitization.py` — PII sanitization processor (recursivo)
- `workflows/whatsapp/__init__.py`
- `workflows/whatsapp/graph.py` — (vazio — Story 1.4)
- `workflows/whatsapp/state.py` — (vazio — Story 1.4)
- `workflows/whatsapp/nodes/__init__.py`
- `workflows/whatsapp/tools/__init__.py`
- `workflows/whatsapp/prompts/__init__.py`
- `tests/__init__.py`
- `tests/conftest.py` — Pytest conftest (vazio)
- `tests/test_models.py` — 16 testes de models
- `tests/test_errors.py` — 7 testes de error hierarchy
- `tests/test_sanitization.py` — 9 testes de PII sanitization (inclui recursivo)
- `tests/test_services/__init__.py`
- `tests/test_services/test_config_service.py` — 2 testes async de ConfigService
- `tests/test_whatsapp/__init__.py`
- `tests/test_providers/__init__.py`

## Change Log

- 2026-03-06: Implementação completa da Story 1.1 — projeto Django 5.2 LTS inicializado com uv, app workflows criada com estrutura completa, 4 models implementados (User, Message, Config, ConfigHistory), ConfigService básico async, data migration com 7 configs iniciais, Django Admin, error hierarchy (AppError + 5 subclasses), structlog com PII sanitization, Docker setup (Dockerfile + docker-compose.yml), 32 testes passando, lint/format OK
- 2026-03-06: **Code Review (AI)** — 10 issues encontrados (2 HIGH, 4 MEDIUM, 4 LOW). 7 corrigidos automaticamente:
  - [H1] SECRET_KEY: validação em production.py impede uso de default inseguro
  - [H2] sanitize_pii: sanitização recursiva para dicts/listas aninhados (LGPD)
  - [M1] Criados workflows/views.py, serializers.py, urls.py (placeholders faltantes)
  - [M2] structlog config movido de base.py para WorkflowsConfig.ready() (elimina dependência frágil)
  - [M3] ConfigService.get() agora lança ValidationError em vez de Config.DoesNotExist
  - [M4] Dockerfile com collectstatic para Django Admin em produção
  - [L1] Fixture user_data não usada removida de conftest.py
  - 34 testes passando (2 novos), lint/format OK
