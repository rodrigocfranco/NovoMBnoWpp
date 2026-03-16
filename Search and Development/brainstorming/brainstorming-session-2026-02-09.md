---
stepsCompleted: [1, 2, 3, 4]
inputDocuments: []
session_topic: 'Potencializar o Medbrain no WhatsApp - tutor médico via WhatsApp da Medway'
session_goals: 'Melhorar fluxo atual, avaliar migração para código, novas funcionalidades fenomenais, insights e discussão estratégica'
selected_approach: 'ai-recommended'
techniques_used: ['Assumption Reversal', 'Cross-Pollination', 'Six Thinking Hats']
ideas_generated: 40+
session_active: false
workflow_completed: true
technique_execution_complete: true
context_file: ''
---

# Brainstorming Session Results

**Facilitator:** Rodrigo Franco
**Date:** 2026-02-09

## Session Overview

**Topic:** Potencializar o Medbrain no WhatsApp
**Goals:** Melhorar fluxo atual, avaliar migração para código, novas funcionalidades fenomenais, insights e discussão estratégica

### Session Setup

- **Sistema atual:** Arquitetura n8n com 116 nodos — tutor médico via WhatsApp (Medway)
- **Stack:** WhatsApp Business API, Claude Sonnet 4, Pinecone (RAG), Redis (memória/buffer/rate-limit), Supabase (histórico), MCP Server, OpenAI Whisper/Vision
- **3 caminhos:** Aluno+MCP, Aluno sem MCP, Não-aluno
- **Funcionalidades:** Dúvidas médicas (busca dupla PT-BR+EN), busca de aulas, quiz, análise de imagem, transcrição de áudio, histórico de dúvidas, classificador anti-jailbreak
- **Ambição:** Transformar de bom em fenomenal

## Technique Selection

**Approach:** AI-Recommended Techniques
**Analysis Context:** Sistema existente funcional que precisa ser elevado a outro nível

**Recommended Techniques:**

- **Assumption Reversal:** Desafiar cada premissa arquitetural e de produto do sistema atual para revelar oportunidades escondidas
- **Cross-Pollination:** Importar inovações de outros domínios (Duolingo, Spotify, gaming, ChatGPT) para o contexto de tutor médico no WhatsApp
- **Six Thinking Hats:** Avaliar todas as ideias com 6 perspectivas complementares para decisões equilibradas

**AI Rationale:** Sequência de dentro para fora — desafiar premissas existentes → importar inovação externa → avaliar holisticamente. Perfeita para produto existente que precisa de salto qualitativo.

## Technique Execution: Assumption Reversal

### Premissa #1: "O bot é reativo — só responde quando o aluno manda mensagem"
**Reversão:** E se o Medbrain iniciasse conversas proativamente?

**Gatilhos proativos validados (60+ gatilhos gerados, filtrados por viabilidade):**

**Comportamentais:**
- Detectar padrões de horário e enviar mensagem no momento certo
- Identificar abandono de conversa e retomar dias depois
- Perceber aumento de frequência (véspera de prova) e oferecer apoio
- Notar mudança de tema abrupta e perguntar se precisa de ajuda

**Temporais:**
- Bom dia com dica médica contextualizada
- Resumo semanal de atividade
- Lembretes de estudo baseados em padrões do usuário

**Aprendizado:**
- Detectar confusão/dúvidas repetidas e oferecer explicação alternativa
- Quiz precisa de banco de questões Medway (restrição identificada)

**Social/Comunidade:**
- "Outros alunos perguntaram sobre X esta semana"
- Trending topics médicos na comunidade

**Conteúdo/Atualizações:**
- Novo conteúdo relevante ao perfil do aluno
- Alertas de guidelines atualizados

**Emocional:**
- Detectar frustração e ajustar abordagem
- Mensagens motivacionais em períodos difíceis

**Estratégico/Conversão:**
- Para não-alunos: CTAs contextuais para Medway

**Desafio Diário (formato calendário, NÃO gamificação):**
- Uma questão/caso clínico por dia
- Baseado em calendário de estudo, não em pontos/streaks

**Restrições identificadas:**
- ❌ Gamificação no WhatsApp — usuário não gosta
- ❌ Integração profunda com plataforma — requer ação de outros times tech
- ❌ Calendário acadêmico — impraticável (varia por faculdade)
- ✅ Usar apenas dados nativos do WhatsApp para gatilhos

---

### Premissa #2: "O Medbrain é uma ferramenta de Q&A"
**Reversão:** E se fosse um tutor pessoal completo?

**Restrição CRÍTICA:** Medbrain no WhatsApp NÃO PODE conflitar com a plataforma Medway (que já faz tutoria, mentoria, guia de estudos).

**5 Identidades validadas para o Medbrain:**

1. **Amigo Médico no Bolso** — Dúvidas rápidas do dia-a-dia médico, linguagem informal, acessível
2. **Companheiro de Faculdade** — Ajuda com estudos da faculdade (que a plataforma Medway NÃO cobre)
3. **Ponte Inteligente para Plataforma** — Conecta o aluno ao conteúdo certo dentro da Medway
4. **Parceiro de Prática Ativa** — Casos clínicos interativos, quizzes, simulações
5. **Aliado do Plantão** — Para médicos em serviço: bulas, protocolos, códigos SUS/TUSS/CID

**Aliado do Plantão — Exploração profunda:**

**Público:** Qualquer médico (não apenas alunos) — funciona como lead generation para Medway

**Framework de segurança (SAFE vs DANGEROUS):**
- ✅ SAFE: Lookup de bulas, decodificação de códigos, calculadoras de beira de leito, protocolos express, checklists de procedimento, suporte administrativo, interação medicamentosa, suporte a prescrição
- ❌ DANGEROUS: Diagnóstico por imagem, decisões clínicas definitivas, qualquer coisa que substitua julgamento médico
- ⚠️ Warnings obrigatórios: "Esta informação é para referência rápida. Sempre confirme com fontes oficiais e use seu julgamento clínico."

