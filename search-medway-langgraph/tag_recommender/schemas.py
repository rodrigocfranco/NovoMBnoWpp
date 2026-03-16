from pydantic import BaseModel, Field


class TagExplanation(BaseModel):
    name: str = Field(description="Nome do assunto achado")
    explanation: str = Field(
        description=(
            "Explicação breve de no máximo 1 frase "
            "sobre o motivo do assunto ser selecionado."
        )
    )


class TagResponse(BaseModel):
    response: str = Field(description="Resposta ou comentário")
    recommended_tags: list[TagExplanation] = Field(
        description="Lista com no máximo 10 assuntos mais relevantes."
    )
