from functools import lru_cache

from langchain.agents import create_agent

from workflows.medbrain_responds.prompts import MEDICAL_PROMPT
from workflows.utils.functions import get_vertex_model


@lru_cache(maxsize=1)
def create_medical_agent():
    return create_agent(
        model=get_vertex_model(temperature=0.1),
        system_prompt=MEDICAL_PROMPT,
    )
