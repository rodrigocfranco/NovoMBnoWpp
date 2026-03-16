from pydantic import BaseModel, Field
from typing import List


class InsightMentor(BaseModel):
    pilar: str = Field(
        description="Pilar analisado, ex: constancia, questoes, provas, horas_estudo"
    )
    status: str = Field(
        description="Status do pilar, ex: critico, meta, supermeta"
    )
    insight_mentor: str = Field(
        description="Insight textual e acionável para o aluno"
    )


class MedbrainInsightsResponse(BaseModel):
    insights: List[InsightMentor] = Field(
        description="Lista de insights gerados para o aluno"
    )
