"""Tool: quiz_generate — gera questões de múltipla escolha para prática ativa."""

import asyncio

import structlog
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from workflows.providers.llm import get_model
from workflows.services.cost_tracker import CostTrackingCallback

logger = structlog.get_logger(__name__)

QUIZ_GENERATION_PROMPT = """\
Gere uma questão de múltipla escolha sobre {topic} no nível {level}.

Formato OBRIGATÓRIO:
**Questão:** [enunciado clínico contextualizado]

A) [alternativa]
B) [alternativa]
C) [alternativa]
D) [alternativa]
E) [alternativa]

**Gabarito:** [letra correta]

**Comentário:** [explicação detalhada com raciocínio clínico]\
"""

LEVEL_MAP = {
    "easy": "básico (conceitos fundamentais, definições)",
    "intermediate": "intermediário (aplicação clínica, diagnóstico diferencial)",
    "hard": "avançado (casos complexos, condutas em cenários atípicos)",
}

# Timeout for internal LLM call (consistent with orchestrate_llm pattern)
QUIZ_LLM_TIMEOUT_SECONDS = 15.0

# Max topic length to prevent excessively long prompts
MAX_TOPIC_LENGTH = 500

# Module-level cached model singleton — avoids recreating per call
_quiz_model = None


def _get_quiz_model():
    """Return cached LLM model for quiz generation (no tools, max_tokens=512)."""
    global _quiz_model
    if _quiz_model is None:
        _quiz_model = get_model(tools=None, max_tokens=512)
    return _quiz_model


@tool
async def quiz_generate(topic: str, level: str = "intermediate") -> str:
    """Gera uma questão de múltipla escolha sobre um tema médico para prática ativa.

    **QUANDO USAR:**
    - Aluno pede um quiz, questão ou pergunta para praticar (ex: "Me faça uma questão sobre IC")
    - Aluno quer testar conhecimento sobre um tema específico
    - Após sugestão contextual de quiz aceita pelo aluno

    **QUANDO NÃO USAR:**
    - Aluno faz uma pergunta médica real → use rag_medical_search ou outras tools
    - Aluno quer calcular score clínico → use medical_calculator

    **EXEMPLO:** "Me faça uma questão sobre insuficiência cardíaca" ✅
    **CONTRA-EXEMPLO:** "O que é insuficiência cardíaca?" ❌ (pergunta real → RAG)

    Args:
        topic: Tema médico para a questão (ex: "insuficiência cardíaca").
        level: Nível de dificuldade: "easy", "intermediate" ou "hard". Default: "intermediate".
    """
    if not topic or not topic.strip():
        return "Por favor, informe o tema para gerar a questão."

    topic = topic.strip()[:MAX_TOPIC_LENGTH]
    level = level.strip().lower()
    if level not in LEVEL_MAP:
        level = "intermediate"

    level_description = LEVEL_MAP[level]
    prompt = QUIZ_GENERATION_PROMPT.format(topic=topic, level=level_description)

    # Cost tracking — user_id identifies the tool source (tool doesn't have
    # access to graph state user_id; cost is tracked separately via structlog)
    cost_callback = CostTrackingCallback(
        user_id="quiz_generator",
        model_name="haiku",
    )

    try:
        model = _get_quiz_model()
        response = await asyncio.wait_for(
            model.ainvoke(
                [HumanMessage(content=prompt)],
                config={"callbacks": [cost_callback]},
            ),
            timeout=QUIZ_LLM_TIMEOUT_SECONDS,
        )
        result = response.content

        logger.info(
            "quiz_generated",
            tool="quiz_generate",
            topic=topic[:80],
            level=level,
            response_length=len(result),
            **cost_callback.get_cost_summary(),
        )

        return result

    except TimeoutError:
        logger.warning(
            "quiz_generation_timeout",
            tool_name="quiz_generate",
            service="llm",
            topic=topic[:80],
            level=level,
            timeout=QUIZ_LLM_TIMEOUT_SECONDS,
        )
        return "A geração da questão excedeu o tempo limite. Tente novamente em alguns instantes."
    except Exception as exc:
        logger.error(
            "quiz_generation_failed",
            tool_name="quiz_generate",
            service="llm",
            error_type=type(exc).__name__,
            error_message=str(exc),
            topic=topic[:80],
            level=level,
        )
        return (
            "Não foi possível gerar a questão no momento. "
            "O serviço está temporariamente indisponível."
        )
