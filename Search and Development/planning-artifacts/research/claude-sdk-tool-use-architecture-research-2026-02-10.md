---
stepsCompleted: [1, 2]
inputDocuments: []
workflowType: 'research'
lastStep: 2
research_type: 'technical'
research_topic: 'Anthropic Claude SDK e Arquitetura Tool Use para Bot WhatsApp Médico'
research_goals: 'Documentar padrões de SDK, Tool Use, Prompt Caching, seleção de modelos e padrões de produção para implementação do Medbrain WhatsApp com Claude'
user_name: 'Rodrigo Franco'
date: '2026-02-10'
web_research_enabled: true
source_verification: true
---

# Research Report: Anthropic Claude SDK e Arquitetura Tool Use

**Data:** 2026-02-10
**Autor:** Rodrigo Franco
**Tipo:** Technical Research
**Contexto:** Bot tutor médico WhatsApp (Medbrain) usando Claude Sonnet com múltiplas ferramentas (RAG search, drug lookup, quiz generation, medical calculators, etc.)

---

## Nota sobre Fontes

Este relatório foi compilado com base na documentação oficial da Anthropic (docs.anthropic.com), documentação dos SDKs no GitHub (github.com/anthropics/anthropic-sdk-python e anthropic-sdk-typescript), e padrões documentados até início de 2025. As URLs de fonte são fornecidas para cada seção. Onde a informação pode ter sido atualizada após maio de 2025, isso é indicado com nível de confiança.

---

## 1. Anthropic Claude SDK (Node.js e Python)

### 1.1 Visao Geral dos SDKs

A Anthropic mantém SDKs oficiais para **Python** e **TypeScript/Node.js**, ambos com paridade de funcionalidades:

| Aspecto | Python SDK | TypeScript SDK |
|---------|-----------|----------------|
| Pacote | `anthropic` (PyPI) | `@anthropic-ai/sdk` (npm) |
| GitHub | github.com/anthropics/anthropic-sdk-python | github.com/anthropics/anthropic-sdk-typescript |
| Async nativo | Sim (`AsyncAnthropic`) | Sim (Promise-based) |
| Streaming | Sim (SSE) | Sim (SSE) |
| Tool Use | Sim | Sim |
| Prompt Caching | Sim | Sim |
| Tipagem | Pydantic models internos | TypeScript types |

**Fonte:** https://docs.anthropic.com/en/api/client-sdks

### 1.2 Inicializacao do Cliente

**Python:**

```python
import anthropic

# Síncrono
client = anthropic.Anthropic()  # Usa ANTHROPIC_API_KEY do env

# Assíncrono
client = anthropic.AsyncAnthropic()  # Para uso com asyncio

# Com configuração explícita
client = anthropic.AsyncAnthropic(
    api_key="sk-ant-...",
    max_retries=3,        # Retry automático em erros transientes
    timeout=60.0,         # Timeout em segundos
)
```

**TypeScript/Node.js:**

```typescript
import Anthropic from '@anthropic-ai/sdk';

const client = new Anthropic();  // Usa ANTHROPIC_API_KEY do env

const client = new Anthropic({
    apiKey: 'sk-ant-...',
    maxRetries: 3,
    timeout: 60000,  // ms
});
```

**Fonte:** https://docs.anthropic.com/en/api/client-sdks

### 1.3 Chamada Basica com Messages API

**Python (async):**

```python
response = await client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    system="Você é um tutor médico especializado...",
    messages=[
        {"role": "user", "content": "Explique farmacologia de beta-bloqueadores"}
    ]
)

# Acesso ao conteúdo
text = response.content[0].text

# Metadados de uso
print(response.usage.input_tokens)   # Tokens de entrada
print(response.usage.output_tokens)  # Tokens de saída
print(response.model)                # Modelo usado
print(response.stop_reason)          # "end_turn", "tool_use", "max_tokens"
```

**Fonte:** https://docs.anthropic.com/en/api/messages

### 1.4 Tool Use (Function Calling) — Implementacao Completa

O Tool Use e o recurso central para o bot WhatsApp medico. Claude pode receber definicoes de ferramentas, decidir quando usa-las, e processar os resultados.

**Fluxo de Tool Use:**

```
1. Usuário envia mensagem + definições de tools
2. Claude decide se precisa de uma tool → retorna tool_use block
3. Aplicação executa a tool com os parâmetros fornecidos
4. Aplicação envia tool_result de volta ao Claude
5. Claude gera resposta final incorporando o resultado
```

**Definicao de Tools (Python):**

```python
tools = [
    {
        "name": "search_medical_knowledge",
        "description": "Busca na base de conhecimento médico (RAG) por informações sobre doenças, medicamentos, procedimentos e protocolos clínicos brasileiros. Use sempre que o aluno perguntar sobre conteúdo médico factual.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A consulta de busca em linguagem natural"
                },
                "specialty": {
                    "type": "string",
                    "enum": ["cardiologia", "pneumologia", "neurologia", "gastroenterologia", "infectologia", "pediatria", "cirurgia", "ginecologia", "ortopedia", "outros"],
                    "description": "Especialidade médica para filtrar resultados"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Número máximo de resultados",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "lookup_drug",
        "description": "Consulta informações detalhadas sobre um medicamento: indicações, contraindicações, posologia, interações medicamentosas e efeitos adversos. Fonte: bulas aprovadas pela ANVISA.",
        "input_schema": {
            "type": "object",
            "properties": {
                "drug_name": {
                    "type": "string",
                    "description": "Nome do medicamento (genérico ou comercial)"
                },
                "info_type": {
                    "type": "string",
                    "enum": ["completo", "indicacoes", "contraindicacoes", "posologia", "interacoes", "efeitos_adversos"],
                    "description": "Tipo de informação desejada"
                }
            },
            "required": ["drug_name"]
        }
    },
    {
        "name": "generate_quiz",
        "description": "Gera uma questão de múltipla escolha sobre o tema atual para testar o conhecimento do aluno. Inclui 4 alternativas (A-D), gabarito e explicação pedagógica.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Tema da questão"
                },
                "difficulty": {
                    "type": "string",
                    "enum": ["basico", "intermediario", "avancado"],
                    "description": "Nível de dificuldade"
                },
                "bloom_level": {
                    "type": "string",
                    "enum": ["conhecimento", "compreensao", "aplicacao", "analise"],
                    "description": "Nível da taxonomia de Bloom"
                }
            },
            "required": ["topic", "difficulty"]
        }
    },
    {
        "name": "medical_calculator",
        "description": "Calcula escores médicos padronizados: CHA2DS2-VASc, MELD, Child-Pugh, Wells, Glasgow, CURB-65, SOFA, etc. Retorna o escore calculado com interpretação clínica.",
        "input_schema": {
            "type": "object",
            "properties": {
                "calculator_name": {
                    "type": "string",
                    "description": "Nome do escore/calculadora médica"
                },
                "parameters": {
                    "type": "object",
                    "description": "Parâmetros necessários para o cálculo (variam por calculadora)"
                }
            },
            "required": ["calculator_name", "parameters"]
        }
    }
]
```

