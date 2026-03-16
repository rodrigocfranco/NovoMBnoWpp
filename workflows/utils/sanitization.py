"""PII sanitization processor for structlog."""

from typing import Any

SENSITIVE_FIELDS = frozenset(["phone", "name", "email", "cpf", "api_key"])


def _redact_value(value: Any) -> Any:
    """Recursively redact sensitive fields in dicts and lists."""
    if isinstance(value, dict):
        for key in value:
            if key in SENSITIVE_FIELDS:
                value[key] = "***REDACTED***"
            else:
                value[key] = _redact_value(value[key])
    elif isinstance(value, list):
        for i, item in enumerate(value):
            value[i] = _redact_value(item)
    return value


def sanitize_pii(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Redact sensitive PII fields from log events."""
    for field in SENSITIVE_FIELDS:
        if field in event_dict:
            event_dict[field] = "***REDACTED***"
    for key, value in event_dict.items():
        if key not in SENSITIVE_FIELDS:
            event_dict[key] = _redact_value(value)
    return event_dict
