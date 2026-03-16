# Guia Completo: Setup WhatsApp Business API para Testes Reais

**Projeto:** mb-wpp (Medbrain WhatsApp)
**Data:** 2026-03-12
**Autor:** Equipe Medbrain
**Objetivo:** Configurar a WhatsApp Cloud API para testes end-to-end reais do pipeline completo

---

## Índice

1. [Visão Geral — O Que Vamos Configurar](#1-visão-geral)
2. [Pré-Requisitos](#2-pré-requisitos)
3. [Passo 1: Criar Conta Meta Developer](#3-passo-1-conta-meta-developer)
4. [Passo 2: Criar App no Meta for Developers](#4-passo-2-criar-app)
5. [Passo 3: Configurar WhatsApp Business API](#5-passo-3-whatsapp-business-api)
6. [Passo 4: Obter Credenciais](#6-passo-4-credenciais)
7. [Passo 5: Configurar Webhook (ngrok para Dev Local)](#7-passo-5-webhook)
8. [Passo 6: Preencher o .env](#8-passo-6-env)
9. [Passo 7: Configurar Demais Serviços](#9-passo-7-demais-serviços)
10. [Passo 8: Executar o Servidor e Testar](#10-passo-8-executar)
11. [Passo 9: Roteiro de Testes E2E](#11-passo-9-roteiro)
12. [Troubleshooting](#12-troubleshooting)
13. [Custos e Limites](#13-custos)
14. [Segurança](#14-segurança)

---

## 1. Visão Geral

O Medbrain WhatsApp usa a **WhatsApp Cloud API** (hospedada pela Meta) para receber e enviar mensagens. A arquitetura é:

```
Aluno (WhatsApp) → Meta Cloud → Webhook (nosso servidor) → Django → LangGraph → LLM → Resposta → WhatsApp
```

Para testes reais, precisamos:

| Componente | O que é | Onde configurar |
|-----------|---------|-----------------|
| **Meta Developer App** | Container da API | developers.facebook.com |
| **WhatsApp Business Account** | Conta comercial | Criada automaticamente com o app |
| **Test Phone Number** | Número de teste da Meta | Painel do app (gratuito) |
| **Webhook URL** | Nosso endpoint público | ngrok (dev) ou Cloud Run (prod) |
| **Access Token** | Token de autenticação | Painel do app |
| **Webhook Secret** | Chave HMAC para validação | Painel do app |

**Endpoint do nosso webhook:** `POST /webhook/whatsapp/`
**Verificação do webhook:** `GET /webhook/whatsapp/` (handshake Meta)

---

## 2. Pré-Requisitos

### 2.1 Contas Necessárias

- [ ] **Conta pessoal no Facebook** — necessária para acessar Meta for Developers
- [ ] **Conta Meta for Developers** — developers.facebook.com (gratuita)
- [ ] **Telefone pessoal com WhatsApp** — para receber mensagens de teste

### 2.2 Ferramentas Locais

- [ ] **Python 3.12+** com `uv` instalado
- [ ] **PostgreSQL** rodando localmente (ou acesso ao Supabase)
- [ ] **Redis** rodando localmente (ou Upstash)
- [ ] **ngrok** instalado — para expor o servidor local à internet

```bash
# Instalar ngrok (macOS)
brew install ngrok

# Criar conta gratuita em ngrok.com e autenticar
ngrok config add-authtoken YOUR_NGROK_TOKEN
```

### 2.3 Credenciais de Serviços Externos (já no .env.example)

Para teste completo do pipeline, você precisa de:

| Serviço | Variável | Obrigatório? | Custo |
|---------|----------|-------------|-------|
| GCP Vertex AI | `VERTEX_PROJECT_ID`, `GCP_CREDENTIALS` | Sim (primary LLM) | Pay-per-use |
| Anthropic | `ANTHROPIC_API_KEY` | Sim (fallback LLM) | Pay-per-use |
| Pinecone | `PINECONE_API_KEY` | Sim (RAG médico) | Free tier disponível |
| Tavily | `TAVILY_API_KEY` | Sim (web search) | Free tier: 1000 req/mês |
| OpenAI | `OPENAI_API_KEY` | Sim (Whisper áudio) | Pay-per-use |
| NCBI | `NCBI_API_KEY`, `NCBI_EMAIL` | Opcional | Gratuito |
| PharmaDB | `PHARMADB_API_KEY` | Opcional | Pago |
| Bulário | `BULARIO_API_URL` | Opcional | Gratuito |

---

## 3. Passo 1: Criar Conta Meta Developer

1. Acesse **https://developers.facebook.com/**
2. Clique em **"Começar"** / **"Get Started"**
3. Faça login com sua conta do Facebook
4. Aceite os termos de desenvolvedor
5. Verifique sua conta (pode pedir número de telefone)

**Resultado:** Você terá acesso ao painel de desenvolvedor da Meta.

---

## 4. Passo 2: Criar App no Meta for Developers

1. No painel, clique em **"Criar App"** / **"Create App"**
2. Selecione o tipo: **"Business"** (Negócios)
3. Preencha:
   - **Nome do App:** `Medbrain WhatsApp Dev` (ou similar — é apenas para identificação)
   - **E-mail:** seu e-mail de desenvolvedor
   - **Business Portfolio:** pode criar um novo ou selecionar existente
4. Clique em **"Criar App"**

**Resultado:** Um App ID será gerado. Você verá o dashboard do app.

---

## 5. Passo 3: Configurar WhatsApp Business API

### 5.1 Adicionar Produto WhatsApp

1. No dashboard do app, vá em **"Adicionar Produtos"** / **"Add Products"**
2. Encontre **"WhatsApp"** e clique em **"Configurar"** / **"Set Up"**
3. A Meta criará automaticamente:
   - Uma **WhatsApp Business Account** de teste
   - Um **número de telefone de teste** (formato: +1 555-xxx-xxxx)

### 5.2 Identificar Seu Número de Teste

1. No menu lateral, vá em **WhatsApp → Início** / **Getting Started**
2. Você verá:
   - **Phone number ID** — copie esse valor (ex: `123456789012345`)
   - **WhatsApp Business Account ID** — para referência
   - **Test phone number** — o número fictício que a Meta fornece

### 5.3 Adicionar Número Destinatário

Para enviar mensagens de teste, você precisa registrar seu número pessoal:

1. Em **WhatsApp → Início**, seção **"Send and receive messages"**
2. No campo **"To"**, clique em **"Manage phone number list"**
3. Adicione seu número pessoal (com código do país: `+55 11 99999-9999`)
4. Você receberá um SMS/WhatsApp com código de verificação — insira-o

**Importante:** No modo de teste, você só pode enviar mensagens para números verificados (máx 5).

### 5.4 Testar Envio Básico (Opcional)

Ainda no painel **Getting Started**, você pode testar o envio:

1. Selecione o número de teste como **"From"**
2. Selecione seu número como **"To"**
3. Clique em **"Send Message"**
4. Verifique se recebeu a mensagem "Hello World" no seu WhatsApp

Se funcionou, a API está ativa.

---

## 6. Passo 4: Obter Credenciais

### 6.1 Temporary Access Token (para desenvolvimento)

1. Em **WhatsApp → Início** / **Getting Started**
2. Copie o **"Temporary access token"**
3. **ATENÇÃO:** Esse token expira em **24 horas**

Este é o valor para `WHATSAPP_ACCESS_TOKEN` no `.env`.

### 6.2 Permanent Access Token (para produção — recomendado)

Para um token que não expira:

1. Vá em **Configurações do App → Básico** / **App Settings → Basic**
2. Copie o **App Secret** (será usado como `WHATSAPP_WEBHOOK_SECRET`)
3. Vá em **Ferramentas → Tokens de Acesso** ou use o **Graph API Explorer**:
   - Selecione seu App
   - Selecione permissões: `whatsapp_business_messaging`, `whatsapp_business_management`
   - Gere o token
   - Clique em **"Extend Access Token"** para obter um token de longa duração
4. Para token permanente (System User Token):
   - Vá em **Business Settings** → **System Users**
   - Crie um System User (tipo Admin)
   - Gere um token com permissões `whatsapp_business_messaging`
   - Este token **não expira**

### 6.3 App Secret (Webhook Signature)

1. Vá em **Configurações do App → Básico** / **App Settings → Basic**
2. Copie o **App Secret**
3. Este é o valor para `WHATSAPP_WEBHOOK_SECRET` no `.env`
4. Nosso middleware (`WebhookSignatureMiddleware`) valida o header `X-Hub-Signature-256` usando HMAC SHA-256 com este secret

### 6.4 Verify Token (Webhook Handshake)

Este é um token que **você inventa** — qualquer string aleatória:

```bash
# Gerar um verify token aleatório
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Este é o valor para `WHATSAPP_VERIFY_TOKEN` no `.env`. Você vai usar esse mesmo valor ao configurar o webhook na Meta.

---

## 7. Passo 5: Configurar Webhook (ngrok para Dev Local)

### 7.1 Iniciar o Servidor Django

```bash
cd /Users/rcfranco/mb-wpp

# Instalar dependências
uv sync

# Rodar migrations
uv run python manage.py migrate

# Iniciar servidor na porta 8000
uv run python manage.py runserver 0.0.0.0:8000
```

### 7.2 Expor com ngrok

Em outro terminal:

```bash
ngrok http 8000
```

O ngrok mostrará algo como:

```
Forwarding  https://abc123.ngrok-free.app → http://localhost:8000
```

Copie a URL HTTPS (ex: `https://abc123.ngrok-free.app`).

**Importante:** Cada vez que reiniciar o ngrok, a URL muda (plano gratuito). Você precisará atualizar no painel da Meta.

### 7.3 Configurar ALLOWED_HOSTS

Antes de testar, adicione o host do ngrok ao Django. No arquivo `config/settings/development.py`, verifique que `ALLOWED_HOSTS` inclui o domínio ngrok:

```python
ALLOWED_HOSTS = ["*"]  # OK para desenvolvimento
```

### 7.4 Registrar Webhook na Meta

1. No painel do app, vá em **WhatsApp → Configuração** / **Configuration**
2. Na seção **Webhook**, clique em **"Editar"** / **"Edit"**
3. Preencha:
   - **Callback URL:** `https://abc123.ngrok-free.app/webhook/whatsapp/`
   - **Verify Token:** o mesmo valor que você colocou em `WHATSAPP_VERIFY_TOKEN` no `.env`
4. Clique em **"Verificar e salvar"** / **"Verify and Save"**

A Meta fará um `GET` para a URL com `hub.mode=subscribe`, `hub.verify_token=seu-token`, `hub.challenge=...`. Nosso endpoint responde com o challenge se o token bater.

**Se a verificação falhar:**
- Verifique que o servidor Django está rodando
- Verifique que o ngrok está ativo
- Verifique que o verify token no `.env` é o mesmo do painel
- Verifique os logs do Django para erros

### 7.5 Inscrever nos Campos de Webhook

Após verificar o webhook, você precisa se inscrever nos eventos:

1. Na seção **Webhook fields**, clique em **"Manage"**
2. Marque **"messages"** — isso é o que dispara nosso endpoint quando alguém envia mensagem
3. Salve

---

## 8. Passo 6: Preencher o .env

Copie o `.env.example` e preencha com as credenciais reais:

```bash
cp .env.example .env
```

Edite o `.env`:

```bash
# Django
SECRET_KEY=uma-chave-secreta-qualquer
DJANGO_SETTINGS_MODULE=config.settings.development
DEBUG=True

# Database (Supabase PostgreSQL)
DATABASE_URL=postgresql://postgres:SUA_SENHA@db.SEU_PROJETO.supabase.co:5432/postgres
# OU local:
# DATABASE_URL=postgresql://postgres:postgres@localhost:5432/mb_wpp

# Redis
REDIS_URL=redis://localhost:6379
# OU Upstash:
# REDIS_URL=rediss://default:SUA_SENHA@SEU_HOST.upstash.io:6379

# ===== WhatsApp Cloud API (Passo 4) =====
WHATSAPP_WEBHOOK_SECRET=SEU_APP_SECRET_DO_PASSO_6.3
WHATSAPP_VERIFY_TOKEN=SEU_VERIFY_TOKEN_DO_PASSO_6.4
WHATSAPP_ACCESS_TOKEN=SEU_ACCESS_TOKEN_DO_PASSO_6.1_OU_6.2
WHATSAPP_PHONE_NUMBER_ID=SEU_PHONE_NUMBER_ID_DO_PASSO_5.2
WHATSAPP_API_VERSION=v21.0

# ===== LLM Providers =====
# GCP Vertex AI (primary) — precisa de service account com Vertex AI API habilitada
VERTEX_PROJECT_ID=seu-gcp-project-id
VERTEX_LOCATION=us-east5
GCP_CREDENTIALS={"type":"service_account","project_id":"...","private_key":"..."}

# Anthropic Direct (fallback)
ANTHROPIC_API_KEY=sk-ant-api03-...

# ===== Tools Médicas =====
# Pinecone (RAG)
PINECONE_API_KEY=pcsk_...
PINECONE_ASSISTANT_NAME=medbrain

# Tavily (Web Search)
TAVILY_API_KEY=tvly-...

# PubMed (Verificação de Artigos)
NCBI_API_KEY=          # Opcional mas recomendado
NCBI_EMAIL=seu@email.com

# PharmaDB (Bulas — primary, opcional)
PHARMADB_API_KEY=

# Bulário (Bulas — fallback, opcional)
BULARIO_API_URL=

# OpenAI (Whisper — Áudio)
OPENAI_API_KEY=sk-...

# Logging
LOG_LEVEL=DEBUG
```

**Dica:** Use `LOG_LEVEL=DEBUG` durante os testes para ver todos os logs do pipeline.

---

## 9. Passo 7: Configurar Demais Serviços

### 9.1 GCP Vertex AI

1. Acesse **console.cloud.google.com**
2. Crie ou selecione um projeto
3. Habilite a **Vertex AI API**: `APIs & Services → Enable APIs → Vertex AI API`
4. Habilite o **Model Garden**: precisa aceitar os termos do Claude no Vertex AI
5. Crie uma **Service Account**:
   - IAM → Service Accounts → Create
   - Role: `Vertex AI User`
   - Gere uma chave JSON
6. Copie o conteúdo JSON inteiro para `GCP_CREDENTIALS` no `.env`

**Modelo usado:** `claude-sonnet-4@20250514` (configurado em `workflows/providers/llm.py`)
**Região:** `us-east5` (default, onde Claude está disponível)

### 9.2 Anthropic Direct API

1. Acesse **console.anthropic.com**
2. Crie uma API Key
3. Copie para `ANTHROPIC_API_KEY`

**Modelo usado:** `claude-sonnet-4-20250514` (fallback)

### 9.3 Pinecone

1. Acesse **app.pinecone.io**
2. Crie uma conta (free tier disponível)
3. Crie um **Assistant** chamado `medbrain` (mesmo nome que `PINECONE_ASSISTANT_NAME`)
4. Faça upload da base de conhecimento médico para o Assistant
5. Copie a API Key para `PINECONE_API_KEY`

### 9.4 Tavily

1. Acesse **app.tavily.com**
2. Crie uma conta (free tier: 1000 req/mês)
3. Copie a API Key para `TAVILY_API_KEY`

### 9.5 OpenAI (Whisper)

1. Acesse **platform.openai.com**
2. Crie uma API Key
3. Copie para `OPENAI_API_KEY`

### 9.6 PostgreSQL + Redis

**Opção A — Local:**
```bash
# PostgreSQL
brew install postgresql@15
brew services start postgresql@15
createdb mb_wpp

# Redis
brew install redis
brew services start redis
```

**Opção B — Cloud (Supabase + Upstash):**
- PostgreSQL: Use a connection string do Supabase (Settings → Database → URI)
- Redis: Use a connection string do Upstash

---

## 10. Passo 8: Executar o Servidor e Testar

### 10.1 Setup Inicial

```bash
cd /Users/rcfranco/mb-wpp

# Instalar dependências
uv sync

# Rodar migrations (inclui data migrations para Config)
uv run python manage.py migrate

# Verificar que tudo carrega sem erros
uv run python manage.py check
```

### 10.2 Iniciar o Servidor

```bash
# Terminal 1: Django
uv run python manage.py runserver 0.0.0.0:8000

# Terminal 2: ngrok
ngrok http 8000
```

### 10.3 Verificar Webhook (Handshake)

Depois de configurar o webhook na Meta (Passo 5), verifique nos logs do Django:

```
webhook_verification_success
```

Se aparecer `webhook_verification_failed`, verifique o `WHATSAPP_VERIFY_TOKEN`.

### 10.4 Enviar Primeira Mensagem de Teste

1. No seu WhatsApp pessoal, procure o número de teste da Meta
2. Envie uma mensagem simples: **"Olá"**
3. Observe os logs do Django — você deve ver:

```
graph_execution_started  message_id=wamid.xxx  phone=5511999999999  message_type=text
graph_execution_completed  message_id=wamid.xxx  phone=5511999999999
whatsapp_message_sent  phone=5511999999999  wamid=wamid.yyy
```

4. Verifique se recebeu a resposta do Medbrain no WhatsApp

---

## 11. Passo 9: Roteiro de Testes E2E

### Teste 1: Mensagem de Texto Simples
**Enviar:** "Olá, bom dia!"
**Esperado:** Resposta de boas-vindas ou saudação do LLM
**Verifica:** Pipeline texto completo (webhook → identify_user → rate_limit → load_context → orchestrate_llm → send_whatsapp)

### Teste 2: Pergunta Médica (RAG)
**Enviar:** "Qual o tratamento para insuficiência cardíaca?"
**Esperado:** Resposta com citações `[1]`, `[2]` da base Pinecone
**Verifica:** Tool RAG (`rag_medical`), sistema de citações, collect_sources

### Teste 3: Pergunta com Busca Web
**Enviar:** "Quais as últimas diretrizes de 2026 para tratamento de diabetes tipo 2?"
**Esperado:** Resposta com citações `[W-1]`, `[W-2]` de fontes web
**Verifica:** Tool `web_search` (Tavily), citações web, bloqueio de concorrentes

### Teste 4: Verificação de Artigo
**Enviar:** "Esse artigo é real? PMID 12345678"
**Esperado:** Verificação do artigo via PubMed
**Verifica:** Tool `verify_paper` (NCBI E-utilities)

### Teste 5: Calculadora Médica
**Enviar:** "Calcule o IMC de um paciente com 80kg e 1.75m"
**Esperado:** Resultado da calculadora de IMC (26.12 kg/m²)
**Verifica:** Tool `medical_calculator`

### Teste 6: Bula de Medicamento
**Enviar:** "Qual a posologia da amoxicilina?"
**Esperado:** Informações da bula
**Verifica:** Tool `drug_lookup` (PharmaDB/Bulário)

### Teste 7: Mensagem de Áudio
**Enviar:** Um áudio curto perguntando algo médico (gravar no WhatsApp)
**Esperado:** Transcrição + resposta relevante
**Verifica:** Download de mídia, Whisper (OpenAI), process_media node

### Teste 8: Imagem de Questão Médica
**Enviar:** Uma foto de uma questão médica (prova, simulado)
**Esperado:** Análise da questão com comentários
**Verifica:** Download de mídia, Claude Vision, process_media node

### Teste 9: Mensagem Não Suportada
**Enviar:** Um sticker ou localização
**Esperado:** "Desculpe, no momento só consigo processar mensagens de texto, áudio e imagem."
**Verifica:** Tratamento de tipos não suportados

### Teste 10: Rate Limiting
**Enviar:** Muitas mensagens em sequência rápida (>10 em poucos segundos)
**Esperado:** Mensagem de rate limit após atingir o limite
**Verifica:** Sliding window + token bucket, mensagem amigável

### Teste 11: Debounce
**Enviar:** 3-4 mensagens curtas em menos de 2 segundos ("Olá" "tudo" "bem?")
**Esperado:** Uma única resposta consolidada (não 3 respostas separadas)
**Verifica:** Mecanismo de debounce

### Checklist de Validação

| # | Teste | Resultado | Notas |
|---|-------|-----------|-------|
| 1 | Texto simples | ☐ Pass ☐ Fail | |
| 2 | RAG + citações | ☐ Pass ☐ Fail | |
| 3 | Web search + citações | ☐ Pass ☐ Fail | |
| 4 | Verificação artigo | ☐ Pass ☐ Fail | |
| 5 | Calculadora médica | ☐ Pass ☐ Fail | |
| 6 | Bula medicamento | ☐ Pass ☐ Fail | |
| 7 | Áudio (Whisper) | ☐ Pass ☐ Fail | |
| 8 | Imagem (Vision) | ☐ Pass ☐ Fail | |
| 9 | Tipo não suportado | ☐ Pass ☐ Fail | |
| 10 | Rate limiting | ☐ Pass ☐ Fail | |
| 11 | Debounce | ☐ Pass ☐ Fail | |

---

## 12. Troubleshooting

### Webhook não verifica

| Sintoma | Causa Provável | Solução |
|---------|---------------|---------|
| Timeout na verificação | ngrok não está rodando | Iniciar ngrok |
| 403 no handshake | Verify token errado | Conferir `WHATSAPP_VERIFY_TOKEN` no `.env` e no painel Meta |
| 401 no POST | App Secret errado | Conferir `WHATSAPP_WEBHOOK_SECRET` |

### Mensagem enviada mas sem resposta

| Sintoma | Causa Provável | Solução |
|---------|---------------|---------|
| `graph_node_error node=identify_user` | PostgreSQL não acessível | Verificar `DATABASE_URL` |
| `graph_node_error node=orchestrate_llm` | LLM não acessível | Verificar `VERTEX_PROJECT_ID` ou `ANTHROPIC_API_KEY` |
| `ExternalServiceError service=whatsapp` | Token expirado | Gerar novo access token no painel Meta |
| Nenhum log aparece | Webhook não configurado | Verificar que inscreveu no campo "messages" |

### Mídia (áudio/imagem) não funciona

| Sintoma | Causa Provável | Solução |
|---------|---------------|---------|
| `media download failed` | Token sem permissão | Verificar permissões do access token |
| `Whisper transcription failed` | OpenAI key inválida | Verificar `OPENAI_API_KEY` |
| `Vision analysis failed` | Vertex AI sem acesso a Claude | Verificar Model Garden |

### Rate Limit / Debounce

| Sintoma | Causa Provável | Solução |
|---------|---------------|---------|
| Todas as mensagens rate limited | Redis não acessível | Verificar `REDIS_URL` |
| Debounce não consolida | Redis connection timeout | Verificar conectividade Redis |

---

## 13. Custos e Limites

### WhatsApp Cloud API (Meta)

- **Número de teste:** Gratuito, mas limitado a **5 destinatários verificados**
- **Mensagens de teste:** Até **250 conversas/24h** no modo de desenvolvimento
- **Template messages:** Necessárias para iniciar conversa (a Meta fornece templates de teste)
- **Sessão de conversa:** Após o aluno enviar a primeira mensagem, você tem **24 horas** para responder sem custo adicional

### Estimativa de Custo por Teste

| Serviço | Custo estimado por pergunta |
|---------|---------------------------|
| Claude Sonnet 4 (Vertex AI) | ~$0.01-0.05 |
| Whisper (áudio 30s) | ~$0.006 |
| Pinecone (query) | Incluso no free tier |
| Tavily (web search) | Incluso no free tier (1000/mês) |
| PubMed | Gratuito |

**Custo total estimado para 11 testes:** < $1.00

---

## 14. Segurança

### O Que NÃO Fazer

- **NUNCA** commitar o `.env` no git (já está no `.gitignore`)
- **NUNCA** compartilhar o Access Token publicamente
- **NUNCA** usar o App Secret como verify token (são coisas diferentes)
- **NUNCA** desabilitar a validação de assinatura do webhook em produção

### O Que o Projeto Já Faz

- **WebhookSignatureMiddleware:** Valida HMAC SHA-256 em todo POST para `/webhook/`
- **PII Sanitization:** Números de telefone são redacted nos logs via `sanitize_pii`
- **Token no header:** Access token enviado via `Authorization: Bearer` (HTTPS obrigatório)

### Rotação de Credenciais

Se o Access Token temporário expirar (24h):

1. Vá em **WhatsApp → Getting Started** no painel Meta
2. Gere um novo token temporário
3. Atualize `WHATSAPP_ACCESS_TOKEN` no `.env`
4. Reinicie o servidor Django (o httpx client é recreado com novo token)

---

## Referências

- [WhatsApp Cloud API — Documentação Oficial](https://developers.facebook.com/docs/whatsapp/cloud-api)
- [Getting Started (Meta)](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started)
- [Webhooks Setup](https://developers.facebook.com/docs/whatsapp/cloud-api/guides/set-up-webhooks)
- [System User Access Tokens](https://developers.facebook.com/docs/whatsapp/business-management-api/get-started#system-user-access-tokens)
- [Pricing](https://developers.facebook.com/docs/whatsapp/pricing)

---

## Arquivos Relevantes no Projeto

| Arquivo | Papel |
|---------|-------|
| `workflows/views.py` | Webhook endpoint (GET verify + POST messages) |
| `workflows/middleware/webhook_signature.py` | Validação HMAC SHA-256 |
| `workflows/providers/whatsapp.py` | Client WhatsApp (send_text_message, download_media, mark_as_read) |
| `workflows/whatsapp/graph.py` | StateGraph do LangGraph (pipeline completo) |
| `workflows/providers/llm.py` | Factory LLM (Vertex AI + Anthropic fallback) |
| `config/settings/base.py` | Todas as variáveis de ambiente |
| `.env.example` | Template com todas as variáveis necessárias |

---

*Gerado como parte do Prep Sprint (Fase 2) — Retrospectiva Epic 3+5, 2026-03-12*
