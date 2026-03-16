from charset_normalizer.md import lru_cache
from langchain.agents import create_agent

from workflows.medbrain_responds.prompts import GUARDRAIL_PROMPT
from workflows.utils.functions import get_default_model


@lru_cache(maxsize=1)
def get_guardrail_agent():
    return create_agent(
        model=get_default_model(),
        system_prompt=GUARDRAIL_PROMPT,
    )