**Chamada com Tools (Python async):**

```python
response = await client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    system="Você é o MedBrain, um tutor médico inteligente...",
    tools=tools,
    messages=[
        {"role": "user", "content": "Qual a dose de amoxicilina para otite média em criança de 3 anos?"}
    ]
)

# Processar resposta — pode conter text E tool_use blocks
for block in response.content:
    if block.type == "text":
        print(block.text)
    elif block.type == "tool_use":
        tool_name = block.name        # "lookup_drug"
        tool_input = block.input      # {"drug_name": "amoxicilina", "info_type": "posologia"}
        tool_use_id = block.id        # "toolu_01A..."
```

**Enviando Tool Result de volta:**

```python
# Após executar a tool
drug_info = await lookup_drug("amoxicilina", "posologia")

# Continuar a conversa com o resultado
response = await client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    system="Você é o MedBrain...",
    tools=tools,
    messages=[
        {"role": "user", "content": "Qual a dose de amoxicilina para otite média em criança de 3 anos?"},
        {"role": "assistant", "content": response.content},  # Inclui o tool_use block
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": json.dumps(drug_info)  # Resultado da execução
                }
            ]
        }
    ]
)
```

**Fonte:** https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview

### 1.5 Chamadas de Tool Paralelas

Claude pode solicitar **multiplas tools simultaneamente** quando as chamadas sao independentes. Isso e identificado quando `response.content` contem mais de um `tool_use` block.

```python
response = await client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    tools=tools,
    messages=[
        {"role": "user", "content": "Compare losartana e enalapril para hipertensão. E calcule o CHA2DS2-VASc do paciente: 72 anos, hipertenso, diabético."}
    ]
)

# Claude pode retornar DOIS tool_use blocks:
# 1. lookup_drug(drug_name="losartana") + lookup_drug(drug_name="enalapril")
# 2. medical_calculator(calculator_name="CHA2DS2-VASc", parameters={...})

tool_results = []
for block in response.content:
    if block.type == "tool_use":
        result = await execute_tool(block.name, block.input)
        tool_results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": json.dumps(result)
        })

# Enviar TODOS os resultados de uma vez
final_response = await client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    tools=tools,
    messages=[
        {"role": "user", "content": "Compare losartana e enalapril..."},
        {"role": "assistant", "content": response.content},
        {"role": "user", "content": tool_results}  # Todos os tool_results juntos
    ]
)
```

**Importante:** Todos os `tool_result` para os `tool_use` blocks de um turno devem ser enviados na mesma mensagem. Claude espera receber todos antes de continuar.

**Fonte:** https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview#parallel-tool-use

### 1.6 tool_choice — Controlando o Uso de Ferramentas

O parametro `tool_choice` controla como Claude decide usar ferramentas:

```python
# Auto (default) — Claude decide se usa ou não
tool_choice={"type": "auto"}

# Qualquer tool obrigatória — Claude DEVE usar alguma tool
tool_choice={"type": "any"}

# Tool específica obrigatória — Claude DEVE usar esta tool
tool_choice={"type": "tool", "name": "search_medical_knowledge"}

# Desabilitar parallel tool use (forçar sequencial)
tool_choice={"type": "auto", "disable_parallel_tool_use": True}
```

**Para o bot medico:** Use `auto` na maioria dos casos. Use `tool` forçado quando o fluxo exige (ex: após o aluno responder um quiz, forçar `generate_quiz` para gerar feedback).

**Fonte:** https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview#controlling-tool-use

### 1.7 Streaming com Tool Use

Para uma experiencia responsiva no WhatsApp, streaming permite enviar texto parcial enquanto Claude pensa:

```python
async with client.messages.stream(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    tools=tools,
    messages=messages
) as stream:
    async for event in stream:
        if event.type == "content_block_start":
            if event.content_block.type == "text":
                # Início de bloco de texto
                pass
            elif event.content_block.type == "tool_use":
                # Início de chamada de tool
                current_tool = event.content_block.name
        elif event.type == "content_block_delta":
            if event.delta.type == "text_delta":
                # Texto parcial — pode enviar ao WhatsApp incrementalmente
                print(event.delta.text, end="", flush=True)
            elif event.delta.type == "input_json_delta":
                # JSON parcial dos parâmetros da tool
                pass
        elif event.type == "message_stop":
            # Mensagem completa
            pass

    # Acesso à mensagem final
    final_message = await stream.get_final_message()
```

**Para WhatsApp:** Streaming nao e diretamente aplicavel ao WhatsApp (que envia mensagens completas), mas permite:
1. Mostrar "digitando..." enquanto Claude processa
2. Enviar a resposta mais rapidamente (processar tool calls assim que detectados, antes da mensagem completar)
3. Implementar timeout mais granular

**Fonte:** https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview#streaming

### 1.8 Tratamento de Erros em Tool Results

Quando a execucao de uma tool falha, voce deve informar Claude com `is_error: true`:

```python
{
    "type": "tool_result",
    "tool_use_id": tool_use_id,
    "content": "Erro: Medicamento 'xyzabc' não encontrado na base de dados da ANVISA.",
    "is_error": True
}
```

Claude vai processar o erro e pode:
- Tentar uma tool diferente
- Pedir informação adicional ao usuário
- Responder com o que sabe, informando a limitação

**Padrao recomendado para o bot medico:**

```python
async def execute_tool_safely(name: str, input: dict) -> dict:
    try:
        result = await tool_registry[name](**input)
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": json.dumps(result)
        }
    except ToolNotFoundError:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": f"Ferramenta '{name}' não disponível.",
            "is_error": True
        }
    except TimeoutError:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": "Timeout na consulta. Tente novamente.",
            "is_error": True
        }
    except Exception as e:
        logger.error(f"Tool execution error: {name}, {e}")
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": f"Erro interno ao executar {name}.",
            "is_error": True
        }
```

