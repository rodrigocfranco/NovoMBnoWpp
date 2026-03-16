from langchain_core.messages import HumanMessage

from smart_content.services.smart_content_service import SmartContentService
from workflows.medbrain_responds.agents.guardrail import get_guardrail_agent
from workflows.medbrain_responds.agents.medical import create_medical_agent
from workflows.medbrain_responds.schemas import GuardRailResponse, MedbrainRespondsState


class MedbrainRespondsGraph:

    def __init__(self):
        pass

    def guardrail_node(self, state: MedbrainRespondsState) -> MedbrainRespondsState:
        guardrail_input = f"""
            <question>
            {state.question_content}
            </question>
            <alternatives>
            {state.question_alternatives}
            </alternatives>
            <student_message>
            {state.student_message}
            </student_message>
        """
        guardrail_agent = get_guardrail_agent()
        response = guardrail_agent.invoke({"messages": [HumanMessage(content=guardrail_input)]})
        result = GuardRailResponse.model_validate_json(response['messages'][-1].content)

        return state.model_copy(update={"is_allowed": result.is_allowed, "queries": result.queries})

    def rag_node(self, state: MedbrainRespondsState) -> MedbrainRespondsState:
        all_rag_results = []

        for query in state.queries[:2]:
            top_k = 4 if len(state.queries) > 1 else 8

            rag_results = SmartContentService().search_content(
                query=query,
                top_k=top_k,
                with_rerank=True,
                search_size=15,
            )

            all_rag_results.extend(rag_results)

        all_rag_results = [rag_result for rag_result in all_rag_results if rag_result["relevance_score"] > 0.5]

        return state.model_copy(update={"rag_results": all_rag_results})

    def medical_node(self, state: MedbrainRespondsState):
        rag_context = "\n\n".join([
            f"[Trecho {i + 1}]\n{result['text']}\nReferência: {result.get('reference_name', 'N/A')}"
            for i, result in enumerate(state.rag_results)
        ])

        medical_input = f"""
            <student_message>
            {state.student_message}
            </student_message>
            <question_stem>
            {state.question_content}
            </question_stem>
            <alternatives>
            {state.question_alternatives}
            </alternatives>
            <question_explanation>
            {state.question_explanation}
            </question_explanation>
            <rag_context>
            {rag_context}
            </rag_context>
        """

        medical_agent = create_medical_agent()

        for chunk, _ in medical_agent.stream(
            {"messages": [HumanMessage(content=medical_input)]}, stream_mode="messages"
        ):
            yield chunk.content

    def execute_stream(
        self, question_content: str, question_alternatives: str, student_message: str, question_explanation: str
    ):
        """
        Execute the graph and stream only the medical agent response.

        Yields:
            str: Chunks of the medical agent response as they are generated.
        """
        # Execute guardrail and RAG nodes first without streaming
        state = MedbrainRespondsState(
            question_content=question_content,
            question_alternatives=question_alternatives,
            student_message=student_message,
            question_explanation=question_explanation
        )

        state = self.guardrail_node(state)

        if not state.is_allowed:
            return "Isso está fora do meu escopo de resposta, sou um assistente específico para essa questão!"

        state = self.rag_node(state)
        return self.medical_node(state)
