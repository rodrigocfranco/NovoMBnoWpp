---
stepsCompleted:
  - step-01-init
  - step-02-discovery
  - step-03-success
  - step-04-journeys
  - step-05-domain
  - step-06-innovation-skipped
  - step-07-project-type
  - step-08-scoping
  - step-09-functional
  - step-10-nonfunctional
  - step-11-polish
  - step-12-complete
inputDocuments:
  - product-brief-mb-wpp-2026-02-11.md
  - technical-arquitetura-ideal-medbrain-whatsapp-research-2026-02-10.md
  - claude-sdk-tool-use-architecture-research-2026-02-10.md
documentCounts:
  briefs: 1
  research: 2
  brainstorming: 0
  projectDocs: 0
classification:
  projectType: api_backend
  domain: healthcare_edtech
  complexity: high
  projectContext: brownfield
workflowType: 'prd'
date: 2026-02-12
author: Rodrigo Franco
project_name: mb-wpp
---

# Product Requirements Document - mb-wpp

**Author:** Rodrigo Franco
**Date:** 2026-02-12

## Resumo Executivo

**Produto:** Medbrain WhatsApp (mb-wpp) — tutor médico por WhatsApp para estudantes de medicina.

**Diferenciador:** Respostas médicas com citações de fontes verificáveis (base de conhecimento curada por professores Medway + diretrizes brasileiras). Enquanto o ChatGPT responde sem fontes, o Medbrain cita Harrison, diretrizes da SBC e materiais Medway.

**Personas:**
- **Aluno Medway** — estudante de medicina assinante, usa para dúvidas de estudo e apoio no internato
- **Não-Aluno** — profissional ou estudante não assinante, usa para consultas rápidas
- **Equipe Medway** — monitora métricas, custos e qualidade; apresenta dados para a diretoria

**Contexto:** Produto em operação via n8n (116 nodes). Esta PRD define a migração para código próprio usando Claude SDK com arquitetura Tool Use — mantendo paridade funcional + resolução das dores atuais (latência, rate limiting imprevisível, formatação, erros silenciosos).

**North Star Metric:** Taxa de satisfação (👍/👎) > 85%

## Critérios de Sucesso

### Sucesso do Usuário

**North Star Metric:** Taxa de satisfação (👍/👎) > 85%
- Funciona como termômetro composto: se o aluno dá 👍, o serviço respondeu, em tempo aceitável, com qualidade útil e confiável.

**Métricas de Experiência:**

| Métrica | Target | Evidência |
|---------|--------|-----------|
| Taxa de satisfação (👍/👎) | >85% | Métrica #1 escolhida pelo PM — sinal composto de qualidade |
| Taxa de retorno D7 | >40% | Padrão de uso: dúvidas pontuais recorrentes (feedback dos alunos) |
| Taxa de resolução (sem reformulação) | >75% | Alunos querem "respostas rápidas" sem ter que reformular |
| Latência P95 (texto) | <8s | Reclamação recorrente dos alunos: "tempo de resposta lento" |
| Latência P95 (áudio) | <12s | Transcrição + processamento |
| Taxa de citação confiável | >70% | Diferenciador #1 do produto vs ChatGPT |

**Momento "aha" da migração:** O aluno não sabe que algo mudou por dentro, mas sente: "ficou mais rápido, mais organizado, e parou de travar". Resolução das dores atuais (latência, formatação, rate limiting imprevisível) sem perder o que já funciona bem.

**Padrões de uso reais (feedback dos alunos):**
- Dúvidas pontuais durante estudos e internato
- Consultas rápidas de conduta, prescrição e dosagem
- Apoio durante rodízios hospitalares
- Resolução de questões pós-trilha e flashcards
- Resumos e aprofundamento de temas de aula

### Sucesso de Negócio

**Objetivos 3 meses (migração completa):**
- 100% do tráfego no código novo (paridade funcional)
- Zero downtime durante migração (Strangler Fig)
- Custo por conversa visível em dashboard (hoje é caixa preta)
- Feedback loop ativo — primeiras métricas de qualidade coletadas
- Base de comparação estabelecida: latência, custo e qualidade documentados

**Objetivos 12 meses (diferenciação e escala):**
- Crescimento da base de usuários ativos (meta a definir com diretoria)
- Custo por usuário ativo otimizado e sustentável (<$1.00/mês)
- Feedback loop gerando melhoria mensurável na qualidade do RAG
- Memória e personalização funcionais — experiência superior ao ChatGPT
- Dados de viabilidade para monetização stand-alone

### Sucesso Técnico

**Prioridades de risco (definidas pelo PM):**
1. **Serviço funcionar** — uptime 99.5% (M1) → 99.9% (M3)
2. **Custo controlado** — custo por conversa <$0.03, visibilidade total via cost tracking
3. **Latência aceitável** — P95 <8s texto, melhorando para <5s em 12 meses

**KPIs Técnicos:**