**Fonte:** https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview#tool-result-errors

### 1.9 SDK Retry Automatico e Configuracao

Ambos os SDKs incluem retry automatico com backoff exponencial para erros transientes (429 rate limit, 500+ server errors, timeouts de conexao):

```python
client = anthropic.AsyncAnthropic(
    max_retries=3,        # Default: 2
    timeout=httpx.Timeout(
        connect=5.0,
        read=60.0,        # Leitura pode demorar para respostas longas
        write=5.0,
        pool=5.0
    )
)
```

O SDK respeita o header `Retry-After` retornado pela API quando rate limits sao atingidos.

**Erros que ativam retry automatico:**
- `429` — Rate limit exceeded
- `500` — Internal server error
- `502` — Bad gateway
- `503` — Service unavailable
- `Connection errors` — Network issues

**Erros que NAO ativam retry (erros do usuario):**
- `400` — Bad request (schema invalido, tool mal definida)
- `401` — Authentication failed
- `403` — Permission denied
- `404` — Not found

**Fonte:** https://github.com/anthropics/anthropic-sdk-python#retries

---

## 2. Prompt Caching

### 2.1 O que e Prompt Caching

Prompt Caching permite reutilizar prefixos previamente processados de prompts entre chamadas da API. Em vez de processar o system prompt + definicoes de tools + contexto a cada requisicao, a Anthropic armazena o prefixo processado em cache por um periodo determinado.

**Impacto direto para o bot medico:** O system prompt extenso (instrucoes do tutor + regras medicas + tom de voz) + as definicoes de 4-8 tools + contexto pedagogico sao processados UMA VEZ e reutilizados em todas as mensagens subsequentes.

**Fonte:** https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching

### 2.2 Economia de Custos

| Tipo de Token | Custo Relativo |
|---------------|---------------|
| Token base (input normal) | 100% (preço cheio) |
| Cache write (primeira vez) | 125% (25% mais caro) |
| Cache read (reutilização) | **10%** (90% de desconto) |

**Calculo pratico para o bot medico:**

Supondo:
- System prompt + tools = ~4.000 tokens
- Mensagem do usuário = ~100 tokens
- 1.000 mensagens/dia

**Sem cache:** 1.000 x 4.100 = 4.100.000 input tokens
**Com cache:** 1 x 5.000 (write a 125%) + 999 x 400.100 (4.000 a 10% + 100 a 100%) = 5.000 + 399.700 = ~404.700 tokens efetivos

**Economia: ~90% nos tokens de system prompt + tools** para chamadas subsequentes dentro do TTL.

### 2.3 Implementacao

O cache e ativado adicionando `cache_control` ao conteudo que deve ser cacheado:

```python
response = await client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    system=[
        {
            "type": "text",
            "text": """Você é o MedBrain, um tutor médico inteligente especializado
            em preparação para provas de medicina no Brasil (1º ao 4º ano).

            REGRAS:
            1. Sempre cite fontes médicas brasileiras quando possível
            2. Use linguagem clara e didática
            3. Para medicamentos, sempre mencione contraindicações
            4. Não faça diagnósticos — oriente a buscar atendimento
            ... (system prompt extenso) ...""",
            "cache_control": {"type": "ephemeral"}  # <-- MARCA PARA CACHE
        }
    ],
    tools=tools,  # Tools também são cacheadas como parte do prefixo
    messages=[
        {"role": "user", "content": "O que é síndrome nefrótica?"}
    ]
)
```

**Pontos de cache (`cache_control`)** podem ser colocados em:
1. **System prompt** — o mais comum e impactante
2. **Definicoes de tools** — cacheadas junto com o system prompt
3. **Mensagens anteriores do historico** — util para conversas longas
4. **Conteudo de imagens** — se usar vision

**Regra dos breakpoints:** Voce pode ter ate **4 blocos com `cache_control`** numa unica requisicao. O cache funciona como prefixo — tudo antes do ultimo breakpoint pode ser cacheado.

### 2.4 TTL (Time to Live)

- **TTL padrao: 5 minutos** desde o ultimo uso
- Cada vez que o cache e lido (hit), o TTL e renovado por mais 5 minutos
- Para o bot medico: se ha interacao constante, o cache se mantem vivo indefinidamente
- Em horarios de baixo uso (madrugada), o cache expira e a proxima requisicao paga cache write novamente

### 2.5 Verificacao de Cache Hit/Miss

A resposta da API inclui campos de uso que indicam cache:

```python
response = await client.messages.create(...)

print(response.usage.input_tokens)              # Tokens de input total
print(response.usage.cache_creation_input_tokens)  # Tokens escritos no cache (125%)
print(response.usage.cache_read_input_tokens)      # Tokens lidos do cache (10%)
```

**Logica de monitoramento:**

```python
usage = response.usage
if usage.cache_read_input_tokens > 0:
    logger.info(f"Cache HIT: {usage.cache_read_input_tokens} tokens lidos do cache")
elif usage.cache_creation_input_tokens > 0:
    logger.info(f"Cache WRITE: {usage.cache_creation_input_tokens} tokens escritos no cache")
else:
    logger.warning("Sem cache — verificar configuração de cache_control")
```

### 2.6 Requisito Minimo de Tokens

O conteudo marcado com `cache_control` precisa atingir um **minimo de tokens** para ser elegivel ao cache:

| Modelo | Mínimo de Tokens para Cache |
|--------|---------------------------|
| Claude Sonnet 4 / 3.5 | 1.024 tokens |
| Claude Haiku 3.5 | 2.048 tokens |
| Claude Opus 4 | 1.024 tokens |

Para o bot medico, o system prompt + tools facilmente ultrapassa 1.024 tokens, entao nao sera um problema.

### 2.7 Padrao Recomendado para Conversas WhatsApp

