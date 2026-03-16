from typing import Optional

from pydantic import BaseModel, Field


class GuardRailResponse(BaseModel):
    is_allowed: bool
    queries: list[str] = Field(
        description=(
            "Lista de 1 a 2 queries de busca. "
            "Use 2 queries se abordarem aspectos diferentes e complementares do tema. "
            "Se uma query é suficiente, retorne lista com apenas 1 elemento."
        ),
        min_length=0,
        max_length=2
    )
    reason: str = Field(
        description=(
            "Explicação breve do motivo da decisão do is_allowed."
        )
    )


class MedbrainRespondsState(BaseModel):
    question_content: str
    question_alternatives: str
    question_explanation: str = ""
    student_message: str = ""
    is_allowed: Optional[bool] = None
    queries: Optional[list[str]] = None
    rag_results: Optional[list[dict]] = None
    final_message: Optional[str] = None
