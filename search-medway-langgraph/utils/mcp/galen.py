from langchain_mcp_adapters.client import MultiServerMCPClient
from django.conf import settings


class MCPGalen:
    def __init__(self, access_token):
        self.access_token = access_token
        self.mcp_client = MultiServerMCPClient(
            {
                "medway": {
                    "transport": "http",
                    "url": settings.MCP_GALEN_URL,
                }
            },
            tool_interceptors=[self.inject_user_context]
        )

    async def get_mcp_tools(self):
        return await self.mcp_client.get_tools()  # ✅ awaited here, not in __init__

    async def inject_user_context(self, request, handler):
        modified_request = request.override(
            args={**request.args, "access_token": self.access_token}
        )
        return await handler(modified_request)
