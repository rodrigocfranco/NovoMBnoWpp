from rest_framework import serializers


class MedbrainRespondsInputSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    track_id = serializers.IntegerField()
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    message = serializers.CharField(max_length=500)