| KPI | Target M1 | Target 12 meses |
|-----|-----------|-----------------|
| Uptime | 99.5% | 99.9% |
| Taxa de erro Claude | <2% | <0.5% |
| Prompt cache hit rate | >70% | >90% |
| Cobertura RAG | Medir baseline | >60% |
| Custo/conversa | Medir (hoje caixa preta) | <$0.03 |

### Resultados Mensuráveis

**Critério de sucesso da migração (go/no-go):**

| Critério | Métrica | Target |
|----------|---------|--------|
| Paridade funcional | 100% features n8n replicadas | Sim/Não |
| Zero downtime | Nenhuma interrupção na migração | 0 incidentes |
| Qualidade ≥ n8n | Comparação Shadow Mode | Igual ou superior |
| Feedback ativo | Taxa de resposta nos Reply Buttons | >10% |
| Custo visível | Cost tracking funcionando | Custo por conversa mensurável |
| Observabilidade | Traces no Langfuse | 100% requests rastreados |

## Escopo do Projeto & Desenvolvimento Faseado

### Estratégia e Filosofia do MVP

**Abordagem MVP:** Problem-Solving MVP — resolver dores reais que os alunos já sentem (latência, rate limiting imprevisível, formatação ruim, erros silenciosos) com uma migração que o usuário não percebe por dentro, mas sente na prática.

**Racional:** O produto já funciona e já tem usuários satisfeitos. O MVP não é "lançar um produto novo" — é migrar a base de código de n8n para código próprio alcançando paridade funcional + quick wins que resolvem as dores documentadas no feedback real de ~50 alunos.

**Estratégia de migração:** Strangler Fig (Shadow Mode → Rollout gradual 5%→25%→50%→100% → Code Primary)

**Recursos Necessários:** Desenvolvedor full-stack com experiência em Node.js ou Python, Claude SDK e integrações WhatsApp. Suporte do PM (Rodrigo) para gestão do system prompt e configurações operacionais.

### Feature Set do MVP (Fase 1)

**Jornadas Core Suportadas:**
- Lucas (Aluno): dúvida de estudo, apoio no plantão, recuperação de erro, rate limit transparente
- Camila (Não-Aluno): primeira interação, uso básico de Q&A
- Ana (Equipe): monitoramento via Langfuse (dashboard dedicado é M1.5)

**Capacidades Must-Have:**

| # | Feature | Justificativa |
|---|---------|---------------|
| 1 | Q&A Médico com Tool Use (Claude SDK) | Core do produto — sem isso não existe |
| 2 | RAG Médico (Pinecone) com citações | Diferenciador #1 vs ChatGPT |
| 3 | Busca Web com citações | Feature existente, paridade |
| 4 | Transcrição de áudio (Whisper) | Feature existente, paridade |
| 5 | Análise de imagens (Vision) | Must-have — alunos mandam muitas fotos de questões |
| 6 | Bulas de medicamentos | Feature existente, paridade |
| 7 | Calculadoras médicas | Feature existente, paridade |
| 8 | Quiz / Prática ativa | Manter no MVP — melhorar estímulo via prompt |
| 9 | Identificação Aluno vs Não-Aluno | Feature existente, paridade |
| 10 | Histórico de conversa (Supabase) | Feature existente, preservar dados |
| 11 | Rate Limiting com transparência | Resolve dor #1 dos alunos (imprevisibilidade) |
| 12 | Feedback 👍/👎 (Reply Buttons) | North Star Metric depende disso |
| 13 | Cost tracking por request | Prioridade de negócio (custo é caixa preta hoje) |
| 14 | Prompt Caching | Redução de ~90% do custo em chamadas repetidas |
| 15 | Observabilidade (Langfuse) | Base para tudo: métricas, alertas, debugging |
| 16 | Formatação inteligente de respostas | Resolve dor de formatação (feedback dos alunos) |
| 17 | Configuração dinâmica (Supabase + Redis) | Equipe precisa mudar parâmetros sem deploy |
| 18 | System prompt gerenciável e versionado | PM mantém e evolui o prompt sem deploy |
| 19 | Self-healing (retry + fallback + alerta) | Resolve erros silenciosos do n8n |
| 20 | Migração Strangler Fig | Zero downtime na migração |

### Features Pós-MVP

**Fase 2 — M1.5 (Quick Wins pós-paridade):**
- Onboarding contextualizado (sem formulário, fricção zero)
- NPS in-chat periódico
- Dashboard básico para equipe Medway (Metabase ou similar)
- Logging de lacunas do RAG
- CTA de compartilhamento
- Validação de aceite de termos com jurídico

**Fase 3 — M2 (Diferenciação):**
- Memória de longo prazo e personalização
- Follow-ups proativos (Reply Buttons)
- Detecção de alucinação (batch com Haiku)
- Relatório de lacunas do RAG automatizado
- Busca de aulas/materiais da plataforma Medway
- Métricas estratégicas (conversão, CAC, engagement)
- Upsell contextual para não-alunos

