from django.db import models

from workflows.models.base import ChatMessage


class ConversationalMedbrainChatHistory(models.Model):
    student_id = models.IntegerField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Student: {self.student_id} - On Chat: {self.id}'


class ConversationalMedbrainChatMessage(ChatMessage):
    chat = models.ForeignKey(
        ConversationalMedbrainChatHistory, on_delete=models.CASCADE, related_name='messages'
    )