```python
async def send_message_to_claude(
    conversation_history: list[dict],
    user_message: str,
    system_prompt: str,
    tools: list[dict]
) -> dict:
    """
    Padrão otimizado com prompt caching para conversas WhatsApp.

    Ordem de cache (do mais estático ao mais dinâmico):
    1. System prompt (cache_control) — muda raramente
    2. Tools (implicitamente cacheadas como parte do prefixo)
    3. Histórico de conversa — cresce a cada mensagem
    4. Mensagem atual do usuário — nunca cacheada
    """

    # System prompt com cache
    system = [
        {
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"}
        }
    ]

    # Histórico + nova mensagem
    messages = conversation_history + [
        {"role": "user", "content": user_message}
    ]

    # Para conversas longas, cachear também o histórico
    # (colocar cache_control no último item do histórico antes da msg atual)
    if len(conversation_history) > 10:
        # Cachear o prefixo do histórico
        last_assistant_msg = None
        for i in range(len(conversation_history) - 1, -1, -1):
            if conversation_history[i]["role"] == "assistant":
                last_assistant_msg = i
                break

        if last_assistant_msg is not None:
            msg = conversation_history[last_assistant_msg]
            if isinstance(msg["content"], str):
                messages[last_assistant_msg] = {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": msg["content"],
                            "cache_control": {"type": "ephemeral"}
                        }
                    ]
                }

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=system,
        tools=tools,
        messages=messages
    )

    return response
```

**Fonte:** https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching

---

## 3. Tool Use — Melhores Praticas da Anthropic

### 3.1 Qualidade das Descricoes de Tools

A **descricao da tool e o fator mais importante** para Claude decidir quando e como usa-la. A Anthropic recomenda:

**Boas descricoes:**
- Explicam **quando** usar a tool (nao so o que ela faz)
- Incluem **exemplos** de quando usar e quando NAO usar
- Descrevem o **formato de retorno** esperado
- Sao **especificas ao dominio** do aplicativo

```python
# BOM — Específico, com contexto de uso
{
    "name": "search_medical_knowledge",
    "description": """Busca na base de conhecimento médico curada por informações
    sobre doenças, medicamentos, procedimentos e protocolos clínicos brasileiros.

    USE ESTA FERRAMENTA quando:
    - O aluno perguntar sobre conteúdo médico factual (doenças, fisiopatologia, tratamentos)
    - Precisar verificar informações médicas antes de responder
    - For necessário citar fontes ou referências

    NÃO USE quando:
    - A pergunta for sobre estudo/organização/motivação (responda diretamente)
    - O aluno estiver respondendo um quiz (use as informações já fornecidas)
    - For uma saudação ou pergunta casual"""
}

# RUIM — Genérico, não ajuda Claude a decidir quando usar
{
    "name": "search",
    "description": "Busca informações"
}
```

**Fonte:** https://docs.anthropic.com/en/docs/build-with-claude/tool-use/best-practices-and-limitations

### 3.2 Design de Schema (input_schema)

**Regras da Anthropic para schemas:**

1. **Use `required` para campos obrigatorios** — Claude tende a omitir campos opcionais
2. **Use `enum` para valores finitos** — Evita valores inventados
3. **Use `description` em cada propriedade** — Claude usa para entender o que preencher
4. **Mantenha schemas simples** — Evite aninhamento profundo
5. **Use `default` valores** — Para campos opcionais com valor padrao obvio

```python
{
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Consulta em linguagem natural. Seja específico: inclua o tema médico, a dúvida específica e o nível de detalhe desejado."
        },
        "specialty": {
            "type": "string",
            "enum": ["cardiologia", "pneumologia", "neurologia", ...],
            "description": "Especialidade médica para filtrar. Omita para busca geral."
        },
        "source_type": {
            "type": "string",
            "enum": ["livro_texto", "diretriz", "artigo_revisao", "todos"],
            "default": "todos",
            "description": "Tipo de fonte preferido"
        }
    },
    "required": ["query"]  # Apenas o essencial
}
```

### 3.3 Numero Ideal de Tools

A Anthropic documenta que:

- Claude funciona bem com **ate ~20 tools** numa unica chamada
- **Performance degrada** com muitas tools (mais tokens de input, mais dificuldade de selecao)
- **Recomendacao pratica**: 5-10 tools e o sweet spot para a maioria dos aplicativos

**Para o bot medico**, 4-8 tools e ideal:
1. `search_medical_knowledge` — RAG
2. `lookup_drug` — Busca de medicamentos
3. `generate_quiz` — Gerador de questoes
4. `medical_calculator` — Calculadoras medicas
5. `get_study_plan` — Plano de estudo (opcional)
6. `save_progress` — Salvar progresso do aluno (opcional)
7. `get_flashcard` — Flashcards (opcional)

### 3.4 Chamadas Paralelas vs Sequenciais

**Paralelas (padrao):**
- Claude envia multiplos `tool_use` blocks quando as chamadas sao independentes
- Exemplo: "Compare losartana com enalapril" → 2 `lookup_drug` em paralelo
- Mais rapido, menos turnos de API

**Sequenciais (disable_parallel_tool_use):**
- Forcado com `tool_choice={"type": "auto", "disable_parallel_tool_use": True}`
- Util quando: resultado de uma tool informa a proxima
- Exemplo: Primeiro busca diagnostico, depois calcula escore com dados do diagnostico

**Para o bot medico:** Usar paralelo como default. Desabilitar apenas em fluxos onde ha dependencia logica entre tools.

### 3.5 Agentic Loop — Padrao para Multiplas Iteracoes

Para cenarios onde Claude precisa usar tools em sequencia (resultado de uma informa a proxima), implemente um **agentic loop**:

```python
async def agentic_conversation(
    client: anthropic.AsyncAnthropic,
    system: str,
    tools: list,
    messages: list,
    max_iterations: int = 5  # Safety limit
) -> str:
    """
    Loop agêntico: continua até Claude parar de pedir tools.
    """
    for iteration in range(max_iterations):
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system,
            tools=tools,
            messages=messages
        )

        # Se stop_reason == "end_turn", Claude terminou
        if response.stop_reason == "end_turn":
            # Extrair texto final
            return "".join(
                block.text for block in response.content
                if block.type == "text"
            )

        # Se stop_reason == "tool_use", processar tools
        if response.stop_reason == "tool_use":
            # Adicionar resposta do assistant ao histórico
            messages.append({"role": "assistant", "content": response.content})

            # Executar todas as tools solicitadas
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result) if not isinstance(result, str) else result
                    })

            # Adicionar resultados ao histórico
            messages.append({"role": "user", "content": tool_results})

            continue

        # max_tokens atingido — resposta incompleta
        if response.stop_reason == "max_tokens":
            logger.warning("max_tokens atingido — resposta pode estar incompleta")
            return "".join(
                block.text for block in response.content
                if block.type == "text"
            )

    logger.error(f"Agentic loop atingiu max_iterations ({max_iterations})")
    return "Desculpe, não consegui completar a consulta. Tente reformular sua pergunta."
```