**Fase 4 — M3 (Produto Fenomenal):**
- Quiz com spaced repetition (Leitner/SM-2)
- Desafio diário / calendário com gamificação
- Estudo guiado por tema (jornadas estruturadas)
- Pesquisa de willingness-to-pay
- Preparação stand-alone (pricing, landing page, assinatura)
- Analytics avançado (cohort, churn prediction, ROI por feature)

### Estratégia de Mitigação de Riscos

**Riscos Técnicos:**

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Instabilidade da API Claude | Alto — serviço para | Circuit breaker + retry + mensagem amigável + alerta à equipe |
| Migração quebra funcionalidade existente | Alto — experiência degrada | Strangler Fig com Shadow Mode — comparar respostas antes de migrar tráfego |
| Prompt Caching não atinge economia esperada | Médio — custo acima do planejado | Monitorar cache hit rate desde dia 1, otimizar se <70% |
| Complexidade do Tool Use maior que o esperado | Médio — atraso na migração | Começar pelos tools mais simples, validar arquitetura cedo |

**Riscos de Mercado:**

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Alunos não percebem melhoria | Médio — sem retorno visível | Quick wins visíveis (formatação, transparência de rate limit) |
| Meta muda políticas de bots de saúde | Alto — serviço bloqueado | Monitorar policies, manter mensagens em sessão ativa |

**Riscos de Recursos:**

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Menos recursos que planejado | Médio — MVP demora mais | Feature set mínimo: 10 features core |
| PM não consegue manter system prompt | Baixo — bottleneck | Interface Supabase simples, com histórico e rollback |
| Custo de infra maior que esperado | Médio — inviabilidade | Cost tracking desde dia 1, alertas de custo |

## Jornadas do Usuário

### Persona 1: Lucas — Aluno Medway

**Quem é:** Lucas, 24 anos, 4o ano de medicina, assinante Medway. WhatsApp é sua ferramenta principal. Estuda em casa, na biblioteca, e faz rodízio no hospital.

#### Cenário 1: Dúvida de estudo (happy path)

Lucas está estudando cardiologia pela plataforma Medway. Lê sobre insuficiência cardíaca e fica com dúvida sobre quando usar carvedilol vs metoprolol. Abre o WhatsApp, manda a pergunta pro Medbrain.

Em 5 segundos, recebe uma resposta estruturada:
- **Indicações** de cada um em tópicos claros
- **Diferenças práticas** com destaque em negrito
- **Fonte:** referência ao Harrison e à diretriz brasileira de IC
- **Pergunta de follow-up:** "Quer praticar com uma questão sobre betabloqueadores na IC?"

Lucas pensa: "Isso levaria 15 minutos no Google e eu não teria certeza da fonte." Dá 👍 no Reply Button.

**Requisitos revelados:** Q&A com Tool Use, RAG com citações, formatação estruturada, feedback 👍/👎, latência <8s.

#### Cenário 2: Apoio no plantão do internato

Lucas está no PS, 2h da manhã. Chega paciente com fibrilação atrial. O preceptor pede pra calcular o CHA₂DS₂-VASc. Lucas manda áudio pro Medbrain: "Paciente 72 anos, hipertenso, diabético, sem AVC prévio, sem IC. Qual o CHA₂DS₂-VASc?"

O Medbrain transcreve o áudio, identifica que precisa de duas tools (calculadora médica + RAG), executa em paralelo. Responde em 10 segundos:
- **Score: 4 pontos** (idade ≥75 = 2, HAS = 1, DM = 1)
- **Conduta:** anticoagulação indicada
- **Fonte:** diretriz SBC 2023
- **Opções de anticoagulantes** com doses

Lucas mostra pro preceptor. Impressiona. Resolve em 30 segundos o que levaria 5 minutos procurando no UpToDate.

**Requisitos revelados:** Transcrição de áudio, calculadoras médicas, tools paralelas, RAG com diretrizes brasileiras, latência <12s (áudio).

#### Cenário 3: Erro técnico — o sistema se resolve

Lucas manda uma pergunta sobre dosagem de amoxicilina pediátrica. O serviço do Claude retorna timeout (instabilidade momentânea da API).

**Antes (n8n):** Silêncio. Lucas espera 1 minuto. Nada. Manda de novo. Nada. Fica frustrado. Vai pro suporte. Abre ticket. Talvez receba resposta em 24h. O erro já se resolveu em 30 segundos.

**Agora (código novo):** O sistema detecta o timeout, tenta retry automático. Se falha de novo, responde ao Lucas:
> "Desculpe, tive uma instabilidade técnica ao processar sua pergunta. Pode enviar novamente?"

Lucas reenvia. Dessa vez funciona. Recebe a resposta. Nem lembra que teve erro.

