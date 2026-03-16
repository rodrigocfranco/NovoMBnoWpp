"""WhatsApp webhook serializers (DRF)."""

import time

from rest_framework import serializers

MAX_TIMESTAMP_AGE_SECONDS = 300


class WhatsAppMessageSerializer(serializers.Serializer):
    """Validate individual WhatsApp message from webhook payload.

    Validates phone format, message type, and timestamp freshness (anti-replay).
    """

    phone = serializers.RegexField(
        regex=r"^\d{10,15}$",
        error_messages={"invalid": "Phone must be 10-15 digits."},
    )
    message_id = serializers.CharField(max_length=200)
    timestamp = serializers.CharField(max_length=20)
    message_type = serializers.CharField(max_length=50)
    body = serializers.CharField(required=False, allow_blank=True, default="")
    media_id = serializers.CharField(required=False, allow_null=True, default=None)
    mime_type = serializers.CharField(required=False, allow_null=True, default=None)
    button_reply_id = serializers.CharField(required=False, allow_null=True, default=None)
    button_reply_title = serializers.CharField(required=False, allow_null=True, default=None)

    def validate_timestamp(self, value: str) -> str:
        """Reject messages older than MAX_TIMESTAMP_AGE_SECONDS (anti-replay)."""
        try:
            ts = int(value)
        except (ValueError, TypeError):
            raise serializers.ValidationError("Invalid timestamp format.")
        age = abs(int(time.time()) - ts)
        if age > MAX_TIMESTAMP_AGE_SECONDS:
            raise serializers.ValidationError(
                f"Timestamp expired: {age}s old (max {MAX_TIMESTAMP_AGE_SECONDS}s)."
            )
        return value

    def validate_message_type(self, value: str) -> str:
        """Reject system and unknown message types."""
        blocked = {"system", "unknown", "ephemeral", "unsupported"}
        if value in blocked:
            raise serializers.ValidationError(f"Message type '{value}' is not processable.")
        return value