**Fonte:** https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview#agentic-tool-use

### 3.6 Chain of Thought com Tools

Claude naturalmente inclui raciocinio antes de chamar uma tool. Isso pode ser util para debug e auditoria:

```python
for block in response.content:
    if block.type == "text":
        # Claude explica seu raciocínio ANTES de chamar a tool
        # Ex: "O aluno perguntou sobre dose pediátrica de amoxicilina.
        #      Vou consultar a base de medicamentos para dar informação precisa."
        logger.debug(f"Raciocínio do Claude: {block.text}")
    elif block.type == "tool_use":
        # A tool call em si
        logger.info(f"Tool call: {block.name}({block.input})")
```

**Dica:** Em producao, logar o raciocinio em nivel DEBUG para auditoria medica sem poluir logs de producao.

### 3.7 Limitacoes Conhecidas

1. **Tools nao sao executadas pelo Claude** — Ele gera os parametros, voce executa
2. **Claude pode "alucinar" tools** — Rarissimo, mas pode inventar tools que nao existem (mais comum com muitas tools)
3. **JSON complexo** — Schemas muito aninhados podem confundir a geracao de parametros
4. **Sem estado entre chamadas** — Cada chamada API e independente; o historico deve ser reenviado
5. **Custo de tokens** — Definicoes de tools contam como input tokens (~200-500 tokens por tool dependendo da complexidade)

**Fonte:** https://docs.anthropic.com/en/docs/build-with-claude/tool-use/best-practices-and-limitations

---

## 4. Selecao de Modelo para Producao

### 4.1 Modelos Disponiveis (atualizado ate mid-2025)

| Modelo | Model ID | Contexto | Max Output | Velocidade | Custo Input | Custo Output |
|--------|----------|----------|-----------|-----------|-------------|-------------|
| Claude Opus 4 | `claude-opus-4-20250514` | 200K | 32K | Lento | $15/MTok | $75/MTok |
| Claude Sonnet 4 | `claude-sonnet-4-20250514` | 200K | 16K | Medio | $3/MTok | $15/MTok |
| Claude Sonnet 3.5 v2 | `claude-3-5-sonnet-20241022` | 200K | 8K | Medio | $3/MTok | $15/MTok |
| Claude Haiku 3.5 | `claude-3-5-haiku-20241022` | 200K | 8K | Rapido | $0.80/MTok | $4/MTok |

**Nota sobre Sonnet 4.5:** Ate minha data de conhecimento (maio 2025), Sonnet 4.5 nao havia sido lancado. Opus 4 e Sonnet 4 foram lancados em maio 2025. Se Sonnet 4.5 existir apos essa data, verificar precos atualizados em https://docs.anthropic.com/en/docs/about-claude/models.

**Fonte:** https://docs.anthropic.com/en/docs/about-claude/models

### 4.2 Recomendacao para o Bot Medico WhatsApp

**Modelo principal: Claude Sonnet 4 (ou Sonnet 3.5 v2)**

| Criterio | Sonnet 4 / 3.5 v2 | Haiku 3.5 | Opus 4 |
|----------|-------------------|-----------|--------|
| Qualidade medica | Excelente | Boa, mas inferior | Superior |
| Tool use | Excelente | Bom | Excelente |
| Velocidade WhatsApp | Aceitavel (~2-5s) | Otima (~1-2s) | Lento (~5-15s) |
| Custo por mensagem | ~$0.01-0.03 | ~$0.003-0.008 | ~$0.05-0.15 |
| Contexto longo | 200K tokens | 200K tokens | 200K tokens |

**Estrategia recomendada: Roteamento por complexidade**

```python
def select_model(message: str, context: dict) -> str:
    """
    Seleciona modelo com base na complexidade da interação.
    """
    # Opus 4 — NUNCA para WhatsApp (muito lento e caro)
    # Reservar para batch processing offline se necessário

    # Haiku 3.5 — Interações simples e rápidas
    if context.get("is_quiz_answer"):
        return "claude-3-5-haiku-20241022"  # Corrigir quiz é simples
    if context.get("is_greeting"):
        return "claude-3-5-haiku-20241022"  # Saudações
    if context.get("is_simple_lookup"):
        return "claude-3-5-haiku-20241022"  # Consulta direta

    # Sonnet 4 — Default para tudo que requer raciocínio
    return "claude-sonnet-4-20250514"
```

### 4.3 Analise de Custo Detalhada

**Cenario: 500 usuarios ativos/dia, 20 mensagens/usuario**

| Item | Tokens/msg | Msgs/dia | Custo/dia (Sonnet 4) | Custo/dia (Haiku 3.5) |
|------|-----------|---------|---------------------|---------------------|
| System + tools (input) | ~4.000 | 10.000 | $120 sem cache / $16 com cache | $32 sem cache / $5 com cache |
| Historico (input) | ~2.000 avg | 10.000 | $60 | $16 |
| User message (input) | ~100 | 10.000 | $3 | $0.80 |
| Output | ~500 | 10.000 | $75 | $20 |
| **Total/dia** | | | **~$154 com cache** | **~$42 com cache** |
| **Total/mes** | | | **~$4.620** | **~$1.260** |

**Com roteamento Haiku/Sonnet (60% Haiku / 40% Sonnet):**
- Estimativa: ~$2.600/mes — **economia de ~44%** vs Sonnet puro

### 4.4 Extended Thinking (Pensamento Estendido)

Claude Sonnet 4 e Opus 4 suportam **extended thinking**, onde o modelo "pensa" internamente antes de responder. Isso melhora raciocinio complexo mas:

- **Aumenta latencia** significativamente (10-30s+)
- **Aumenta custo** (tokens de pensamento contam)
- **NAO recomendado para WhatsApp** em tempo real
- **Util para**: geracao batch de questoes (Construtor de Questoes), analise medica complexa offline

```python
# Extended thinking — NÃO usar para WhatsApp em tempo real
response = await client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=16000,
    thinking={
        "type": "enabled",
        "budget_tokens": 5000  # Orçamento para pensamento
    },
    messages=[...]
)

# Acessar pensamento (para debug/auditoria)
for block in response.content:
    if block.type == "thinking":
        print(f"Pensamento: {block.thinking}")
    elif block.type == "text":
        print(f"Resposta: {block.text}")
```

**Fonte:** https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking

