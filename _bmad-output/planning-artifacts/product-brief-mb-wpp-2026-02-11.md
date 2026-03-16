---
stepsCompleted: [1, 2, 3, 4, 5]
inputDocuments:
  - brainstorming-session-2026-02-09.md
  - claude-sdk-tool-use-architecture-research-2026-02-10.md
  - technical-arquitetura-ideal-medbrain-whatsapp-research-2026-02-10.md
date: 2026-02-11
author: Rodrigo Franco
project_name: mb-wpp
---

# Product Brief: mb-wpp

## Sumário Executivo

O Medbrain WhatsApp (mb-wpp) é um tutor médico inteligente via WhatsApp que funciona como um parceiro médico para todas as horas — dúvidas do dia a dia, engajamento em estudos, apoio no plantão, cálculos clínicos e muito mais. Diferencia-se por combinar IA conversacional de ponta com uma base de conhecimento médico curada (nacional e internacional) e citações de fontes reais e verificáveis, resolvendo o problema central de confiança que impede estudantes e médicos de dependerem de soluções de IA generativas.

O produto atual opera em produção sobre uma arquitetura n8n com 116 nodos, atendendo alunos Medway e não-alunos. A migração para código próprio com arquitetura profissional (Tool Use, testes automatizados, observabilidade, feedback loops) é o catalisador para transformar o Medbrain de uma ferramenta funcional em um produto de referência — com potencial de se tornar um produto stand-alone vendável no futuro.

---

## Visão Central

### Declaração do Problema

Estudantes de medicina e médicos em atividade precisam de um companheiro confiável disponível 24/7 para consultas médicas rápidas, estudo ativo e apoio em situações clínicas. As soluções existentes falham em um ponto crítico: **confiança**. O ChatGPT responde perguntas médicas, mas sem garantia de precisão ou fontes verificáveis. O Open Evidence foca em referências internacionais, mas não cobre o contexto médico brasileiro (ANVISA, protocolos SUS, diretrizes nacionais). Nenhuma solução atual combina qualidade de resposta, referências confiáveis e conveniência no canal onde o profissional já vive — o WhatsApp.

### Impacto do Problema

- Alunos **não confiam** nas respostas de IA generativa por falta de citações reais, levando-os a confirmar manualmente cada informação — anulando o ganho de tempo
- Médicos em plantão não têm acesso rápido a protocolos, bulas e calculadoras de beira de leito em um canal único e prático
- A ausência de feedback estruturado impede a melhoria contínua da qualidade — não há como saber se as respostas estão boas ou ruins
- A plataforma n8n atual limita a criação de novas funcionalidades, relatórios, segurança e personalização — travando a evolução do produto

### Por Que as Soluções Existentes São Insuficientes

| Solução | O Que Faz Bem | Onde Falha |
|---------|--------------|------------|
| **ChatGPT** | Conversação natural, amplitude de conhecimento | Sem fontes verificáveis, alucina referências, sem contexto brasileiro, sem features médicas especializadas |
| **Open Evidence** | Referências internacionais, busca em evidências | Genérico, sem conteúdo nacional, não é um tutor (é uma ferramenta de busca), sem WhatsApp |
| **Concorrentes BR** | Presença no mercado brasileiro | Não possuem a base de conteúdo curado Medway nem a profundidade de features |
| **Medbrain atual (n8n)** | Funciona bem em produção, stack validada | Limitado pela plataforma n8n para expansão, sem testes, sem observabilidade granular, sem feedback loop |

### Solução Proposta

O mb-wpp será um **tutor médico inteligente de nível profissional** — quase um "ChatGPT médico turbinado" onde o aluno pode confiar 100%. Construído sobre uma arquitetura moderna de código próprio com:

- **Referências reais e verificáveis** em cada resposta (fontes nacionais e internacionais)
- **Arquitetura Tool Use** com Claude SDK nativo — tools especializadas (RAG médico, bulas, calculadoras, quiz, busca web com citações)
- **Feedback loop completo** — captura de satisfação do usuário, avaliação automatizada, melhoria contínua do RAG
- **Observabilidade total** — cost tracking por request, métricas de qualidade, dashboards de decisão
- **Base evolutiva** — código profissional com testes, CI/CD e capacidade ilimitada de expansão