---

### Premissa #3: "A resposta é sempre texto formatado"
**Reversão:** E se o Medbrain usasse TODO o potencial da API do WhatsApp?

**Descoberta CRÍTICA:** WhatsApp baniu chatbots de IA de propósito geral desde 15/jan/2026. Medbrain está em zona cinzenta — equipe ciente e assumindo o risco.

**Recursos da API WhatsApp mapeados:**
- Mensagens de texto (4096 chars, formatação markdown)
- Imagens (5MB, JPEG/PNG), Áudio (16MB, OGG/Opus), Vídeo (16MB, MP4), Documentos (100MB, PDF)
- Reply Buttons (máx 3), List Messages (máx 10 itens)
- **WhatsApp Flows** — mini-apps com até 10 telas: TextInput, TextArea, Dropdown, RadioButtons, CheckboxGroup, DatePicker, OptIn, Image, EmbeddedLink
- Reações, Location, Contacts

**Cases validados:**

**WhatsApp Flows:**
- Quiz interativo multi-tela (não mais texto puro)
- Anamnese guiada para casos clínicos
- Formulário de perfil do aluno (onboarding)
- Triagem de dúvidas complexas

**TTS (Text-to-Speech):**
- Resumos em áudio para ouvir no carro/transporte
- Pronúncia de termos médicos

**PDF dinâmico:**
- Resumos de estudo personalizados
- Protocolos de plantão para consulta offline
- Histórico de dúvidas compilado

**Banco de vídeos:**
- Procedimentos médicos gravados em vídeo
- Vídeos curtos demonstrativos enviados sob demanda

**Imagens da base de conhecimento:**
- Usar imagens já existentes na base Medway (não gerar com IA — custo alto)
- Necessidade identificada: melhor curadoria e descrição das imagens existentes
- Pipeline de extração+descrição de imagens para RAG visual

---

### Premissa #4: "A memória é de 30 minutos / 10 mensagens"
**Reversão:** E se o Medbrain lembrasse tudo sobre o usuário para sempre?

**Pesquisa de mercado realizada:**
- Mem0: 26% accuracy boost, 91% latency reduction, 90% token reduction — mas dados sensíveis demais para terceirizar
- ChatGPT 4-layer architecture: referência do mercado
- MemGPT/Letta: overcomplexo para WhatsApp
- Knowledge Graphs: overengineering para o caso

**Arquitetura recomendada — 3 Camadas Híbridas:**

| Camada | Storage | Conteúdo | Custo |
|--------|---------|----------|-------|
| **Perfil Persistente** | Supabase | Especialidade, ano, preferências, contexto | ~$0.003/conversa |
| **Resumo de Sessão** | Supabase | Últimos 3-5 resumos de conversa, tags de tópicos | ~$0.005/conversa |
| **Contexto Atual** | Redis | Buffer mensagens (pode aumentar para 60min/15msg) | Zero (já existe) |

**Custo total: ~$0.01/conversa. Para 1000 conversas/dia: ~$10-20/mês adicional.**

**Decisão pendente:** Definir COM CALMA o que de fato guardar na memória — cada campo deve responder "o que muda na resposta do bot se ele souber isso?" Se a resposta for "nada", não guarda.

**Viabilidade:** ALTA — já possuem toda a infra necessária (Supabase + Redis + Pinecone).

---

### Premissa #5: "Um único prompt gigante resolve tudo"
**Reversão:** E se houvesse múltiplos agentes especializados?

**Pesquisa de mercado reveladora:**
- 41-86.7% dos sistemas multi-agentes FALHAM em produção
- Cognition AI (Devin): publicou "Don't Build Multi-Agents"
- "17x error trap" — erros se multiplicam entre agentes
- Anthropic recomenda: "Start simple. Add multi-step only when simpler solutions fall short."

**Primeira proposta (Router + Especialistas) — DESCARTADA:**
- Problema identificado por Rodrigo: mensagens com múltiplas intenções quebram o classificador
- Ex: "dose de noradrenalina em bula + indicações + uso em sepse + quiz" = 4 intenções

**Proposta FINAL validada — Tool Use Architecture:**

Em vez de múltiplos agentes, **um agente único com múltiplas ferramentas (tools)**. O Claude DECIDE quais tools chamar (0, 1 ou várias em paralelo).

**Arquitetura gold standard (pesquisa profunda na documentação Anthropic):**

```
Webhook WhatsApp
    → Pré-processamento (código): rate limit, buffer, Whisper, Vision, anti-jailbreak, perfil
    → Claude Sonnet + Tool Use (strict: true)
        Tools: buscar_base_medica, buscar_bula, buscar_aula, gerar_quiz,
               buscar_codigo, buscar_protocolo, calcular_dose, buscar_imagem
    → Tool Runner SDK Anthropic (loop automático, error handling, streaming)
    → Pós-processamento (código): formato WhatsApp, mídia, memória async
```

**Regras de produção identificadas:**
1. **Descrições de tools detalhadas** (3-4 frases mínimo) — fator #1 de sucesso segundo Anthropic
2. **`strict: true`** em todas as tools — garante schema validation
3. **Parallel tool calls** — Claude 4 models chamam múltiplas tools em paralelo automaticamente
4. **Prompt caching** — cachear system prompt + tools (economia de até 90% no input)
5. **Error handling graceful** — tool falha → Claude adapta resposta com conhecimento próprio
6. **Seleção dinâmica de tools por contexto** — plantão recebe tools diferentes de estudo
7. **Observabilidade** — monitorar latência, tool errors, custo/conversa, satisfação

**Custo estimado: $0.005-0.02/conversa (mais barato, mais rápido e mais confiável que o monolito atual)**

**Frameworks (LangGraph, CrewAI, AutoGen) — DESCARTADOS:** Anthropic recomenda usar SDK direto, sem abstração. Frameworks "add abstraction layers that obscure underlying prompts and responses."

