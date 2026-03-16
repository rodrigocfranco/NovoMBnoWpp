# ADR-012: Padrão get_model(tools=) — Bind Tools Antes de with_fallbacks()

**Date:** 2026-03-12
**Status:** DECIDED (implementado no Epic 2, documentado no Sprint 6)
**Decisores:** Charlie (Senior Dev), Rodrigo Franco
**Origem:** Descoberta durante Story 2.3 (Verificação de Artigos PubMed), documentado como action item na retrospectiva do Epic 2

---

## Contexto

O ADR-006 define a estratégia multi-provider com Vertex AI (primary) + Anthropic Direct (fallback) usando `model.with_fallbacks()` do LangChain. Quando as 5 tools médicas do Epic 2 foram implementadas, descobrimos um **bug arquitetural** na interação entre `bind_tools()` e `with_fallbacks()`.

## Problema Descoberto

```python
# ERRADO — fallback perde as tools
model = get_model()  # retorna RunnableWithFallbacks
model_with_tools = model.bind_tools(tools)
# bind_tools() só é aplicado ao primary (ChatAnthropicVertex)
# Quando fallback ativa, ChatAnthropic NÃO tem tools bound
# Resultado: LLM tenta chamar tools mas não consegue → erro silencioso
```

Quando `bind_tools()` é chamado em um `RunnableWithFallbacks`, o bind é aplicado **apenas ao primary model**. Se o primary falha e o fallback ativa, o `ChatAnthropic` (fallback) não possui as tools vinculadas. Isso causa:

1. LLM tenta chamar tools que não existem no fallback
2. Resposta sem tool calls (degradação silenciosa)
3. Ou erro de schema incompatível

## Decisão

**Bind tools em AMBOS os models ANTES de criar o `with_fallbacks()`.**

```python
# CORRETO — get_model(tools=) faz bind em ambos
def get_model(*, tools: list | None = None) -> Any:
    primary = ChatAnthropicVertex(...)
    fallback = ChatAnthropic(...)

    if tools:
        primary = primary.bind_tools(tools)
        fallback = fallback.bind_tools(tools)

    return primary.with_fallbacks([fallback])
```

## Implementação Atual

Arquivo: `workflows/providers/llm.py`

- `get_model(tools=)` aceita lista opcional de tools
- Quando `tools` é fornecido, faz `bind_tools()` em primary E fallback antes de `with_fallbacks()`
- Cached singleton separado: `_default_model` (sem tools) e `_tools_model` (com tools)
- O `orchestrate_llm` node chama `get_model(tools=get_tools())` para obter modelo com tools

## Regra de Uso

| Caso | Chamada |
|------|---------|
| LLM sem tools (ex: mensagem simples) | `get_model()` |
| LLM com tools (ex: orchestrate_llm) | `get_model(tools=get_tools())` |
| NUNCA fazer | `get_model().bind_tools(tools)` |

**REGRA INVIOLÁVEL:** Nunca chamar `.bind_tools()` no retorno de `get_model()`. Sempre passar tools como parâmetro.

## Alternativas Consideradas

1. **Wrapper custom que intercepta bind_tools** — Rejeitada por complexidade
2. **Não usar with_fallbacks, fazer try/except manual** — Rejeitada por perder retry automático do LangChain
3. **Monkey-patch RunnableWithFallbacks.bind_tools** — Rejeitada por fragilidade

## Consequências

**Positivas:**
- Fallback funciona corretamente com tools (zero degradação)
- API simples: `get_model(tools=)` encapsula a complexidade
- Cache singleton eficiente (2 instâncias: com e sem tools)

**Negativas:**
- Qualquer nova chamada a `get_model` com tools diferente cria instância nova (cache miss)
- Requer disciplina: nunca usar `.bind_tools()` direto no retorno

## Impacto

Afeta todo código que usa LLM com tools:
- `workflows/whatsapp/nodes/orchestrate_llm.py` — usa `get_model(tools=get_tools())`
- Qualquer futuro nó ou serviço que precise de LLM com tools

## Referências

- ADR-006: Multi-Provider LLM Strategy
- ADR-010: Orquestração LLM — LangGraph + LangChain
- Story 2.3: Verificação de Artigos PubMed (onde o bug foi descoberto)
- Epic 2 Retrospective (2026-03-10): Action item "Documentar padrão get_model(tools=) como ADR"
- `workflows/providers/llm.py`: Implementação atual