O Medbrain não é apenas uma ferramenta de Q&A — é um parceiro médico para todas as horas que acompanha, ensina e evolui com o usuário.

### Diferenciadores-Chave

1. **Base de conhecimento Medway curada** — conteúdo exclusivo dos professores e materiais Medway, inacessível a concorrentes
2. **Referências nacionais + internacionais** — cobertura que o Open Evidence e ChatGPT não oferecem (ANVISA, protocolos SUS, diretrizes brasileiras)
3. **WhatsApp nativo** — onde o aluno já vive, zero fricção de adoção
4. **Citações reais verificáveis** — cada resposta com fonte rastreável, resolvendo o problema #1 de confiança
5. **Potencial stand-alone** — arquitetura preparada para se tornar um produto independente vendável, além de canal da Medway

---

## Usuários-Alvo

### Usuários Primários

#### Persona 1: Aluno Medway — "Lucas"

**Contexto:** Lucas, 24 anos, estudante do 4o ano de medicina, assinante ativo da Medway. Estuda em casa, na biblioteca e revisa conteúdo no transporte. Usa o WhatsApp como ferramenta principal de comunicação no dia a dia.

**Necessidades:**
- Tirar dúvidas médicas rapidamente sem sair do WhatsApp
- Receber respostas com **fontes confiáveis** que ele possa citar em provas e discussões clínicas
- Acesso rápido a bulas, protocolos e cálculos durante plantões do internato
- Conexão com conteúdo da plataforma Medway (aulas, materiais) de forma contextual

**Diferencial por ter dados na plataforma:**
- Busca de aulas e materiais específicos da Medway
- Contexto de aprendizado enriquecido (o bot sabe o que ele já estudou)
- Features exclusivas derivadas dos dados da plataforma

**Momento "Aha":**
- Recebe uma resposta com fonte real e verificável — sabe que pode confiar
- Resolve em 30 segundos uma dúvida que levaria 10 minutos pesquisando no Google

**Variação por estágio:** Alunos de anos iniciais (1o-2o) fazem perguntas mais básicas e conceituais. Alunos de anos finais (5o-6o / internato) fazem perguntas clínicas aplicadas, buscam protocolos e usam calculadoras.

**Comportamento atual:** Retorna ao Medbrain quando tem dúvidas pontuais. Ainda não há um loop de hábito estabelecido — oportunidade de criar engajamento recorrente através de follow-ups, prática ativa e conteúdo contextualizado.

---

#### Persona 2: Não-Aluno — "Camila"

**Contexto:** Camila, 26 anos, residente de clínica médica, não é assinante Medway. Conheceu o Medbrain por indicação de um colega ou campanha de marketing. Usa como ferramenta auxiliar no dia a dia clínico e de estudo.

**Necessidades:**
- As mesmas dúvidas e consultas rápidas do aluno Medway
- Acesso a informações médicas confiáveis no WhatsApp
- Praticidade — não quer instalar outro app ou criar conta em outra plataforma

**Limitações em relação ao aluno:**
- Sem acesso a features derivadas da plataforma Medway (busca de aulas, materiais exclusivos)
- Experiência base completa, mas sem personalização por dados da plataforma

**Valor estratégico:**
- Lead qualificado para conversão em aluno Medway
- Público-alvo para futuro produto stand-alone (monetização independente)
- Canal de aquisição orgânica via indicação (aluno satisfeito indica colegas)

**Momento "Aha":** O mesmo que o aluno — resposta confiável + velocidade. A diferença é que Camila descobre que existe algo melhor que o ChatGPT para medicina.

### Usuários Secundários

- **Equipe Medway (produto/tech):** Consomem dashboards de uso, custo, qualidade e satisfação para decisões de produto
- **Equipe de curadoria de conteúdo:** Usam relatórios de lacunas do RAG para priorizar criação de conteúdo
- **Gestão/diretoria:** Avaliam viabilidade de monetização com dados de custo por usuário e engagement

### Jornada do Usuário