---

### Premissa #6: "O n8n com 116 nodos é a melhor forma de orquestrar"
**Reversão:** E se o n8n fosse o maior gargalo, não a solução?

**Limitações identificadas do n8n para o futuro do Medbrain:**
- Tool Runner SDK Anthropic (parallel calls, strict mode, prompt caching) → impossível no n8n
- Memória de 3 camadas com extração async → difícil no n8n
- Seleção dinâmica de tools por perfil → gambiarra com if/else visual
- Testes automatizados → inexistente no n8n
- Observabilidade granular → limitada no n8n
- Todas as ideias desta sessão são significativamente mais fáceis em código

**Preocupação do Rodrigo:** Sistema n8n funciona perfeitamente hoje. Precisa de segurança na migração: bem documentada, Git, organização, garantia de funcionamento, capacidade de troubleshooting.

**Estratégia de migração validada — Strangler Fig Pattern:**

1. **Shadow Mode (1-2 semanas):** Código novo roda em paralelo, recebe mesmas msgs, mas NÃO envia resposta. Apenas loga. Compara outputs com n8n.
2. **Rollout Gradual (3-4 semanas):** Feature flag por usuário. Começa 5% → 10% → 25% → 50% → 100%. Fallback automático pro n8n se der erro.
3. **Código Principal (ongoing):** 100% no código, n8n preservado como backup 30 dias, depois remove.

**Garantias de segurança:**
- Git desde dia zero com estrutura organizada (src/, tests/, scripts/)
- Testes com mensagens REAIS extraídas do Supabase (500-1000 fixtures)
- Feature flags com rollback em 1 segundo
- Observabilidade completa (cada request logado com msg, tools, resposta, latência, custo)
- Docker + CI/CD

**Cronograma estimado:** ~6-8 semanas até 100% migrado, com zero downtime.

---

### Premissa #7: "O bot atende 100% sozinho, sem humano"
**Reversão:** E se houvesse human handoff?

**Resultado:** DESCARTADA — plataforma Medway já oferece contato humano. Medbrain só precisa saber direcionar para a plataforma quando necessário (já coberto pela identidade "Ponte Inteligente").

---

### Premissa #8: "O primeiro contato é genérico"
**Reversão:** E se o onboarding fosse a melhor experiência do produto?

**Proposta inicial:** WhatsApp Flow com formulário de perfil (área de interesse, ano, contexto).

**DESCARTADA por Rodrigo — princípio de fricção zero:**
- "Área de interesse" → limitaria o usuário? Se escolhe cardiologia, não pode perguntar pneumologia?
- "Está em plantão?" → implica que não pode fazer perguntas de plantão depois?
- Cada pergunta que não muda comportamento do bot = fricção pura