Nos bastidores: o erro é logado no Langfuse com contexto completo (usuário, mensagem, tipo de erro, timestamp). Se isso está acontecendo com vários alunos ao mesmo tempo, a equipe Medway recebe alerta automático.

**Requisitos revelados:** Retry automático, mensagem de erro amigável ao usuário, logging de erros com contexto, alertas de taxa de erro, circuit breaker.

#### Cenário 4: Rate limit atingido — transparência

Lucas usou bastante o Medbrain hoje estudando pra prova. Na 18ª interação, recebe junto da resposta:
> "Você ainda tem 2 perguntas disponíveis hoje. Seu limite reseta amanhã às 00h."

Na 20ª, o sistema informa:
> "Você atingiu seu limite de 20 interações por hoje. Seu limite reseta amanhã às 00h. Até lá!"

Lucas sabe exatamente o que aconteceu, quando volta, e não precisa procurar suporte.

**Antes (n8n):** "Do nada ele diz que eu atingi o limite e fica nessa por pelo menos 48h." (feedback real de aluna)

**Requisitos revelados:** Contador de uso visível, mensagem clara de limite, informação de reset, rate limiting previsível e transparente.

### Persona 2: Camila — Não-Aluno

**Quem é:** Camila, 26 anos, residente de clínica médica, não assinante Medway. Conheceu o Medbrain por indicação de colega.

#### Cenário 1: Primeira interação (descoberta)

Camila recebe o contato do Medbrain de um colega residente. "Usa isso, é melhor que o ChatGPT pra medicina." Manda "Oi" no WhatsApp.

Recebe uma mensagem de boas-vindas simples (sem formulário, sem cadastro):
> "Olá! Sou o Medbrain, seu tutor médico pelo WhatsApp. Pode me perguntar qualquer dúvida médica — respondo com fontes verificáveis. Experimente!"

Camila testa: "Quais critérios de Light para diferenciar transudato de exsudato?"

Recebe resposta completa, estruturada, com fonte. Pensa: "Isso é realmente melhor que o ChatGPT." Momento "aha" — confiança na fonte.

**Requisitos revelados:** Onboarding fricção zero (M1.5), Q&A funcional sem cadastro, diferenciação aluno/não-aluno transparente.

#### Cenário 2: Uso recorrente e conversão

Camila usa o Medbrain 3x por semana durante 2 meses. Na prática do hospital, virou hábito. Após uma resposta, vê:
> "Gostou? Indica o Medbrain pra um colega!"

Indica para 2 colegas residentes. Quando a Medway lança funcionalidades exclusivas para alunos (busca de aulas, materiais), Camila vê:
> "Essa funcionalidade é exclusiva para alunos Medway. Conheça os planos."

Camila já confia no produto. Considera assinar.

**Requisitos revelados:** CTA compartilhamento, identificação aluno/não-aluno, upsell contextual (M2), tracking de conversão (M2).

### Persona 3: Ana — Equipe Medway

**Quem é:** Ana, analista de produto na Medway. Responsável por monitorar o Medbrain, analisar dados e apresentar insights para a diretoria.

#### Cenário 1: Monitoramento e análise semanal

Segunda-feira, 9h. Ana abre o dashboard do Langfuse/Metabase. Vê:
- **Semana passada:** 4.200 conversas, custo total $98, custo médio $0.023/conversa
- **Satisfação:** 87% (👍), acima do target de 85%
- **Latência P95:** 6.2s (dentro do target)
- **Top 5 temas perguntados:** Cardiologia (18%), Pediatria (15%), Clínica Médica (14%), Cirurgia (12%), Infectologia (10%)
- **Taxa de erro:** 0.8% (abaixo de 2%)

Prepara relatório para a diretoria com dados mastigados: "O Medbrain está custando $0.023 por conversa com 87% de satisfação. Recomendação: investir em conteúdo de cardiologia e pediatria (50% das lacunas do RAG são nesses temas)."

**Requisitos revelados:** Dashboard de métricas, cost tracking, relatórios de satisfação, análise por tema, dados exportáveis.

#### Cenário 2: Alerta de erro — resposta proativa

Quarta-feira, 14h. Ana recebe alerta: "Taxa de erro subiu para 12% nos últimos 15 minutos (normal: <2%)."

Abre o Langfuse. Vê que os erros são todos timeout do Claude API. Verifica o status page da Anthropic — instabilidade confirmada.

Enquanto isso, os alunos afetados já receberam mensagem automática do bot: "Tive uma instabilidade técnica, pode reenviar sua pergunta." Nenhum ticket de suporte aberto.

Ana monitora. Em 20 minutos, a taxa volta ao normal. Registra o incidente. Nenhuma ação manual foi necessária.

**Antes (n8n):** Ana descobriria o problema horas depois, quando os tickets de suporte começassem a chegar.

**Requisitos revelados:** Alertas automáticos por threshold, dashboard de erros em tempo real, auto-recovery do bot, logging com contexto.

### Resumo de Requisitos por Jornada