| Etapa | Aluno Medway | Não-Aluno |
|-------|-------------|-----------|
| **Descoberta** | Divulgação interna Medway, onboarding da plataforma | Indicação de colega, marketing Medway, redes sociais |
| **Primeiro contato** | Manda mensagem no WhatsApp, sem onboarding específico hoje | Igual — sem onboarding estruturado hoje |
| **Uso recorrente** | Retorna com dúvidas pontuais (sem hábito estabelecido ainda) | Igual — uso sob demanda |
| **Momento de valor** | Resposta confiável com fonte + resolução rápida | Igual + descoberta de alternativa superior ao ChatGPT |
| **Retenção** | Oportunidade: follow-ups, prática ativa, conteúdo contextualizado | Oportunidade: conversão para aluno Medway ou futuro plano stand-alone |

**Oportunidades identificadas na jornada:**
- **Onboarding:** Criar boas-vindas contextualizada (sem formulário — princípio fricção zero do brainstorming)
- **Hábito:** Follow-up Reply Buttons, "continue estudando", desafio diário baseado em calendário
- **Feedback:** Botões de satisfação integrados nas respostas para fechar o loop de qualidade

---

## Métricas de Sucesso

### Métricas de Sucesso do Usuário

| Métrica | O Que Mede | Como Medir | Target |
|---------|-----------|------------|--------|
| **Taxa de satisfação** | % respostas com feedback positivo | Ratio 👍 / (👍+👎) nos Reply Buttons | > 85% |
| **Taxa de retorno D7** | % usuários que voltam em 7 dias | Contagem de usuários únicos recorrentes | > 40% |
| **Taxa de resolução** | % dúvidas resolvidas sem reformulação | Usuário NÃO reformula a mesma pergunta | > 75% |
| **Profundidade de sessão** | Engajamento por sessão | Média de mensagens por sessão | 5-8 msgs |
| **Tempo de resposta percebido** | Experiência de velocidade | Latência P95 (webhook → resposta entregue) | < 8s texto, < 12s áudio |
| **Taxa de citação confiável** | Confiança nas respostas | % respostas com pelo menos 1 fonte verificável | > 70% |
| **NPS in-chat** | Satisfação geral | Pesquisa periódica a cada 30-50 interações | > 40 |

### Objetivos de Negócio

**3 meses (Migração completa):**
- Paridade funcional com n8n — 100% do tráfego no código novo
- Cost tracking operacional — custo por conversa visível em dashboard
- Primeiras métricas de qualidade coletadas (feedback loop ativo)
- Zero downtime durante migração (Strangler Fig validado)
- Base de comparação estabelecida: latência, custo e qualidade documentados

**12 meses (Diferenciação e escala):**
- Crescimento da base de usuários ativos (meta a definir com diretoria)
- Custo por usuário ativo otimizado e sustentável
- Feedback loop gerando melhoria mensurável na qualidade do RAG
- Preparação para monetização stand-alone (dados de custo, engagement e willingness-to-pay)
- Memória e personalização funcionais — experiência significativamente superior ao ChatGPT

### KPIs Operacionais e Técnicos

| KPI | Descrição | Target M1 | Target M3 (12 meses) |
|-----|-----------|-----------|----------------------|
| **DAU** | Usuários ativos diários | Baseline atual | +30% vs baseline |
| **MAU** | Usuários ativos mensais | Baseline atual | +50% vs baseline |
| **Custo/conversa** | Custo médio por conversa completa | Medir (hoje é caixa preta) | < $0.03 |
| **Custo/usuário ativo/mês** | Custo mensal por DAU | Medir | < $1.00 |
| **Uptime** | Disponibilidade do serviço | 99.5% | 99.9% |
| **Latência P95 (texto)** | Tempo de resposta | < 8s | < 5s |
| **Taxa de erro Claude** | % requisições com erro | < 2% | < 0.5% |
| **Prompt cache hit rate** | Eficiência do cache | > 70% | > 90% |
| **Cobertura RAG** | % respostas que usam RAG vs conhecimento do modelo | Medir | > 60% |

### Métricas de Qualidade de Conteúdo