---

## 5. Padroes de Producao

### 5.1 Rate Limiting

**Limites por tier (Anthropic API):**

| Tier | RPM (Requests/min) | Input TPM | Output TPM | Custo mensal |
|------|-------------------|-----------|-----------|-------------|
| Tier 1 (Free) | 50 | 40K | 8K | $0 |
| Tier 1 | 50 | 40K-80K | 8K-16K | >$5 |
| Tier 2 | 1.000 | 80K-160K | 16K-32K | >$40 |
| Tier 3 | 2.000 | 400K-800K | 80K-160K | >$200 |
| Tier 4 | 4.000 | 2M-4M | 400K-800K | >$1.000 |

**Nota:** Os limites exatos variam por modelo e sao atualizados frequentemente. Verificar https://docs.anthropic.com/en/api/rate-limits.

**Headers de rate limit na resposta:**

```
anthropic-ratelimit-requests-limit: 1000
anthropic-ratelimit-requests-remaining: 999
anthropic-ratelimit-requests-reset: 2026-02-10T14:30:00Z
anthropic-ratelimit-tokens-limit: 80000
anthropic-ratelimit-tokens-remaining: 79500
anthropic-ratelimit-tokens-reset: 2026-02-10T14:30:00Z
```

**Fonte:** https://docs.anthropic.com/en/api/rate-limits

### 5.2 Estrategia de Rate Limiting para WhatsApp

```python
import asyncio
from datetime import datetime, timedelta

class RateLimiter:
    """Rate limiter baseado nos headers da API Anthropic."""

    def __init__(self, max_rpm: int = 900, max_tpm: int = 70000):
        self.max_rpm = max_rpm  # 90% do limite para margem de segurança
        self.max_tpm = max_tpm
        self.request_count = 0
        self.token_count = 0
        self.window_start = datetime.now()
        self._lock = asyncio.Lock()

    async def acquire(self, estimated_tokens: int = 5000):
        """Aguarda até que haja capacidade disponível."""
        async with self._lock:
            now = datetime.now()

            # Reset window a cada minuto
            if (now - self.window_start) >= timedelta(minutes=1):
                self.request_count = 0
                self.token_count = 0
                self.window_start = now

            # Aguardar se limites atingidos
            while (self.request_count >= self.max_rpm or
                   self.token_count + estimated_tokens > self.max_tpm):
                wait_time = 60 - (now - self.window_start).seconds
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                self.request_count = 0
                self.token_count = 0
                self.window_start = datetime.now()
                now = datetime.now()

            self.request_count += 1
            self.token_count += estimated_tokens

    def update_from_response(self, response):
        """Atualiza contadores com dados reais da resposta."""
        actual_tokens = (
            response.usage.input_tokens +
            response.usage.output_tokens
        )
        # Ajustar estimativa
        self.token_count = self.token_count - 5000 + actual_tokens
```

### 5.3 Token Counting e Cost Tracking

**Dados disponiveis na resposta da API:**

```python
response = await client.messages.create(...)

# Uso de tokens — SEMPRE disponível
usage = response.usage
print(f"Input tokens:  {usage.input_tokens}")
print(f"Output tokens: {usage.output_tokens}")

# Cache tokens — quando prompt caching está ativo
print(f"Cache write:   {usage.cache_creation_input_tokens}")
print(f"Cache read:    {usage.cache_read_input_tokens}")
```

**Sistema de cost tracking para o bot:**

```python
from dataclasses import dataclass
from decimal import Decimal

# Preços por 1M tokens (atualizar conforme pricing vigente)
PRICING = {
    "claude-sonnet-4-20250514": {
        "input": Decimal("3.00"),
        "output": Decimal("15.00"),
        "cache_write": Decimal("3.75"),   # 125% do input
        "cache_read": Decimal("0.30"),    # 10% do input
    },
    "claude-3-5-haiku-20241022": {
        "input": Decimal("0.80"),
        "output": Decimal("4.00"),
        "cache_write": Decimal("1.00"),
        "cache_read": Decimal("0.08"),
    },
}

@dataclass
class UsageRecord:
    model: str
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
    user_id: str
    conversation_id: str
    timestamp: str

    @property
    def cost(self) -> Decimal:
        """Calcula custo em USD."""
        prices = PRICING[self.model]
        per_m = Decimal("1000000")

        # Input tokens que NÃO foram cache
        regular_input = self.input_tokens - self.cache_write_tokens - self.cache_read_tokens

        cost = (
            Decimal(regular_input) * prices["input"] / per_m +
            Decimal(self.cache_write_tokens) * prices["cache_write"] / per_m +
            Decimal(self.cache_read_tokens) * prices["cache_read"] / per_m +
            Decimal(self.output_tokens) * prices["output"] / per_m
        )
        return cost.quantize(Decimal("0.000001"))


def track_usage(response, user_id: str, conversation_id: str) -> UsageRecord:
    """Extrai e registra uso de uma resposta da API."""
    return UsageRecord(
        model=response.model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        cache_write_tokens=getattr(response.usage, 'cache_creation_input_tokens', 0) or 0,
        cache_read_tokens=getattr(response.usage, 'cache_read_input_tokens', 0) or 0,
        user_id=user_id,
        conversation_id=conversation_id,
        timestamp=datetime.utcnow().isoformat()
    )
```

### 5.4 Retry Strategy com Backoff Exponencial

Alem do retry automatico do SDK, implemente retry de nivel de aplicacao para erros de parsing e logica:

```python
import asyncio
import random

class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True

async def retry_with_backoff(
    func,
    *args,
    config: RetryConfig = RetryConfig(),
    retryable_exceptions: tuple = (
        anthropic.RateLimitError,
        anthropic.InternalServerError,
        anthropic.APIConnectionError,
    ),
    **kwargs
):
    """
    Retry com backoff exponencial e jitter.

    O SDK já faz retry para erros HTTP transientes,
    mas este wrapper adiciona retry para erros de aplicação
    (parsing falhou, validação falhou, etc.)
    """
    last_exception = None

    for attempt in range(config.max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except retryable_exceptions as e:
            last_exception = e

            if attempt == config.max_retries:
                raise

            # Calcular delay com backoff exponencial
            delay = min(
                config.base_delay * (config.exponential_base ** attempt),
                config.max_delay
            )

            # Adicionar jitter para evitar thundering herd
            if config.jitter:
                delay = delay * (0.5 + random.random())

            # Respeitar Retry-After header se disponível
            if hasattr(e, 'response') and e.response:
                retry_after = e.response.headers.get('retry-after')
                if retry_after:
                    delay = max(delay, float(retry_after))

            logger.warning(
                f"Attempt {attempt + 1}/{config.max_retries + 1} failed: {e}. "
                f"Retrying in {delay:.1f}s"
            )

            await asyncio.sleep(delay)

    raise last_exception
```

