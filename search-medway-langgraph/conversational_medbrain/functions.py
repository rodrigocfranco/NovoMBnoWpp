from typing import Optional

from workflows.models import ConversationalMedbrainChatHistory


def get_or_create_chat(chat: Optional[ConversationalMedbrainChatHistory], student_id: Optional[int]):
    if chat:
        history, _ = ConversationalMedbrainChatHistory.objects.get_or_create(
            id=chat.id,
            defaults={'student_id': student_id},
        )
        return history

    return ConversationalMedbrainChatHistory.objects.create(student_id=student_id)