| Métrica | O Que Mede | Como Medir |
|---------|-----------|------------|
| **Score médio RAG** | Relevância dos chunks retornados | Média do similarity score do Pinecone |
| **Taxa de lacuna** | Perguntas sem boa resposta na base | Queries com RAG score < threshold |
| **Top 20 lacunas semanais** | Temas mais perguntados sem cobertura | Dashboard automático por tema |
| **Taxa de alucinação** | Respostas sem base factual | Avaliação batch com Haiku (amostragem) |
| **Feedback negativo por tema** | Áreas problemáticas | Correlação 👎 com tags de tema |

### Métricas Estratégicas (Stand-alone)

| Métrica | Relevância | Quando Medir |
|---------|-----------|--------------|
| **Conversão não-aluno → aluno** | ROI do Medbrain como canal de aquisição | A partir de M2 |
| **Custo de aquisição via Medbrain** | Eficiência vs outros canais | A partir de M2 |
| **Engagement não-aluno** | Viabilidade de monetização stand-alone | A partir de M2 |
| **Willingness-to-pay** | Validação de preço para stand-alone | Pesquisa qualitativa M3 |

---

## Escopo MVP

### Features Core (Paridade Funcional com n8n)

| Feature | Descrição | Justificativa |
|---------|-----------|---------------|
| **Q&A Médico com Tool Use** | Arquitetura Tool Use com Claude SDK nativo substituindo o fluxo n8n | Core do produto — toda interação passa por aqui |
| **RAG Médico (Pinecone)** | Busca vetorial na base de conhecimento Medway com citações de fontes | Diferenciador #1: confiança via referências verificáveis |
| **Busca Web com Citações** | Tool de busca web para complementar a base própria com fontes externas | Cobertura de temas fora da base curada |
| **Transcrição de Áudio** | Processamento de mensagens de voz via OpenAI Whisper | Feature existente, essencial para UX no WhatsApp |
| **Análise de Imagens** | Processamento de imagens médicas via Vision | Feature existente, diferencial clínico |
| **Bulas de Medicamentos** | Tool especializada para consulta de bulas | Feature existente, alta demanda no plantão |
| **Calculadoras Médicas** | Tools de cálculos clínicos de beira de leito | Feature existente, valor direto no plantão |
| **Quiz / Prática Ativa** | Tool de geração de questões para estudo ativo | Feature existente, engajamento |
| **Identificação Aluno vs Não-Aluno** | Diferenciação de features baseada em dados da plataforma Medway | Regra de negócio existente |
| **Histórico de Conversa** | Persistência de conversas no Supabase | Feature existente, continuidade de contexto |
| **Rate Limiting** | Controle de uso via Redis | Proteção operacional existente |

### Adições MVP (Simples + Alto Valor)

| Feature | Descrição | Justificativa |
|---------|-----------|---------------|
| **Feedback 👍/👎** | Reply Buttons do WhatsApp após respostas para captura de satisfação | Fecha o loop de qualidade — sem isso, não sabemos se as respostas estão boas |
| **CTA de Compartilhamento** | Mensagem simples junto ao feedback incentivando compartilhar o contato com colegas | Crescimento orgânico com zero complexidade (texto dentro da sessão ativa) |
| **Cost Tracking por Request** | Logging estruturado de custo em cada chamada Claude/Pinecone/Whisper | Transforma custo de caixa preta em dado visível para decisão |
| **Prompt Caching** | Configuração nativa do Claude SDK para cache de system prompts | Redução de custo e latência sem desenvolvimento adicional |
| **Observabilidade (Langfuse)** | Instrumentação básica de traces, latência e erros em cada request | Visibilidade operacional desde o dia 1 — base para todas as métricas |

### Estratégia de Migração (MVP)

- **Padrão Strangler Fig:** Migração gradual sem downtime
- **Fase 1 — Shadow Mode:** Código novo recebe requests em paralelo, respostas descartadas, comparação de qualidade
- **Fase 2 — Rollout Gradual:** 5% → 25% → 50% → 100% do tráfego no código novo
- **Fase 3 — Code Primary:** n8n desligado, código próprio assume 100%
- **Critério de avanço:** Métricas de qualidade e latência iguais ou superiores ao n8n em cada fase

### Fora do Escopo MVP

