from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from utils.authentication import GalenAuthentication
from utils.functions import create_stream_response
from utils.galen_communication.services.question_service import QuestionService
from workflows.medbrain_responds.api.serializers import MedbrainRespondsInputSerializer
from workflows.medbrain_responds.graph import MedbrainRespondsGraph


class MedbrainRespondsView(APIView):
    authentication_classes = [GalenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = MedbrainRespondsInputSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        question_id = serializer.validated_data["question_id"]
        track_id = serializer.validated_data["track_id"]

        service = QuestionService(token=request.auth)
        summary = service.summary(question_id, params={'track': track_id})

        graph = MedbrainRespondsGraph()

        event_stream = graph.execute_stream(
            question_content=summary.question.content,
            question_alternatives=summary.question.alternatives_text,
            student_message=serializer.validated_data["message"],
            question_explanation=summary.clean_explanation
        )

        return create_stream_response(event_stream)
