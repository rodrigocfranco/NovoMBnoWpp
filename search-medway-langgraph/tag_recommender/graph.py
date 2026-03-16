from langchain.agents import create_agent
from langchain.messages import HumanMessage

from workflows.tag_recommender.schemas import TagResponse
from workflows.tag_recommender.prompts import FIND_TAGS_SYSTEM_PROMPT
from workflows.utils.functions import get_default_model


class TagRecommenderGraph:
    """
    Service to find the most relevant tags, based on search input.
    """

    def __init__(self, student_question, tags_options):
        self.model = get_default_model()
        self.student_question = student_question
        self.tags_options = tags_options

    def _create_graph(self):
        return create_agent(
            self.model,
            system_prompt=FIND_TAGS_SYSTEM_PROMPT.format(tags=self.tags_options),
            response_format=TagResponse
        )

    def execute(self):
        agent = self._create_graph()

        result = agent.invoke(
            {"messages": [HumanMessage(f"Busca: {self.student_question}")]}
        )

        return result.get("structured_response")