| Feature | Fase Planejada | Motivo do Adiamento |
|---------|---------------|---------------------|
| Onboarding contextualizado | M1.5 | Gera valor, mas não é blocker para migração |
| NPS in-chat periódico | M1.5 | Depende de volume de dados pós-migração |
| Dashboard para equipe Medway | M1.5 | Dados coletados no MVP, visualização depois |
| Memória de longo prazo / personalização | M2 | Complexidade alta, requer design de schema e UX |
| Follow-ups proativos (Reply Buttons) | M2 | Requer template messages aprovados + compliance WhatsApp |
| Mensagens proativas de compartilhamento | M2 | Fora da sessão ativa = template messages + risco compliance |
| Detecção de alucinação automatizada | M2 | Pipeline batch com Haiku, depende de volume de dados |
| Relatório de lacunas do RAG | M2 | Automação complexa, depende de dados de feedback |
| Busca de aulas/materiais da plataforma Medway | M2 | Integração com API da plataforma, escopo próprio |
| Quiz com spaced repetition | M3 | Feature sofisticada, depende de memória de longo prazo |
| Desafio diário / calendário | M3 | Depende de mensagens proativas + personalização |
| Features de produto stand-alone | M3 | Depende de validação de mercado e dados de engagement |

### Critérios de Sucesso do MVP

| Critério | Métrica | Target |
|----------|---------|--------|
| **Paridade funcional** | 100% das features n8n replicadas | Sim/Não |
| **Zero downtime** | Nenhuma interrupção durante migração | 0 incidentes |
| **Qualidade ≥ n8n** | Comparação de respostas Shadow Mode | Qualidade igual ou superior |
| **Latência aceitável** | P95 tempo de resposta texto | < 8s |
| **Feedback ativo** | Taxa de resposta nos Reply Buttons | > 10% das mensagens |
| **Custo visível** | Cost tracking operacional funcionando | Custo por conversa mensurável |
| **Observabilidade** | Traces completos no Langfuse | 100% dos requests rastreados |

### Riscos e Constraints

| Risco/Constraint | Impacto | Mitigação |
|-----------------|---------|-----------|
| **Compliance WhatsApp Business API** | Mudanças nas regras da Meta podem afetar mensagens proativas e templates | Monitorar políticas da Meta; manter mensagens de compartilhamento dentro da sessão ativa no MVP; validar templates antes de M2 |
| **Qualidade da migração** | Respostas do código novo podem ser inferiores ao n8n | Shadow Mode com comparação automatizada antes de rollout |
| **Custo Claude em escala** | Custo por request pode ser maior que o esperado | Prompt caching desde o MVP + cost tracking para decisão rápida |
| **Dependência de APIs externas** | Whisper, Pinecone, WhatsApp API podem ter indisponibilidade | Circuit breakers, retry with backoff, fallbacks onde possível |

### Visão Futura (Detalhada)

Se o MVP for bem-sucedido, o mb-wpp evolui em três ondas:

#### M1.5 — Quick Wins (pós-migração imediata)

Capitalizar a nova arquitetura com melhorias rápidas que o n8n não permitia.

| Feature | Descrição | Valor Esperado |
|---------|-----------|----------------|
| **Onboarding Contextualizado** | Mensagem de boas-vindas personalizada na primeira interação — sem formulário, sem fricção. Detecta se é aluno ou não-aluno e adapta a mensagem. Princípio fricção zero do brainstorming. | Primeira impressão profissional, orienta o usuário sobre o que o Medbrain pode fazer |
| **NPS In-Chat** | Pesquisa de satisfação periódica (a cada 30-50 interações) via Reply Buttons dentro da sessão ativa. Pergunta simples: "De 0-10, quanto você recomendaria o Medbrain?" | Métrica de satisfação geral para decisões estratégicas — complementa o feedback 👍/👎 pontual |
| **Dashboard Básico (Equipe Medway)** | Visualização dos dados já coletados no MVP: custo por conversa, volume de uso, taxa de feedback, latência, erros. Pode ser Langfuse dashboard ou Metabase simples sobre Supabase. | Equipe de produto e gestão tomam decisões com dados reais, não intuição |
| **Logging de Lacunas do RAG** | Registrar queries onde o RAG retorna score abaixo do threshold — sem automação de relatório ainda, apenas persistência dos dados para análise futura | Base de dados para o relatório automatizado do M2, custo quase zero |

