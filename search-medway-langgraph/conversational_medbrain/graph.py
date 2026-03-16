from asgiref.sync import sync_to_async

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, trim_messages
from langchain_core.messages.utils import count_tokens_approximately
from langchain_core.runnables import RunnableConfig
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.types import Command

from utils.checkpointer import DB_URI
from workflows.conversational_medbrain.agents.router import router_agent
from workflows.conversational_medbrain.agents.stats import StatsAgent
from workflows.conversational_medbrain.schemas import ConversationalState, RouterDecision, Action
from workflows.models import ConversationalMedbrainChatHistory, ConversationalMedbrainChatMessage
from workflows.utils.functions import message_to_role

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


class ConversationalWorkflowGraph:

    def __init__(self, chat: ConversationalMedbrainChatHistory, access_token: str):
        self.chat = chat
        self.stats_agent = None

    @classmethod
    async def create(cls, chat: ConversationalMedbrainChatHistory, access_token: str) -> "ConversationalWorkflowGraph":
        instance = cls(chat, access_token)
        instance.stats_agent = await StatsAgent(access_token=access_token).agent()
        return instance

    def _trim_initial_messages(self, state: ConversationalState, max_tokens=1000):
        return trim_messages(
            state.messages,
            strategy="last",
            token_counter=count_tokens_approximately,
            max_tokens=max_tokens,
            start_on="human",
            end_on=("human", "tool"),
        )

    async def router_node(self, state: ConversationalState):
        messages = self._trim_initial_messages(state)
        result = await router_agent.ainvoke({"messages": messages})
        response: RouterDecision = result["structured_response"]

        if response.action == Action.HANDOFF:
            return Command(goto=str(response.route.value))

        return Command(
            update={"messages": [AIMessage(content=response.reply)]},
            goto=END
        )

    @staticmethod
    def mock_medical(state: ConversationalState):
        return Command(
            update={"messages": [AIMessage("Eu sou um médico! Resposta: Use dipirona")]},
            goto=END
        )

    @staticmethod
    def mock_search(state: ConversationalState):
        return Command(
            update={"messages": [AIMessage("Não achei resultados ainda pq ninguém me codou :<")]},
            goto=END
        )

    async def student_stats(self, state: ConversationalState):
        last_message = state.messages[-1]
        result = await self.stats_agent.ainvoke({"messages": [last_message]})
        response_text = result["messages"][-1].content
        return Command(
            update={"messages": [AIMessage(response_text)]},
            goto=END
        )

    async def _save_message(self, message: BaseMessage):
        await sync_to_async(ConversationalMedbrainChatMessage.objects.create)(
            chat=self.chat,
            role=message_to_role(message),
            message=message.content
        )

    async def execute(self, message: str) -> str:
        graph = StateGraph(ConversationalState)
        graph.add_node("router", self.router_node)
        graph.add_node("medical", self.mock_medical)
        graph.add_node("search", self.mock_search)
        graph.add_node("stats", self.student_stats)
        graph.add_edge(START, "router")

        human_message = HumanMessage(content=message)
        config: RunnableConfig = {"configurable": {"thread_id": self.chat.id}}

        async with AsyncPostgresSaver.from_conn_string(DB_URI) as checkpointer:
            compiled_graph = graph.compile(checkpointer=checkpointer)
            await self._save_message(human_message)
            state = await compiled_graph.ainvoke(
                ConversationalState(messages=[human_message]),
                config=config,
            )

        final_response = state["messages"][-1]
        await self._save_message(final_response)
        return final_response.content
