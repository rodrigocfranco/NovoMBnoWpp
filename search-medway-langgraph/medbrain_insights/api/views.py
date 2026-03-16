from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_api_key.permissions import HasAPIKey

from workflows.medbrain_insights.graph import MedbrainInsightsGraph
from workflows.medbrain_insights.api.serializers import MedbrainInsightsInputSerializer


class MedbrainInsightsViewSet(APIView):
    permission_classes = [HasAPIKey]

    def post(self, request, *args, **kwargs):
        serializer = MedbrainInsightsInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        id_aluno = serializer.validated_data['id_aluno']
        reference_date = serializer.validated_data['data_referencia']

        insights_graph = MedbrainInsightsGraph(
            reference_date=reference_date,
            questions_data=serializer.validated_data['questoes'],
            exams_data=serializer.validated_data['provas_simulados'],
            hours_data=serializer.validated_data['horas_estudo'],
            study_days_data=serializer.validated_data['dias_estudo'],
            residency_degrees=serializer.validated_data['residency_degrees'],
        )

        output_insights = insights_graph.execute()

        return Response({
            "output": {
                "data_referencia": reference_date,
                "id_aluno": id_aluno,
                "insights": output_insights
            }
        })