#### M2 — Diferenciação (3-6 meses)

Features que tornam o Medbrain significativamente superior ao ChatGPT para medicina.

| Feature | Descrição | Valor Esperado |
|---------|-----------|----------------|
| **Memória de Longo Prazo** | Persistência de contexto entre sessões — o Medbrain lembra o que o aluno já perguntou, seus temas de interesse, nível de conhecimento. Schema no Supabase com summarização periódica. | Experiência significativamente superior ao ChatGPT — "ele me conhece" |
| **Personalização de Respostas** | Adaptar profundidade, linguagem e referências com base no perfil do usuário (ano do curso, especialidade, histórico de interações) | Respostas mais relevantes, menos reformulações, maior satisfação |
| **Follow-ups Proativos** | Reply Buttons pós-resposta como "Quer praticar com questões sobre esse tema?" ou "Quer se aprofundar?" — requer template messages aprovados pela Meta | Cria loop de hábito, aumenta profundidade de sessão e retenção |
| **Mensagens Proativas de Compartilhamento** | Mensagens programadas (fora da sessão) incentivando o aluno a indicar colegas — com controle de frequência para evitar spam | Crescimento orgânico escalável, mas precisa de compliance WhatsApp validado |
| **Detecção de Alucinação (Batch)** | Pipeline automatizado com Haiku avaliando amostragem de respostas — compara resposta do Medbrain vs fontes citadas, flagging de inconsistências | Qualidade mensurável e auditável, redução de risco reputacional |
| **Relatório de Lacunas do RAG** | Dashboard automático com top 20 temas mais perguntados sem boa cobertura na base, gerado semanalmente a partir dos logs do M1.5 | Equipe de curadoria prioriza criação de conteúdo com dados reais, não suposição |
| **Busca de Aulas/Materiais Medway** | Tool que consulta API da plataforma Medway para recomendar aulas, resumos e materiais específicos contextualizados à dúvida do aluno | Diferenciador exclusivo para alunos Medway, impossível de copiar por concorrentes |
| **Métricas Estratégicas Ativas** | Começar a medir conversão não-aluno → aluno, CAC via Medbrain, engagement comparativo aluno vs não-aluno | Dados para decisão de monetização e viabilidade stand-alone |

#### M3 — Produto Fenomenal (6-12 meses)

Evolução para produto potencialmente stand-alone — o Medbrain deixa de ser apenas um canal da Medway e se torna um produto de referência no mercado médico.

| Feature | Descrição | Valor Esperado |
|---------|-----------|----------------|
| **Quiz com Spaced Repetition** | Sistema de revisão espaçada baseado nas interações do aluno — o Medbrain identifica temas fracos e propõe revisão no timing ideal (Leitner/SM-2) | Retenção de conhecimento comprovadamente superior, diferenciador pedagógico forte |
| **Desafio Diário / Calendário** | Questão diária contextualizada ao estágio do aluno, com streak tracking e gamificação leve — gera hábito de uso recorrente | Loop de hábito consolidado, aumento significativo de DAU e retenção D7/D30 |
| **Estudo Guiado por Tema** | Jornadas de estudo estruturadas — o Medbrain guia o aluno por um tema do básico ao avançado ao longo de várias sessões, com checkpoints e quiz | Transformação de ferramenta de Q&A em plataforma de estudo ativo |
| **Pesquisa de Willingness-to-Pay** | Pesquisa qualitativa com não-alunos para validar interesse e faixa de preço para produto stand-alone | Dados concretos para decisão de monetização independente |
| **Preparação Stand-Alone** | Separação de features exclusivas Medway vs features universais, modelo de pricing, landing page, fluxo de assinatura | Viabilidade de receita independente, Medbrain como produto próprio |
| **Analytics Avançado** | Dashboards de engagement por cohort, predição de churn, scoring de qualidade por tema, ROI por feature | Decisões de produto data-driven em nível profissional |
