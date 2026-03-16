from langchain.agents import create_agent

from workflows.conversational_medbrain.prompts.router import ROUTER_SYSTEM_PROMPT
from workflows.conversational_medbrain.schemas import RouterDecision
from workflows.utils.functions import get_default_model

router_agent = create_agent(
    model=get_default_model(),
    system_prompt=ROUTER_SYSTEM_PROMPT,
    response_format=RouterDecision,
)
