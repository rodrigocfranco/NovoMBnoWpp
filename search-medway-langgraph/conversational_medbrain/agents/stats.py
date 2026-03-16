from langchain.agents import create_agent

from workflows.conversational_medbrain.prompts.stats import STATS_SYSTEM_PROMPT
from workflows.utils.functions import get_default_model
from workflows.utils.mcp.galen import MCPGalen


class StatsAgent:
    def __init__(self, access_token):
        self.access_token = access_token
        self.mcp_service = MCPGalen(access_token=access_token)

    async def agent(self):
        mcp_tools = await self.mcp_service.get_mcp_tools()

        return create_agent(
            model=get_default_model(),
            system_prompt=STATS_SYSTEM_PROMPT,
            tools=mcp_tools
        )