| Jornada | Requisitos Revelados |
|---------|---------------------|
| Lucas — Estudo | Q&A Tool Use, RAG + citações, formatação estruturada, feedback 👍/👎 |
| Lucas — Plantão | Áudio (Whisper), calculadoras médicas, tools paralelas, baixa latência |
| Lucas — Erro | Retry automático, mensagem de erro amigável, logging, alertas, circuit breaker |
| Lucas — Rate Limit | Contador visível, mensagem de limite clara, informação de reset |
| Camila — Descoberta | Onboarding zero fricção, Q&A sem cadastro, identificação aluno/não-aluno |
| Camila — Recorrente | CTA compartilhamento, upsell contextual, tracking de conversão |
| Ana — Análise | Dashboard métricas, cost tracking, relatórios, dados exportáveis |
| Ana — Alerta | Alertas automáticos, dashboard tempo real, auto-recovery, logging contextual |

## Requisitos Específicos do Domínio

### Contexto Regulatório

**Classificação:** Ferramenta educacional de apoio — não é dispositivo médico (SaMD) e não se enquadra em classificação ANVISA. Comparável a ferramentas já existentes no mercado (Open Evidence, ChatGPT para medicina).

**Status atual:** Produto em operação sem incidentes regulatórios. A migração de n8n para código próprio não altera o perfil de risco — mesma funcionalidade, mesma base de conhecimento, mesma finalidade.

### Disclaimer e Responsabilidade

- Mensagem de disclaimer já implementada: o Medbrain é ferramenta de apoio, a decisão clínica cabe ao médico
- Modelo equivalente ao Open Evidence e outras ferramentas de referência médica
- Respostas sempre acompanhadas de fontes verificáveis — reforça o caráter de consulta, não de prescrição

### Compliance e Privacidade (LGPD)

- Contrato e compliance já preparados pela Medway
- Dados de conversas armazenados no Supabase com controle de acesso
- **Ação futura (M1.5):** Validar com jurídico a necessidade de aceite de termos no primeiro uso via WhatsApp — pode ser integrado ao onboarding contextualizado
- Não há tratamento de dados de pacientes reais — os dados são dúvidas de estudo e cenários hipotéticos

### Políticas WhatsApp Business API

- Produto já opera em conformidade com as políticas da Meta
- **Ação de validação:** Reler e confirmar compliance com políticas atuais de bots de saúde no WhatsApp Business API durante a migração
- Monitorar atualizações de política da Meta (especialmente para template messages no M2)

### Precisão do Conteúdo Médico