### 5.5 Timeout Handling

```python
import httpx

# Configuração de timeout granular
client = anthropic.AsyncAnthropic(
    timeout=httpx.Timeout(
        connect=5.0,     # Conexão: 5s
        read=120.0,      # Leitura: 2min (respostas longas com tools)
        write=10.0,      # Escrita: 10s
        pool=10.0        # Pool de conexões: 10s
    )
)

# Timeout por requisição (override)
try:
    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        tools=tools,
        messages=messages,
        timeout=30.0  # Override: 30s para esta chamada específica
    )
except anthropic.APITimeoutError:
    # Tratamento específico de timeout
    logger.error("API timeout — resposta demorou mais que o esperado")
    # Para WhatsApp: enviar mensagem de "processando..." e retry
    await send_whatsapp_message(user_id, "Estou pensando... um momento! ⏳")
    # Retry com timeout maior
    response = await client.messages.create(
        ...,
        timeout=60.0
    )
```

### 5.6 Hierarquia Completa de Erros do SDK

```python
import anthropic

try:
    response = await client.messages.create(...)
except anthropic.AuthenticationError as e:
    # 401 — API key inválida
    logger.critical(f"Auth failed: {e}")
    raise SystemExit("API key inválida")

except anthropic.PermissionDeniedError as e:
    # 403 — Sem permissão
    logger.error(f"Permission denied: {e}")

except anthropic.NotFoundError as e:
    # 404 — Modelo não encontrado
    logger.error(f"Model not found: {e}")

except anthropic.RateLimitError as e:
    # 429 — Rate limit (SDK já faz retry automático)
    logger.warning(f"Rate limit: {e}")
    # Se chegou aqui, SDK esgotou retries

except anthropic.BadRequestError as e:
    # 400 — Request inválido (schema errado, tool mal definida)
    logger.error(f"Bad request: {e}")
    # NÃO fazer retry — é erro do código

except anthropic.InternalServerError as e:
    # 500+ — Erro do servidor (SDK já faz retry automático)
    logger.error(f"Server error: {e}")

except anthropic.APIConnectionError as e:
    # Network error
    logger.error(f"Connection error: {e}")

except anthropic.APITimeoutError as e:
    # Timeout
    logger.error(f"Timeout: {e}")

except anthropic.APIError as e:
    # Qualquer outro erro de API
    logger.error(f"API error: {e.status_code} - {e.message}")
```

**Fonte:** https://github.com/anthropics/anthropic-sdk-python#handling-errors

### 5.7 Padrao Completo de Producao — Middleware WhatsApp

```python
"""
Padrão completo de integração Claude + WhatsApp para produção.
Combina todos os padrões: cache, tools, retry, tracking, rate limiting.
"""

import anthropic
import asyncio
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class MedBrainService:
    """Serviço principal do bot médico com Claude."""

    def __init__(
        self,
        api_key: str,
        system_prompt: str,
        tools: list[dict],
        model: str = "claude-sonnet-4-20250514",
        max_tool_iterations: int = 5,
    ):
        self.client = anthropic.AsyncAnthropic(
            api_key=api_key,
            max_retries=3,
            timeout=httpx.Timeout(connect=5, read=120, write=10, pool=10)
        )
        self.system_prompt = system_prompt
        self.tools = tools
        self.model = model
        self.max_tool_iterations = max_tool_iterations
        self.rate_limiter = RateLimiter()
        self.tool_registry = {}  # name -> async callable

    def register_tool(self, name: str, handler):
        """Registra handler para uma tool."""
        self.tool_registry[name] = handler

    async def process_message(
        self,
        user_id: str,
        conversation_id: str,
        user_message: str,
        conversation_history: list[dict],
    ) -> tuple[str, list[UsageRecord]]:
        """
        Processa uma mensagem do WhatsApp com agentic loop completo.

        Returns:
            tuple[str, list[UsageRecord]]: (resposta_texto, registros_de_uso)
        """
        usage_records = []

        # Preparar system com cache
        system = [
            {
                "type": "text",
                "text": self.system_prompt,
                "cache_control": {"type": "ephemeral"}
            }
        ]

        # Preparar mensagens
        messages = conversation_history + [
            {"role": "user", "content": user_message}
        ]

        # Agentic loop
        for iteration in range(self.max_tool_iterations):
            # Rate limiting
            await self.rate_limiter.acquire()

            try:
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=system,
                    tools=self.tools,
                    messages=messages
                )
            except anthropic.RateLimitError:
                logger.warning("Rate limit atingido após retries do SDK")
                return "Estou com muitas consultas no momento. Tente novamente em 1 minuto.", usage_records
            except anthropic.APITimeoutError:
                logger.error("Timeout na API")
                return "A consulta demorou mais que o esperado. Tente novamente.", usage_records
            except anthropic.APIError as e:
                logger.error(f"Erro de API: {e}")
                return "Ocorreu um erro interno. Tente novamente em instantes.", usage_records

            # Registrar uso
            usage_records.append(
                track_usage(response, user_id, conversation_id)
            )

            # Atualizar rate limiter com dados reais
            self.rate_limiter.update_from_response(response)

            # Se Claude terminou (sem mais tool calls)
            if response.stop_reason == "end_turn":
                final_text = "".join(
                    block.text for block in response.content
                    if block.type == "text"
                )
                return final_text, usage_records

            # Se Claude quer usar tools
            if response.stop_reason == "tool_use":
                # Adicionar resposta do assistant
                messages.append({
                    "role": "assistant",
                    "content": [block.model_dump() for block in response.content]
                })

                # Executar tools em paralelo
                tool_results = await self._execute_tools(response.content)

                # Adicionar resultados
                messages.append({
                    "role": "user",
                    "content": tool_results
                })

                continue

            # max_tokens — resposta truncada
            if response.stop_reason == "max_tokens":
                return "".join(
                    block.text for block in response.content
                    if block.type == "text"
                ), usage_records

        # Safety: max iterations atingido
        logger.error(f"Max tool iterations ({self.max_tool_iterations}) para user {user_id}")
        return "Não consegui completar a consulta. Tente reformular sua pergunta.", usage_records

    async def _execute_tools(self, content_blocks) -> list[dict]:
        """Executa todas as tool calls em paralelo."""
        tasks = []
        for block in content_blocks:
            if block.type == "tool_use":
                tasks.append(self._execute_single_tool(block))

        return await asyncio.gather(*tasks)

    async def _execute_single_tool(self, block) -> dict:
        """Executa uma única tool com tratamento de erro."""
        handler = self.tool_registry.get(block.name)

        if not handler:
            logger.error(f"Tool não registrada: {block.name}")
            return {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": f"Ferramenta '{block.name}' não disponível.",
                "is_error": True
            }

        try:
            result = await asyncio.wait_for(
                handler(**block.input),
                timeout=30.0  # Timeout por tool
            )
            return {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result
            }
        except asyncio.TimeoutError:
            logger.error(f"Timeout executando tool {block.name}")
            return {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": f"Timeout ao consultar {block.name}. Tente novamente.",
                "is_error": True
            }
        except Exception as e:
            logger.error(f"Erro executando tool {block.name}: {e}")
            return {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": f"Erro ao executar {block.name}: {str(e)}",
                "is_error": True
            }
```

