from django.conf import settings
from google.oauth2 import service_account
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_google_vertexai.model_garden import ChatAnthropicVertex
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, create_model
from typing import Any, Optional

from workflows.models.base import ChatRoleChoices


def get_default_model(model_name="gpt-4o-mini", temperature=0):
    return ChatOpenAI(
        model=model_name,
        api_key=settings.OPENAI_API_KEY,
        temperature=temperature
    )


def get_vertex_model(
    temperature: float = 0,
    model: str = "claude-sonnet-4@20250514",
):
    credentials = service_account.Credentials.from_service_account_info(
        settings.CREDS_GOOGLE,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )

    return ChatAnthropicVertex(
        model_name=model,
        project=settings.VERTEX_PROJECT_ID,
        location=settings.VERTEX_LOCATION,
        credentials=credentials,
        temperature=temperature,
        streaming=True
    )


def message_to_role(msg: BaseMessage) -> ChatRoleChoices:
    if isinstance(msg, HumanMessage):
        return ChatRoleChoices.HUMAN
    if isinstance(msg, AIMessage):
        return ChatRoleChoices.AGENT
    if isinstance(msg, SystemMessage):
        return ChatRoleChoices.SYSTEM
    return ChatRoleChoices.AGENT


def json_schema_to_pydantic(tool_name: str, input_schema: dict) -> type[BaseModel]:
    TYPE_MAP = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }

    properties = input_schema.get("properties", {})
    required = input_schema.get("required", [])

    fields = {}
    for field_name, field_info in properties.items():
        python_type = TYPE_MAP.get(field_info.get("type", "string"), Any)

        if field_name in required:
            fields[field_name] = (python_type, ...)
        else:
            fields[field_name] = (Optional[python_type], None)

    return create_model(tool_name, **fields)