- RAG com base de conhecimento curada pelos professores Medway — conteúdo revisado
- Citações de fontes verificáveis em cada resposta (diferenciador #1)
- **MVP:** Logging de qualidade via feedback 👍/👎
- **M2:** Detecção automatizada de alucinação (batch com Haiku) para auditoria de qualidade

### Riscos de Domínio e Mitigações

| Risco | Impacto | Mitigação | Fase |
|-------|---------|-----------|------|
| Resposta médica incorreta influencia conduta | Alto | Disclaimer + fontes verificáveis + feedback loop | MVP |
| Dados de conversas expostos | Médio | RLS no Supabase, service_role apenas no backend, LGPD compliance | MVP |
| Mudança nas políticas da Meta para bots de saúde | Médio | Monitoramento de policies, manter mensagens dentro de sessão ativa | Contínuo |
| Necessidade de aceite formal de termos | Baixo | Validar com jurídico, implementar no onboarding M1.5 se necessário | M1.5 |

## Requisitos Técnicos do Backend

> **Nota:** Esta seção fornece contexto de implementação para o Architecture Document. As capacidades formais estão em Requisitos Funcionais; os atributos de qualidade em Requisitos Não-Funcionais.

### Visão Geral da Arquitetura

O mb-wpp é um backend de processamento de mensagens com fluxo unidirecional:

```
WhatsApp (Meta Cloud API) → Webhook → mb-wpp → Claude/Tools → WhatsApp (resposta)
```

Não é uma API REST tradicional. Tem um único ponto de entrada (webhook) e um único consumidor (WhatsApp Business API). Toda a complexidade está na orquestração interna.

### Webhook e Integração WhatsApp

**Provedor:** Meta Cloud API (direto)
- Webhook de entrada: recebe notificações de mensagens (texto, áudio, imagem, interações com Reply Buttons)
- API de saída: envia respostas via WhatsApp Business API (texto, Reply Buttons)
- **Decisão em aberto:** Avaliar se Meta Cloud API direto é a melhor opção ou se um provedor intermediário oferece vantagens

**Fluxo do webhook:**
1. Meta envia POST com payload da mensagem
2. Backend valida assinatura do webhook (segurança)
3. Extrai dados: phone number, tipo de mensagem, conteúdo
4. Enfileira para processamento (message buffer no Redis para debounce)
5. Retorna 200 OK imediatamente (Meta exige resposta rápida)

### Autenticação e Identificação de Usuário

**Mecanismo:** Phone number → lookup na plataforma Medway
- Número do WhatsApp é o identificador único capturado do webhook
- Verificação contra API/base de dados da plataforma Medway para classificar: aluno ativo, ex-aluno, não-aluno
- Resultado cacheado no Redis para evitar lookup a cada mensagem
- Features disponíveis variam por tipo de usuário

### Pipeline de Processamento de Mensagens

| Etapa | Componente | Responsabilidade |
|-------|-----------|-----------------|
| 1. Recepção | Webhook handler | Validar, extrair dados, responder 200 OK |
| 2. Buffer | Redis (debounce) | Acumular mensagens rápidas (espera configurável) |
| 3. Identificação | Cache Redis + API Medway | Classificar usuário (aluno/não-aluno) |
| 4. Rate Check | Redis (sliding window) | Verificar e decrementar limite diário |
| 5. Pré-processamento | Whisper / Vision | Transcrever áudio ou processar imagem |
| 6. Contexto | Supabase + Redis | Carregar histórico de conversa |
| 7. Processamento | Claude SDK (Tool Use) | Gerar resposta com tools especializadas |
| 8. Pós-processamento | Formatter | Formatar para WhatsApp (markdown limpo) |
| 9. Envio | WhatsApp API | Enviar resposta + Reply Buttons (feedback) |
| 10. Persistência | Supabase + Langfuse | Salvar conversa + trace de observabilidade |
| 11. Cost tracking | Langfuse + Supabase | Registrar custo por request |

### Stack Tecnológica

| Camada | Tecnologia | Justificativa |
|--------|-----------|---------------|
| **Runtime** | Node.js (TypeScript) ou Python | A definir — ambos têm SDK Claude nativo |
| **WhatsApp** | Meta Cloud API | Já em uso, sem intermediário |
| **IA** | Claude SDK (Anthropic) | Tool Use nativo, Prompt Caching, streaming |
| **Vector DB** | Pinecone | RAG médico, já em uso |
| **Database** | Supabase (PostgreSQL) | Já em uso — migrar schema, preservar dados |
| **Cache** | Redis (Upstash) | Rate limit, session, message buffer, cache |
| **Áudio** | OpenAI Whisper | Transcrição de mensagens de voz |
| **Observabilidade** | Langfuse | Traces, métricas, custo, qualidade |
| **Deploy** | Railway ou Fly.io | A definir — Railway já usado na Medway |
| **CI/CD** | GitHub Actions | Testes automatizados, deploy automático |

### Tratamento de Erros e Resiliência

| Padrão | Aplicação | Configuração |
|--------|-----------|-------------|
| **Retry automático** | Chamadas Claude, Pinecone, Whisper | Retries com backoff exponencial (configurável) |
| **Circuit breaker** | Serviços externos | Abre após N falhas, tenta novamente após intervalo (configurável) |
| **Timeout** | Todas as chamadas externas | Valores configuráveis por serviço |
| **Fallback ao usuário** | Quando retry falha | Mensagem amigável configurável |
| **Dead letter queue** | Mensagens que falharam completamente | Log para análise, alerta se volume alto |

### Rate Limiting

| Tipo de Usuário | Limite Diário | Anti-burst |
|-----------------|--------------|------------|
| Aluno Medway | Configurável (ex: 50/dia) | Configurável (ex: 3 msg/3s) |
| Não-Aluno | Configurável (ex: 20/dia) | Configurável (ex: 3 msg/3s) |

- Sliding Window (Redis) para limite diário + Token Bucket para anti-burst
- Transparência: mensagem com perguntas restantes + horário de reset

### Configuração Dinâmica (Requisito MVP)

**Princípio:** Parâmetros operacionais devem ser modificáveis pela equipe Medway sem deploy.

**Implementação:** Tabela de configuração no Supabase com cache no Redis.

**Parâmetros configuráveis:**

| Categoria | Parâmetros |
|-----------|-----------|
| **Rate limiting** | Limites diários por tipo de usuário, anti-burst, horário de reset |
| **Resiliência** | Retries, timeouts por serviço, thresholds de circuit breaker |
| **Mensagens** | Debounce time, mensagem de erro, mensagem de limite atingido |
| **Alertas** | Thresholds de erro, destinatários de alerta |
| **System prompt** | Prompt principal, regras médicas, disclaimer, tom de voz |

**Requisitos da configuração:**
- Mudança reflete em minutos (cache TTL curto no Redis)
- Histórico de alterações (quem mudou, quando, valor anterior)
- Rollback para versão anterior em caso de problema

### System Prompt como Conteúdo Gerenciável

O system prompt é a alma do Medbrain. Define personalidade, regras médicas, disclaimer, como citar fontes, quando usar cada tool.

**Requisitos:**
- Armazenado no Supabase (não hardcoded no código)
- Versionado: cada alteração gera versão com timestamp e autor
- Editável sem deploy pela equipe de produto
- Histórico de mudanças visível
- Rollback para versão anterior
- Compatível com Prompt Caching do Claude (o cache invalida automaticamente quando o prompt muda)

### Migração de Dados

**Contexto:** Supabase já em uso com dados de produção. A migração é de código, não de banco.

**Estratégia:**
- Manter base Supabase existente — preservar dados de usuários, histórico, contadores
- Evoluir schema conforme necessário (adicionar colunas, índices, tabelas novas)
- Código novo e n8n apontam para o mesmo Supabase durante transição (Strangler Fig)
- Migração de schema via migrations versionadas (sem perda de dados)

### Infraestrutura e Deploy

**Decisão em aberto:** Railway vs Fly.io

**Ambientes necessários:**
- **Staging:** Para testes e Shadow Mode durante migração
- **Production:** Tráfego real
- **CI/CD:** GitHub Actions com testes automatizados antes de deploy

### Decisões Técnicas em Aberto

| Decisão | Opções | Quando Decidir |
|---------|--------|---------------|
| Linguagem/runtime | TypeScript vs Python | Architecture Doc |
| Deploy | Railway vs Fly.io | Architecture Doc |
| WhatsApp provider | Meta Cloud API direto vs intermediário | Architecture Doc |
| Schema evolution | Migrations manuais vs ferramenta (Prisma, Drizzle, Alembic) | Architecture Doc |

## Requisitos Funcionais

### Interação com Usuário via WhatsApp

- **FR1:** Aluno pode enviar perguntas por texto pelo WhatsApp e receber respostas
- **FR2:** Aluno pode enviar mensagens de áudio e receber respostas baseadas na transcrição do áudio
- **FR3:** Aluno pode enviar imagens (fotos de questões, exames, casos) e receber análise baseada no conteúdo visual
- **FR4:** Aluno pode fornecer feedback sobre a qualidade da resposta recebida (positivo/negativo)
- **FR5:** Aluno pode adicionar um comentário opcional após fornecer feedback, explicando o motivo da avaliação
- **FR6:** O sistema pode acumular mensagens rápidas consecutivas antes de processar (debounce)
- **FR7:** O sistema pode responder de forma informativa quando recebe um tipo de mensagem não suportado (sticker, localização, documento, contato)
- **FR8:** O sistema pode dividir respostas que excedem o limite do WhatsApp em mensagens sequenciais, mantendo coerência e formatação
- **FR9:** O sistema pode indicar ao usuário que está processando sua mensagem enquanto elabora a resposta
- **FR10:** Novo usuário pode receber mensagem de boas-vindas na primeira interação, sem necessidade de cadastro ou formulário

### Consulta Médica Inteligente

- **FR11:** Aluno pode fazer perguntas médicas e receber respostas contextualizadas com citações de fontes verificáveis
- **FR12:** O sistema pode buscar informações na base de conhecimento médica e citar as fontes utilizadas
- **FR13:** O sistema pode buscar informações na web quando a base de conhecimento não tem cobertura, citando fontes
- **FR14:** Aluno pode consultar informações sobre bulas de medicamentos (indicações, dosagens, interações)
- **FR15:** Aluno pode utilizar calculadoras médicas fornecendo dados por texto ou áudio
- **FR16:** O sistema pode selecionar automaticamente as ferramentas adequadas para cada pergunta e utilizá-las (inclusive em paralelo) para compor a resposta
- **FR17:** O sistema pode incluir disclaimers médicos apropriados nas respostas, reforçando que é ferramenta de apoio e não substitui avaliação médica

### Formatação e Apresentação de Respostas

- **FR18:** O sistema pode formatar respostas de forma estruturada e otimizada para leitura no WhatsApp
- **FR19:** O sistema pode adaptar o formato da resposta ao tipo de conteúdo (explicação, cálculo, lista, comparação, questão)

### Identificação e Controle de Acesso

- **FR20:** O sistema pode identificar o tipo de usuário (aluno Medway, não-aluno) a partir do número de telefone
- **FR21:** O sistema pode disponibilizar funcionalidades diferenciadas conforme o tipo de usuário
- **FR22:** Aluno pode visualizar quantas perguntas restam no dia e quando o limite reseta
- **FR23:** O sistema pode limitar o número de interações diárias por tipo de usuário
- **FR24:** O sistema pode proteger contra burst de mensagens (anti-spam)

### Quiz e Prática Ativa

- **FR25:** Aluno pode participar de quiz e prática ativa sobre temas médicos
- **FR26:** O sistema pode sugerir quiz de prática ativa ao final de respostas relevantes, estimulando a adesão

### Histórico e Contexto

- **FR27:** Aluno pode ter suas conversas anteriores consideradas no contexto das novas respostas
- **FR28:** O sistema pode armazenar e recuperar histórico de conversas por usuário

### Observabilidade e Monitoramento

- **FR29:** Equipe Medway pode rastrear o custo por request e por conversa
- **FR30:** Equipe Medway pode monitorar métricas de qualidade (satisfação, latência, taxa de erro)
- **FR31:** Equipe Medway pode receber alertas automáticos quando thresholds de erro são ultrapassados
- **FR32:** Equipe Medway pode acessar traces completos de cada interação para debugging e análise de qualidade

### Configuração e Operação

- **FR33:** Equipe Medway pode modificar parâmetros operacionais sem deploy (rate limits, timeouts, retries, mensagens)
- **FR34:** Equipe Medway pode editar o system prompt do Medbrain sem deploy
- **FR35:** Equipe Medway pode visualizar histórico de alterações do system prompt com autor e timestamp
- **FR36:** Equipe Medway pode reverter o system prompt para uma versão anterior
- **FR37:** Equipe Medway pode visualizar histórico de alterações de configurações operacionais (quem alterou, quando, valor anterior e novo)
- **FR38:** O sistema pode refletir mudanças de configuração em minutos, sem restart

### Resiliência e Recuperação

- **FR39:** O sistema pode realizar retry automático em caso de falha de serviço externo
- **FR40:** O sistema pode enviar mensagem amigável ao usuário quando uma falha persiste após retries
- **FR41:** O sistema pode fornecer resposta parcial quando uma ferramenta específica falha, informando ao usuário quais fontes não estavam disponíveis
- **FR42:** O sistema pode interromper chamadas a serviços em falha recorrente (circuit breaker)
- **FR43:** O sistema pode registrar erros com contexto completo (usuário, mensagem, tipo de erro, timestamp) para análise

### Migração e Continuidade

- **FR44:** O sistema pode operar em paralelo com o n8n durante a migração (Shadow Mode / Strangler Fig)
- **FR45:** O sistema pode preservar todos os dados existentes no Supabase durante a migração
- **FR46:** Equipe Medway pode controlar o percentual de tráfego roteado para o código novo vs n8n
- **FR47:** Equipe Medway pode comparar respostas geradas pelo código novo vs n8n durante Shadow Mode para validação de qualidade

## Requisitos Não-Funcionais

### Performance

- **NFR1:** Latência P95 para respostas de texto < 8 segundos (end-to-end: webhook recebido → resposta enviada)
- **NFR2:** Latência P95 para respostas de áudio < 12 segundos (inclui transcrição Whisper)
- **NFR3:** Latência P95 para respostas de imagem < 15 segundos (inclui processamento Vision)
- **NFR4:** O sistema deve suportar pelo menos 50 conversas concorrentes sem degradação de performance
- **NFR5:** Message debounce deve acumular mensagens por no máximo 3 segundos (valor configurável via config dinâmica)

### Custo e Eficiência

- **NFR6:** Custo médio por conversa < $0.03 em regime estável (após otimizações de Prompt Caching)
- **NFR7:** Prompt Cache hit rate > 70% no M1, evoluindo para > 90% em 12 meses
- **NFR8:** Cost tracking com granularidade por request (precisão de ±5% sobre custo real da API)
- **NFR9:** Alertas automáticos quando gasto diário exceder threshold configurável

### Disponibilidade e Confiabilidade

- **NFR10:** Uptime do serviço >= 99.5% (M1) evoluindo para >= 99.9% (M3)
- **NFR11:** Taxa de erro do sistema < 2% (M1) evoluindo para < 0.5% (12 meses)
- **NFR12:** Tempo de recuperação automática (MTTR) < 5 minutos para falhas de serviços externos
- **NFR13:** Nenhuma mensagem de usuário deve ser silenciosamente perdida — toda mensagem recebe resposta ou mensagem de erro explícita
- **NFR14:** Webhook deve responder com 200 OK em < 3 segundos (requisito da Meta Cloud API para evitar reenvios)

### Segurança e Privacidade

- **NFR15:** Dados de conversas protegidos com Row Level Security (RLS) no Supabase — isolamento por usuário
- **NFR16:** Validação de assinatura em todos os webhooks recebidos (prevenção de injeção de mensagens)
- **NFR17:** Chaves de API e credenciais armazenadas exclusivamente em variáveis de ambiente, nunca no código-fonte
- **NFR18:** Dados pessoais tratados conforme LGPD (consentimento, finalidade, minimização de dados)
- **NFR19:** Logs de observabilidade não devem conter dados sensíveis do usuário em texto plano
- **NFR20:** Acesso à configuração dinâmica e edição de system prompt restrito à equipe autorizada

### Integrações e Dependências Externas

- **NFR21:** Timeout configurável individualmente por serviço externo (Claude, Pinecone, Whisper, Meta API)
- **NFR22:** Circuit breaker com threshold configurável para cada dependência externa
- **NFR23:** Estratégia de fallback documentada para cada dependência (comportamento quando cada serviço falha)
- **NFR24:** Compatibilidade com versão atual da WhatsApp Business API, com capacidade de migrar para novas versões
