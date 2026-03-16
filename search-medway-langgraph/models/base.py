from django.db import models


class ChatRoleChoices(models.IntegerChoices):
    SYSTEM = (1, 'System')
    HUMAN = (2, 'Human')
    AGENT = (3, 'Agent')


class ChatMessage(models.Model):
    role = models.IntegerField(choices=ChatRoleChoices)  # type: ignore[arg-type]
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.role}: {self.message}'

    class Meta:
        abstract = True