### 5.8 Observabilidade e Metricas

**Metricas essenciais para monitorar em producao:**

| Metrica | Como Coletar | Alerta |
|---------|-------------|--------|
| Latencia por request | `time.time()` antes/depois | > 10s para WhatsApp |
| Tokens por conversa | `response.usage` | > 50K tokens (custo alto) |
| Cache hit rate | `cache_read / (cache_read + cache_write)` | < 80% (cache não funcionando) |
| Taxa de erro | Contagem de exceções | > 5% das requisições |
| Tool calls por mensagem | Contagem de `tool_use` blocks | > 5 (loop infinito?) |
| Custo por usuario/dia | Soma de `UsageRecord.cost` | > threshold definido |
| Rate limit hits | Contagem de `RateLimitError` | > 10/hora |

### 5.9 Gerenciamento de Historico de Conversa

Para o WhatsApp, o historico cresce a cada mensagem. Estrategias para manter custo controlado:

```python
class ConversationManager:
    """Gerencia histórico de conversa com janela deslizante."""

    MAX_HISTORY_MESSAGES = 20  # Últimas 20 mensagens
    MAX_HISTORY_TOKENS = 50000  # Ou 50K tokens

    def trim_history(self, messages: list[dict]) -> list[dict]:
        """
        Remove mensagens antigas mantendo contexto recente.

        Estratégia:
        1. Sempre manter a primeira mensagem (contexto inicial)
        2. Manter as últimas N mensagens
        3. Se exceder token limit, resumir mensagens do meio
        """
        if len(messages) <= self.MAX_HISTORY_MESSAGES:
            return messages

        # Manter primeira + últimas N-1
        first = messages[0]
        recent = messages[-(self.MAX_HISTORY_MESSAGES - 1):]

        # Inserir resumo do que foi removido
        summary = {
            "role": "user",
            "content": "[Contexto anterior resumido: o aluno estava estudando sobre o tema X, já respondeu Y questões, etc.]"
        }

        return [first, summary] + recent
```

---

## 6. Resumo de Decisoes para o Medbrain WhatsApp

### Stack Recomendada

| Componente | Recomendacao | Justificativa |
|-----------|-------------|--------------|
| SDK | `anthropic` Python (AsyncAnthropic) | Async nativo, retry built-in, tipagem |
| Modelo principal | Claude Sonnet 4 | Melhor custo/qualidade para educacao medica |
| Modelo leve | Claude Haiku 3.5 | Quiz feedback, saudacoes, consultas simples |
| Prompt Caching | Sim, obrigatorio | 90% economia no system prompt + tools |
| Tool Use | 4-6 tools (RAG, drugs, quiz, calculator) | Sweet spot de funcionalidade |
| Parallel tools | Habilitado (default) | Menor latencia |
| Agentic loop | Max 5 iteracoes | Safety limit |
| Rate limiting | Client-side + respeitar headers | Prevenir 429 |
| Cost tracking | Por mensagem, por usuario, por dia | Via response.usage |
| Retry | SDK built-in (3x) + app-level para parsing | Dupla camada |

### Riscos e Mitigacoes

| Risco | Mitigacao |
|-------|----------|
| Custo descontrolado | Budget alerts, roteamento Haiku/Sonnet, trim de historico |
| Latencia alta no WhatsApp | Haiku para queries simples, timeout 30s, mensagem "pensando..." |
| Alucinacoes medicas | RAG com fontes verificadas, system prompt rigoroso, disclaimer legal |
| Rate limits | Client-side limiter, queue de mensagens, retry com backoff |
| Cache miss | TTL 5min renovavel, monitorar cache hit rate |

---

## Fontes Consultadas

Todas as URLs abaixo sao da documentacao oficial da Anthropic e estavam ativas ate minha data de conhecimento (maio 2025). Recomenda-se verificar se houve atualizacoes:

1. **SDK Overview:** https://docs.anthropic.com/en/api/client-sdks
2. **Messages API:** https://docs.anthropic.com/en/api/messages
3. **Tool Use Overview:** https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview
4. **Tool Use Best Practices:** https://docs.anthropic.com/en/docs/build-with-claude/tool-use/best-practices-and-limitations
5. **Prompt Caching:** https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
6. **Models & Pricing:** https://docs.anthropic.com/en/docs/about-claude/models
7. **Rate Limits:** https://docs.anthropic.com/en/api/rate-limits
8. **Extended Thinking:** https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking
9. **Python SDK GitHub:** https://github.com/anthropics/anthropic-sdk-python
10. **TypeScript SDK GitHub:** https://github.com/anthropics/anthropic-sdk-typescript
11. **Error Handling:** https://github.com/anthropics/anthropic-sdk-python#handling-errors
12. **Retry Configuration:** https://github.com/anthropics/anthropic-sdk-python#retries

---

**Nota de confianca:** Este relatorio foi compilado com base em conhecimento da documentacao oficial da Anthropic ate maio de 2025. Precos, limites de rate, e model IDs podem ter sido atualizados apos essa data. Recomenda-se verificar as fontes listadas para informacoes mais recentes. Em particular, verificar se Sonnet 4.5 foi lancado e seus precos/capacidades.
