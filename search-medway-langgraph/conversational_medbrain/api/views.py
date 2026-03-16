from adrf.views import APIView
from asgiref.sync import sync_to_async

from utils.galen_communication.services.mcp_service import GalenMCPService

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from utils.authentication import GalenAuthentication
from workflows.conversational_medbrain.api.serializers import ConversationMedbrainSerializer
from workflows.conversational_medbrain.functions import get_or_create_chat
from workflows.conversational_medbrain.graph import ConversationalWorkflowGraph


class ConversationalMedbrainView(APIView):
    authentication_classes = [GalenAuthentication]
    permission_classes = [IsAuthenticated]

    async def post(self, request, *args, **kwargs):
        serializer = ConversationMedbrainSerializer(data=request.data, context={'request': request})
        await sync_to_async(serializer.is_valid)(raise_exception=True)

        access_token = request.META.get('HTTP_AUTHORIZATION', '').replace('Bearer ', '')

        # TO BE REMOVED
        access_token = self.generate_provisory_token(access_token)

        user_message = serializer.validated_data["message"]
        user = serializer.validated_data["user"]
        chat = serializer.validated_data.get("chat")

        chat = await sync_to_async(get_or_create_chat)(chat, user.student.id)

        conversational_graph = await ConversationalWorkflowGraph.create(chat, access_token)
        response = await conversational_graph.execute(user_message)

        response_data = {
            'message': response,
            'chat_id': chat.id
        }

        return Response(response_data)

    # TO BE REMOVED
    def generate_provisory_token(self, firebase_token):
        mcp_service = GalenMCPService(token=firebase_token)
        grant_code = mcp_service.get_grant_code()

        return mcp_service.get_mcp_token(grant_code)