**Decisão FINAL — Onboarding zero-friction:**
- Lookup automático: já sabe se é aluno Medway pelo número de telefone
- Mensagem de boas-vindas simples e convidativa, sem formulário
- Perfil se constrói organicamente pela memória (Premissa #4)
- Flow de personalização opcional só se surgir funcionalidade que exija dados prévios

**Princípio validado:** Só perguntar ao usuário o que de fato muda o comportamento do bot. Se a resposta for "nada muda", não perguntar.

---

### Premissa #9: "Não sabemos se as respostas são boas ou ruins"
**Reversão:** E se houvesse um ciclo virtuoso de avaliação e melhoria contínua?

**3 Camadas de feedback validadas:**

**Camada 1 — Feedback explícito (baixo esforço):**
- Reply Buttons após respostas: [👍 Ajudou] [👎 Não ajudou] [📝 Corrigir]
- Se "Corrigir" → campo pra dizer o que estava errado
- Dados → Supabase → dashboard de qualidade

**Camada 2 — Feedback implícito (zero esforço):**
- Usuário reformulou mesma pergunta → resposta anterior ruim
- "?" ou "não entendi" → resposta confusa
- Parou de responder → possível frustração
- Voltou com mesma dúvida no dia seguinte → não resolveu

**Camada 3 — Avaliação automatizada (batch):**
- Amostra periódica de conversas do Supabase
- LLM avaliador (Haiku, barato): "Resposta correta, completa, útil? Score 1-5"
- Identifica padrões de respostas fracas por tema
- Relatório semanal: "Temas com baixa qualidade: [X, Y, Z]"
- Alimenta melhoria do RAG (curadoria direcionada)

**Adição do Rodrigo — Feedback proativo periódico:**
- Mensagem automática a cada 30-50 interações (por uso, NÃO por calendário)
- Formato simples: Reply Buttons [⭐ Excelente] [👍 Boa] [👎 Pode melhorar]
- Se negativo → texto livre pra entender o problema
- Máximo 1 feedback a cada 30-50 interações (não chatear)
- Possibilidade de NPS detalhado via WhatsApp Flow a cada ~100 interações
- Alimenta dashboard de satisfação do produto

**Resultado:** Ciclo virtuoso — feedback → identifica fraquezas → melhora RAG/prompts → qualidade sobe → feedback melhora

---

### Premissa #10: "A base de conhecimento (RAG) é estática — alguém curou, subiu, e pronto"
**Reversão:** E se a base de conhecimento evoluísse continuamente de forma inteligente?

**Auto-diagnóstico de lacunas:**
- Quando RAG retorna score baixo → logar: query, score, tema estimado
- Dashboard semanal: "Top 20 perguntas sem boa resposta na base"
- Direciona curadoria com dados reais em vez de adivinhação

**Feedback loop alimentando RAG (conecta com Premissa #9):**
- Resposta com 👎 → marca chunk do Pinecone como "baixa qualidade"
- "Corrigir" + correção do aluno → ticket de revisão para curadoria
- Avaliação automatizada identifica padrões: "Farmacologia score médio 2.8/5" → priorizar

**Enrichment automático:**
- Claude responde sem tool call + recebe 👍 → candidata para inclusão na base (fila de revisão humana, nunca automático)

**Versionamento de conhecimento:**
- Metadata no Pinecone: `last_updated`, `source`, `quality_score`, `usage_count`
- Chunks nunca consultados → revisar ou remover
- Alto uso + baixo feedback → prioridade de melhoria

**Resultado:** Base de conhecimento se transforma de repositório passivo em organismo vivo que melhora com cada interação.

---

### Premissa #11: "O anti-jailbreak é um classificador separado que roda antes de tudo"
**Reversão:** E se a segurança fosse uma camada integrada e mais inteligente?

**Problema do classificador binário atual:**
- Falsos positivos: bloqueia perguntas legítimas que parecem estranhas
- Falsos negativos: ataques sofisticados passam
- Custo fixo: roda em TODA mensagem, mesmo "oi" ou "obrigado"

**Abordagem integrada multi-camada (com Tool Use Architecture):**

**Camada 1 — Filtro rápido (código, pré-Claude):**
- Regex/heurística para ataques óbvios (patterns conhecidos)
- Custo: zero (roda em código puro)
- Captura ~70% dos ataques triviais

**Camada 2 — System prompt robusto:**
- Claude com instruções claras de limites
- O próprio Claude é o melhor filtro de jailbreak — treinado para isso

**Camada 3 — Monitoramento async (pós-resposta):**
- Amostragem de conversas suspeitas
- Alerta para equipe se padrão de ataque detectado
- Bloqueio automático de número se confirmado

**Guardrails médicos adicionais:**
- Não dar diagnósticos definitivos
- Disclaimers em situações de risco
- Detectar emergências → direcionar para SAMU/192

**Vantagem:** Elimina nó do pipeline, reduz latência, segurança mais robusta.

---

### Premissa #12: "O rate limit é igual para todos — X mensagens por minuto"
**Reversão:** E se o rate limit fosse inteligente e adaptativo?

**Por perfil:**
- Aluno Medway ativo → limite mais generoso
- Não-aluno (trial) → mais restrito
- Aluno em véspera de prova (detectado por padrão) → temporariamente elevado

**Por contexto:**
- Conversa produtiva sequencial → não limitar
- Spam/repetição → limitar mais rápido
- Mensagens curtas ("ok", "entendi") → não contar

**Por custo (budget diário):**
- Em vez de limitar mensagens, limitar custo em dólar por usuário/dia
- Budget diário por aluno: ex. $0.50 (~25-100 interações dependendo da complexidade)

**Degradação elegante:**
- Em vez de bloquear → usar modelo mais barato (Haiku) para perguntas simples
- Ou reduzir tools disponíveis (só texto, sem RAG)
- Usuário nunca fica completamente sem resposta

---

### Premissa #13: "O custo é uma caixa preta — sabemos o total da fatura mas não o custo por usuário"
**Reversão:** E se cada interação tivesse custo rastreado com precisão cirúrgica?

**Adição de Rodrigo:** Ferramenta hoje é gratuita para todos. Precisam rastrear custos detalhadamente para futuras decisões de cobrança e limites.

**Cost Tracking por request:**

| Métrica | Como capturar | Onde logar |
|---------|--------------|------------|
| Input/Output tokens | Response metadata Claude | Supabase |
| Cache hits | Response metadata (prompt caching) | Supabase |
| Tool calls | Contar tools por request | Supabase |
| Pinecone queries | Contar buscas RAG | Supabase |
| Whisper (áudio) | Flag se teve transcrição | Supabase |
| Vision (imagem) | Flag se teve análise | Supabase |
| Latência total | Timestamp início → fim | Supabase |

**Tabela `request_costs` no Supabase:**
```
user_id | timestamp | input_tokens | output_tokens | cache_read_tokens |
tools_called | pinecone_queries | whisper_used | vision_used |
total_cost_usd | latency_ms | model_used
```

**Dashboard de decisão estratégica:**
- Custo por usuário (diário, semanal, mensal)
- Custo por funcionalidade (dúvida médica vs bula vs quiz vs caso clínico)
- Top outliers (investigar: uso legítimo ou abuso?)
- Distribuição P50/P90/P99 de custos por conversa
- Comparativo aluno vs não-aluno

**Valor para o negócio:**
1. Decisão de pricing com dados reais — não chutar valor
2. Identificar funcionalidades caras → otimizar
3. Detectar abuso (usuário $50/mês = fora do escopo)
4. Justificar investimento para diretoria
5. Modelar cenários de monetização
6. Otimização contínua (prompt caching savings, model downgrade savings)

**Implementação:** Trivial na arquitetura Tool Use — response do Claude já retorna `usage.input_tokens` e `usage.output_tokens`. Basta logar. Custo do tracking: praticamente zero (~1 INSERT/request no Supabase).

---

## Technique Execution: Cross-Pollination

### Domínio #1: Duolingo — Engajamento educacional

**Ideias exploradas:**
- Bite-sized learning ("Pílula do dia") — micro-aprendizado em 3 mensagens curtas
- Dificuldade adaptativa — ajustar complexidade das perguntas baseado em desempenho
- Recall ativo ("Explica com suas palavras") — aluno escreve explicação, Claude avalia e corrige
- Notificações provocativas com dados reais

**Análise de viabilidade do broadcast diário:**
- Custo de template Marketing no Brasil: ~US$ 0,0625/mensagem
- 5.000 alunos/dia = ~US$ 9.375/mês SÓ de taxa Meta
- Portfolio Pacing: WhatsApp não derruba, mas monitora feedback entre lotes

**DECISÃO: Broadcast diário DESCARTADO por custo-benefício desfavorável.**

**Abordagem validada — conteúdo embutido na experiência reativa:**
- Mensagens de serviço (dentro da janela de 24h) = GRATUITAS
- Pílulas embutidas na resposta: "Aliás, você sabia que [dado relacionado ao tema]?"
- Prática ativa (quiz, casos) embutida na conversa natural
- Recall ativo e dificuldade adaptativa funcionam perfeitamente no modo reativo
- Reengajamento de inativos (15-30 dias): UMA mensagem direcionada (volume pequeno, custo baixo)

**Princípio validado:** Investir em fazer a experiência reativa ser tão boa que o aluno volta sozinho, em vez de gastar com broadcasts.

---

### Domínio #2: Spotify — Personalização e descoberta

**Ideias validadas:**
- "Discover Weekly médico" — sugerir temas relacionados que o aluno ainda não explorou (dentro da janela 24h, custo zero)
- "Medbrain Wrapped" — retrospectiva mensal/semestral em PDF: temas explorados, pontos fortes, áreas a melhorar
- Detecção de "mood de estudo" — adaptar profundidade e formato da resposta pelo padrão de mensagens

---

### Domínio #3: ChatGPT — Experiência conversacional com IA (exploração profunda)

**Voice Mode bidirecional:**
- Áudio → Whisper → Claude → TTS → áudio de volta
- Conversa 100% por voz, sem digitar — perfeito para plantão, carro, transporte
- Custo TTS: ~$0.0075/resposta (OpenAI TTS)
- Opt-in: aluno escolhe texto ou áudio

**Organização por tema (caderno automático):**
- Bot tagga cada interação por tema (cardiologia, farmaco, etc.) automaticamente
- Tags armazenadas no Supabase junto com resumos de sessão
- Aluno pergunta "O que já discutimos de cardio?" → resumo organizado por data e subtema
- "Me faz um PDF de tudo que estudei de cardio" → material personalizado
- Valor: caderno de estudos que se constrói sozinho

**Calculadoras médicas expandidas (Aliado do Plantão):**
- Função renal: Cockcroft-Gault, CKD-EPI, MDRD, correção de dose
- Scores: Glasgow, SOFA/qSOFA, APACHE II, Wells, CHA₂DS₂-VASc, HAS-BLED, CURB-65, Child-Pugh/MELD, HEART
- Correções: sódio, cálcio, déficit água livre, osmolaridade, anion gap, gradiente A-a
- Doses: mg/kg, superfície corporal, mcg/kg/min → ml/h, protocolos de infusão
- Cada cálculo com interpretação clínica do resultado

**Modos do Medbrain (ativação automática ou manual):**

| Aspecto | Modo Estudo | Modo Plantão | Modo Revisão |
|---------|-------------|--------------|--------------|
| Tom | Didático, detalhado | Direto, objetivo | Pergunta-resposta |
| Tamanho | Respostas longas | Respostas curtas | Flashcard |
| Extras | Exemplos, explicações | Só essencial, protocolo | Quiz ao final |
| Formato | Texto + PDF | Bullets, números | Reply Buttons |
| Ativação | Default / "modo estudo" | "modo plantão" / detectado | "modo revisão" / "me testa" |

**Canvas / Conteúdo estruturado:**
- Respostas complexas (tabelas, protocolos, fluxogramas) → PDF dinâmico em vez de texto puro
- Resumos de estudo construídos ao longo da conversa → PDF personalizado sob demanda

**Suggested follow-ups com Reply Buttons:**
- 2-3 perguntas relacionadas ao final de cada resposta
- Reduz fricção, aumenta engajamento e profundidade

**Prioridade de busca corrigida por Rodrigo:**
1. RAG Pinecone (conteúdo curado Medway) → fonte confiável
2. Perplexity API (busca web com citações) → fontes rastreáveis (PubMed, guidelines)
3. Conhecimento Claude (último recurso) → disclaimer obrigatório: "sem fonte específica"

**Busca com citações visíveis:**
- Mostrar DE ONDE veio a resposta: "Segundo Harrison 21a ed., cap. 298..." ou "Aula X do Prof. Y (Medway)"
- Metadata do chunk no Pinecone deve incluir: fonte, autor, capítulo
- Gera confiança — aluno sabe que não é alucinação

**Transparência de memória:**
- "O que você sabe sobre mim?" → bot lista perfil construído organicamente
- Aluno pode corrigir: "Na verdade, já me formei"

---

### Domínio #4: Gaming — Mecânicas de engajamento sem gamificação

**Progressão de maestria (não de pontos):**
- Bot percebe e verbaliza evolução: "Suas perguntas de farmaco evoluíram muito!"
- Reconhecimento genuíno > pontuação artificial

**"Boss fights" → Casos clínicos complexos:**
- Após várias perguntas sobre um tema → oferecer caso integrador multi-etapa
- Via WhatsApp Flow: apresentação → hipóteses → exames → diagnóstico → conduta

**"Side quests" → Curiosidades médicas naturais:**
- Inserir curiosidades relevantes naturalmente na conversa
- Torna experiência mais humana e menos robótica

---

### Domínio #5: Netflix — Curadoria e experiência de conteúdo

**"Continue estudando":**
- Bot retoma contexto ao retornar: "Da última vez a gente discutia sepse e qSOFA. Quer continuar daí?"
- Usa memória de sessão — zero esforço do aluno

**Preview antes de comprometer:**
- Antes de caso clínico ou quiz longo: "Esse caso tem 5 etapas, ~10 min. Quer começar agora ou algo mais rápido?"
- Respeita o tempo do aluno

**Recomendação baseada em padrões coletivos:**
- "Alunos que estudaram IAM também perguntaram sobre trombólise vs angioplastia"
- Dados agregados de todos os alunos → recomendação individual

---

### Domínio #6: Waze — Inteligência contextual

**"Rota alternativa" → Abordagem alternativa:**
- Detecta que aluno está preso (mesma pergunta 3x) → muda abordagem: analogia, exemplo, ou direciona para aula na plataforma

**Indicador de progresso:**
- "Dos 8 temas principais de emergências, a gente já cobriu 5. Faltam: choque, PCR e via aérea difícil."

---

### Domínio #7: Bancos digitais (Nubank) — Transparência e controle

**Notificações de uso (APROVADO por Rodrigo):**
- "Você já usou 35 das suas 50 interações hoje"
- Transparência total sobre consumo — essencial para futuro modelo de cobrança
- Aluno tem controle e visibilidade do próprio uso

**Timeline de atividade (extrato):**
- "Meu histórico" → extrato organizado: interações, temas, quizzes, com datas
- Exportável como PDF

---

### Domínio #8: Uber — Experiência de serviço

**Estimativa antes de começar (APROVADO por Rodrigo):**
- Para funcionalidades pesadas (caso clínico, quiz, resumo PDF): "Gerar esse resumo leva ~30s. Confirma?"
- Gerencia expectativa — aluno não acha que travou

**Rating bidirecional educacional:**
- Bot dá feedback construtivo ao aluno: "Suas perguntas de ECG mostram que domina o básico. Pronto pro avançado?"

**Status em tempo real (APROVADO por Rodrigo):**
- Para buscas demoradas: "Buscando na base Medway... Encontrei! Complementando com fontes atualizadas..."
- WhatsApp API permite typing indicator + mensagens intermediárias de status
- Reduz ansiedade de espera e mostra que o bot está trabalhando

---

## Technique Execution: Six Thinking Hats

### Chapéu Branco — Fatos e Dados

**Fatos confirmados:**
- Sistema n8n 116 nodos funciona em produção
- Stack operacional: Claude Sonnet 4, Pinecone, Redis, Supabase, Whisper, Vision
- WhatsApp baniu chatbots IA de propósito geral (jan/2026) — Medbrain em zona cinzenta, risco aceito pela equipe
- Template Marketing BR: ~US$ 0,0625/msg — broadcast diário inviável
- Mensagens de serviço (dentro de 24h): gratuitas
- Multi-agentes falham 41-86.7% em produção — Tool Use é o caminho validado
- Anthropic recomenda SDK direto sem frameworks
- Prompt caching: até 90% economia em input tokens
- Infra existente suporta memória 3 camadas

**Dados que NÃO temos (precisam ser construídos):**
- Custo atual por conversa (caixa preta sem tracking)
- Taxa de satisfação (sem feedback loop)
- Temas mais perguntados (sem analytics granular)
- Latência média de resposta atual
- % respostas que usam RAG vs conhecimento do modelo

**Contexto organizacional:**
- Time tech será inserido no projeto e treinado sobre a nova arquitetura
- Dados atuais: apenas tabelas brutas no Supabase — precisam de reconstrução completa
- Camada de inteligência e relatórios precisa ser construída do zero

---

### Chapéu Vermelho — Emoção e Intuição

| Ideia | Intuição | Status |
|-------|----------|--------|
| Migração n8n → código | Inevitável. Sem isso, nada do resto acontece. | Consenso |
| Tool Use Architecture | Certo. Pesquisa validou de todos os ângulos. | Consenso |
| Memória 3 camadas | Excitante. Precisa calma pra definir O QUÊ guardar. | Consenso |
| Aliado do Plantão | Potencial ENORME. Killer feature. | Consenso |
| Calculadoras beira de leito | Valor imediato e tangível. | Consenso |
| Modos (estudo/plantão/revisão) | Elegante. Muda percepção do produto. | Consenso |
| Follow-ups Reply Buttons | Quick win. Alto impacto, baixo esforço. | Consenso |
| Voice mode bidirecional | Wow factor. Nice to have, não must have. | Consenso |
| Cost tracking granular | Não é sexy, mas sustenta o negócio. | Must-have |
| Feedback loop + RAG dinâmico | Volante que melhora tudo sozinho. | Consenso |
| Perplexity prioridade 2 | Fontes rastreáveis > "confie em mim". | Consenso |
| Rebuild Supabase/dashboards | Dor necessária. Dados brutos sem inteligência = nada. | Must-have |

---

### Chapéu Amarelo — Benefícios (Top 5 ideias)

1. **Tool Use + Migração:** Desbloqueia tudo. Mais barato, rápido, confiável. Prompt caching pode pagar a migração.
2. **Aliado do Plantão:** Mercado expandido (qualquer médico). Lead generation natural.
3. **Feedback loop + RAG dinâmico:** Ciclo virtuoso — produto melhora sozinho com uso.
4. **Cost tracking + Dashboards:** Decisões de monetização com dados reais. Detecta otimizações.
5. **Modos + Follow-ups:** Experiência percebida muda radicalmente.

---

### Chapéu Preto — Riscos

1. **Migração:** Risco de regressão funcional. Mitigação: Strangler Fig + shadow mode + testes reais.
2. **Responsabilidade médica:** Calculadoras com resultado errado = consequência clínica. Disclaimers obrigatórios + validação por médico.
3. **Complexidade acumulada:** ~40+ ideias. Tentar tudo = não entregar nada. Priorização brutal é essencial.
4. **Rebuild Supabase:** Migração de dados pode perder histórico. Schema novo deve suportar tudo desde o início.
5. **Perplexity como dependência:** Mais um ponto de falha. Mitigação: fallback para Claude com disclaimer.
6. **Sustentabilidade de custo:** Gratuito hoje. Se escalar sem monetização, custo sobe. Decisão não pode demorar.

---

### Chapéu Verde — Combinações Criativas

**"Smart Tutor" mode:**
- Memória + Modos + Follow-ups + Recall ativo + Dificuldade adaptativa = tutor que realmente ensina e acompanha evolução

**"Observatory" — Dashboard unificado:**
- Cost tracking + Feedback + RAG quality + Usage analytics = UM painel com 4 abas
- Decisões de negócio, produto, curadoria e engenharia no mesmo lugar

**Nota de Rodrigo:** Tudo dentro de um mesmo bot/produto. Não separar Plantão como produto isolado — modos do MESMO Medbrain.

---

### Chapéu Azul — Processo e Implementação

**Faseamento final validado (3 Momentos + ciclos):**

**Momento 0 — Prova de Conceito (1 semana):**
- Webhook → Claude + Tool Use com 1 tool (buscar_base_medica) → resposta WhatsApp
- Valida: latência, prompt caching, parallel calls, strict mode, qualidade
- Critério: 20 perguntas reais do Supabase, 80%+ respostas iguais ou melhores que n8n
- Se falhar → pivotar ANTES de investir meses

**Momento 1 — Migração Core (6-8 semanas):**
- Projeto: Git, Docker, CI/CD, estrutura organizada
- Supabase schema novo: desenhado para tudo (cost, memória, feedback, tags)
- Tool Use Architecture: todas as tools existentes
- Segurança: filtro regex + system prompt + guardrails médicos
- Cost tracking: logging de tokens, tools, latência em cada request
- Shadow mode → rollout gradual (5% → 25% → 50% → 100%)
- Critério "pronto": 500+ msgs processadas, 90%+ qualidade igual/superior, zero erros críticos
- NÃO inclui: feedback buttons, follow-ups, status, memória, modos, calculadoras

**Momento 1.5 — Quick Wins (1-2 semanas pós-100%):**
- Follow-up Reply Buttons
- Feedback explícito (👍👎📝)
- Status em tempo real (typing + msgs intermediárias)
- Estimativa antes de operações pesadas
- Notificações de uso
- Citações visíveis nas respostas
- Tudo é mudança no pós-processamento/system prompt, sem risco arquitetural

**Momento 2 — Diferenciação (4-6 semanas):**
- Memória 3 camadas (perfil + resumo + contexto)
- Modos do Medbrain (estudo/plantão/revisão) — tudo no MESMO bot
- Calculadoras médicas (com validação por médico)
- Perplexity como prioridade 2 de busca
- Dashboard Observatory v1

**Momento 3 — Fenomenal (ongoing):**
- Voice mode bidirecional (Whisper + TTS)
- Caderno automático por tema + PDF personalizado
- Dificuldade adaptativa + recall ativo
- RAG dinâmico (auto-diagnóstico de lacunas)
- WhatsApp Flows para quiz/casos clínicos interativos
- Medbrain Wrapped
- Avaliação automatizada (Haiku batch)
- Feedback implícito

**Princípios validados durante a sessão:**
- Só guardar na memória o que muda o comportamento do bot
- Só perguntar ao usuário o que muda o comportamento do bot (fricção zero)
- Investir na experiência reativa em vez de broadcasts caros
- Um bot, tudo dentro — não separar como produtos isolados
- Dados reais antes de decisões (cost tracking, feedback, analytics)
- Disclaimers médicos são obrigatórios, não opcionais

---

## Decisão: Estratégia de Teste — Momento 0

**Abordagem validada: Híbrida em 2 fases**

**Fase 1 (Dias 1-3): Replay do Supabase**
- Extrair últimas ~200 conversas reais do Supabase (perguntas + áudios + imagens)
- Rodar contra o código novo em batch
- Comparar: qualidade da resposta, tools chamadas, latência, custo
- Valida ~80% do necessário sem risco nenhum

**Fase 2 (Dias 4-7): Shadow Mode no webhook**
- Webhook atual continua funcionando normalmente (n8n responde ao aluno)
- Fork assíncrono da mensagem para o código novo
- Código novo processa, loga tudo (resposta, tokens, tools, latência, custo) — NÃO envia resposta ao aluno
- Comparação side-by-side: resposta n8n vs resposta código novo

```
Webhook WhatsApp (atual)
    ├── n8n (responde ao aluno normalmente) ✅
    └── Código novo (processa em shadow, loga, NÃO responde) 📊
```

**Implementação do fork:** HTTP Request node no próprio n8n (POST assíncrono para endpoint do código novo) ou middleware mínimo antes do n8n.

**Vantagens:**
1. Fase 1 dá confiança antes de tocar no webhook de produção
2. Fase 2 dá dados reais sem risco — se o código novo der erro, o aluno nem sabe
3. Coleta métricas de comparação: latência, custo, qualidade lado a lado
4. Valida o cost tracking desde o dia 1 com dados reais
5. Início natural do Strangler Fig Pattern — shadow mode é o primeiro passo da migração

---

## Idea Organization and Prioritization

### Organização Temática

**Tema 1: Arquitetura Core — Tool Use + Migração**
_O alicerce que desbloqueia tudo_

- Tool Use Architecture com SDK Anthropic direto (strict: true, parallel calls)
- Strangler Fig Pattern: shadow mode → rollout gradual → migração completa
- Prompt caching (até 90% economia input tokens)
- Anti-jailbreak multi-camada integrado (regex → system prompt → monitoring async)
- Rate limit inteligente e adaptativo (por perfil, contexto, budget)

**Tema 2: Inteligência e Observabilidade**
_Dados reais para decisões reais_

- Cost tracking granular por request (tabela `request_costs` no Supabase)
- Dashboard "Observatory" unificado (custo + feedback + RAG quality + usage)
- Rebuild Supabase schema (projetado para suportar tudo desde o início)
- Analytics de temas mais perguntados, latência, % RAG vs modelo

**Tema 3: Qualidade de Conteúdo — RAG + Busca**
_Respostas confiáveis com fontes rastreáveis_

- Prioridade de busca: RAG Pinecone → Perplexity API → Claude (com disclaimer)
- Citações visíveis em cada resposta (fonte, autor, capítulo)
- RAG dinâmico: auto-diagnóstico de lacunas + feedback alimentando qualidade
- Versionamento de conhecimento (metadata: quality_score, usage_count, last_updated)

**Tema 4: Experiência Conversacional**
_De chatbot para tutor inteligente_

- Modos do Medbrain: Estudo / Plantão / Revisão (tudo no MESMO bot)
- Follow-up Reply Buttons (2-3 perguntas relacionadas)
- Status em tempo real (typing indicator + mensagens intermediárias)
- Estimativa antes de operações pesadas
- Transparência de memória ("O que você sabe sobre mim?")
- Voice mode bidirecional (Whisper + TTS)

**Tema 5: Memória e Personalização**
_Bot que conhece e acompanha o aluno_

- Memória 3 camadas: Perfil Persistente + Resumo de Sessão + Contexto Atual
- Caderno automático por tema (tags + resumos sob demanda + PDF)
- Dificuldade adaptativa baseada em desempenho
- Detecção de padrões de estudo e "mood"
- "Continue estudando" — retoma contexto automaticamente

**Tema 6: Engajamento e Prática Ativa**
_Aprender fazendo, não só lendo_

- Calculadoras médicas expandidas (Cockcroft-Gault, Glasgow, SOFA, Wells, etc.)
- Recall ativo ("Explica com suas palavras")
- Quiz e casos clínicos interativos (WhatsApp Flows)
- Progressão de maestria (reconhecimento genuíno > gamificação)
- "Rota alternativa" — muda abordagem quando aluno está preso

**Tema 7: Feedback e Melhoria Contínua**
_Ciclo virtuoso que melhora o produto sozinho_

- Feedback explícito: Reply Buttons (👍👎📝) a cada resposta
- Feedback proativo: NPS a cada 30-50 interações
- Feedback implícito: padrões de uso, abandono, reformulação
- Avaliação automatizada (Haiku batch) para qualidade
- Notificações de uso e timeline de atividade

### Priorização de Ideias

| Prioridade | Ideia | Impacto | Viabilidade | Momento |
|-----------|-------|---------|-------------|---------|
| Must-have | Tool Use + Migração código | Crítico | Alta (validado) | M0-M1 |
| Must-have | Cost tracking granular | Crítico | Trivial | M1 |
| Must-have | Supabase schema rebuild | Crítico | Média | M1 |
| Must-have | Disclaimers médicos | Crítico | Trivial | M1 |
| Quick win | Follow-up Reply Buttons | Alto | Trivial | M1.5 |
| Quick win | Feedback explícito (👍👎) | Alto | Trivial | M1.5 |
| Quick win | Status em tempo real | Médio | Trivial | M1.5 |
| Quick win | Citações visíveis | Alto | Baixa | M1.5 |
| Quick win | Notificações de uso | Médio | Trivial | M1.5 |
| Diferenciação | Memória 3 camadas | Alto | Média | M2 |
| Diferenciação | Modos (estudo/plantão/revisão) | Alto | Média | M2 |
| Diferenciação | Calculadoras médicas | Alto | Média | M2 |
| Diferenciação | Perplexity prioridade 2 | Alto | Média | M2 |
| Diferenciação | Dashboard Observatory v1 | Alto | Média | M2 |
| Fenomenal | Voice mode bidirecional | Médio | Média | M3 |
| Fenomenal | Caderno automático + PDF | Médio | Média | M3 |
| Fenomenal | RAG dinâmico | Alto | Alta | M3 |
| Fenomenal | WhatsApp Flows (quiz/casos) | Alto | Média | M3 |
| Fenomenal | Dificuldade adaptativa | Médio | Média | M3 |
| Fenomenal | Medbrain Wrapped | Baixo | Média | M3 |
| Descartado | Broadcast diário | Baixo | Inviável ($9.375/mês) | — |
| Descartado | Plantão como produto separado | — | — | — |

### Action Plan — Momento 0 (Próxima Semana)

**Objetivo:** Validar Tool Use Architecture com dados reais antes de investir meses.

**Dia 1-2:**
- Setup projeto (Git, estrutura básica, dependências)
- Implementar: Webhook → Claude SDK + 1 tool (`buscar_base_medica`) → resposta formatada
- Cost tracking básico (logar tokens + latência)

**Dia 3:**
- Extrair 200 conversas reais do Supabase
- Rodar batch contra código novo
- Comparar: qualidade, latência, custo

**Dia 4-5:**
- Shadow mode: fork no webhook para código novo (processa mas não responde)
- Validar com mensagens reais em tempo real
- Comparação side-by-side com n8n

**Dia 6-7:**
- Análise de resultados: qualidade, custo, latência
- Decisão Go/No-Go para Momento 1
- Documentação de aprendizados

**Critério de sucesso:** 80%+ das respostas iguais ou melhores que n8n, latência aceitável, cost tracking funcionando.

**Critério de falha (pivotar):** Qualidade significativamente inferior, latência inaceitável, custos muito superiores ao n8n.

---

## Session Summary and Insights

**Conquistas da Sessão:**
- 40+ ideias estruturadas geradas através de 3 técnicas complementares
- 7 temas organizados cobrindo desde arquitetura até experiência do usuário
- Faseamento validado em 5 momentos (M0 → M1 → M1.5 → M2 → M3)
- Decisões críticas tomadas: descarte de broadcast, Perplexity como P2, tudo no mesmo bot
- Estratégia de teste Momento 0 definida (replay Supabase + shadow mode)
- Princípios de design validados (fricção zero, dados antes de decisões, disclaimers obrigatórios)

**Breakthroughs Criativos:**
- Tool Use Architecture como gold standard (validado por pesquisa extensiva)
- Strangler Fig Pattern como estratégia de migração segura
- "Observatory" como dashboard unificado (custo + feedback + RAG + usage)
- Conteúdo embutido na experiência reativa em vez de broadcasts caros
- Shadow mode como primeiro passo natural da migração E estratégia de teste

**Reflexões da Sessão:**
- Assumption Reversal foi a técnica mais produtiva — questionou cada premissa do sistema atual e revelou oportunidades em cada uma
- Cross-Pollination trouxe ideias tangíveis de domínios inesperados (Duolingo, Spotify, Uber)
- Six Thinking Hats forçou avaliação crítica que levou a revisão completa do faseamento
- A combinação das 3 técnicas garantiu exploração profunda E organização prática
- Rodrigo demonstrou forte senso de priorização e pragmatismo ao longo de toda sessão
