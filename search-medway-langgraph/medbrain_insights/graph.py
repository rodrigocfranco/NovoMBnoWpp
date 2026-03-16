from langchain.agents import create_agent
from langchain.messages import HumanMessage

from workflows.medbrain_insights.prompts import (
    MEDBRAIN_INSIGHTS_SYSTEM_PROMPT,
    MEDBRAIN_INSIGHTS_USER_PROMPT
)
from workflows.medbrain_insights.schemas import MedbrainInsightsResponse
from workflows.medbrain_insights.utils import EvaluationInsightService, prompt_priority, prompt_educational_rules

from workflows.utils.functions import get_default_model


class MedbrainInsightsGraph:
    """
    Graph to generate Medbrain Insights.
    """

    def __init__(
        self,
        reference_date,
        study_days_data,
        questions_data,
        exams_data,
        hours_data,
        residency_degrees
    ):
        self.model = get_default_model()
        self.reference_date = reference_date
        self.residency_degrees = residency_degrees

        self.study_days_data = study_days_data
        self.questions_data = questions_data
        self.exams_data = exams_data
        self.hours_data = hours_data

    def _create_graph(self):
        return create_agent(
            self.model,
            system_prompt=MEDBRAIN_INSIGHTS_SYSTEM_PROMPT.format(
                month_priority=prompt_priority(self.reference_date.month),
                month_educational_rules=prompt_educational_rules(self.reference_date.month)
            ),
            response_format=MedbrainInsightsResponse
        )

    def execute(self):
        agent = self._create_graph()
        service = EvaluationInsightService(residency_degrees=self.residency_degrees, reference_date=self.reference_date)

        # Pilar constancia
        output_constancia = service.evaluate_study_days(self.study_days_data)

        # Pilar Questões e Performance
        output_questions = service.evaluate_questions(self.questions_data)

        # Pilar Provas e Simulados
        output_exams = service.evaluate_exams(self.exams_data)

        # Pilar Horas
        output_hours = service.evaluate_hours(self.hours_data)

        result = agent.invoke(
            {"messages": [HumanMessage(
                MEDBRAIN_INSIGHTS_USER_PROMPT.format(
                    reference_date=self.reference_date.isoformat(),
                    reference_month=self.reference_date.strftime("%b"),
                    output_constancia=output_constancia,
                    output_hours=output_hours,
                    output_questions=output_questions,
                    output_exams=output_exams
                )
            )]}
        )

        return result.get("structured_response").model_dump()["insights"]
