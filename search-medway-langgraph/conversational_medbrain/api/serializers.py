from rest_framework import serializers

from workflows.models import ConversationalMedbrainChatHistory


class ConversationMedbrainSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=500)
    chat = serializers.PrimaryKeyRelatedField(
        queryset=ConversationalMedbrainChatHistory.objects.all(), allow_null=True, required=False
    )
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    def validate(self, data):
        chat = data.get('chat')
        student = data['user'].student

        if chat and chat.student_id != student.id:
            raise serializers.ValidationError('Chat não pertence ao estudante')
        return data
