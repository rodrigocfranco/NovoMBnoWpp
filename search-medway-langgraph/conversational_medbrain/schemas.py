from enum import Enum
from typing import Annotated

from langgraph.graph import add_messages
from pydantic import BaseModel, model_validator


class Action(str, Enum):
    RESPOND = "RESPOND"
    HANDOFF = "HANDOFF"


class Route(str, Enum):
    medical = "medical"
    search = "search"
    stats = "stats"


class ConversationalState(BaseModel):
    messages: Annotated[list, add_messages]


class RouterDecision(BaseModel):
    action: Action
    route: Route | None
    reply: str | None

    @model_validator(mode="after")
    def validate_route_on_handoff(self) -> "RouterDecision":
        if self.action == Action.HANDOFF and self.route is None:
            raise ValueError("route is required when action is HANDOFF")
        return self
