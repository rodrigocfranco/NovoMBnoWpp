"""Shared fixtures for WhatsApp workflow tests."""


def make_whatsapp_state(**overrides) -> dict:
    """Create a minimal WhatsAppState-like dict for testing.

    Returns a dict with all required WhatsAppState fields populated
    with sensible defaults. Use keyword arguments to override specific fields.
    """
    state = {
        "phone_number": "5511999999999",
        "user_message": "Olá",
        "message_type": "text",
        "media_url": None,
        "media_id": None,
        "mime_type": None,
        "wamid": "wamid.test",
        "user_id": "1",
        "subscription_tier": "free",
        "is_new_user": False,
        "messages": [],
        "formatted_response": "",
        "additional_responses": [],
        "response_sent": False,
        "trace_id": "trace-test",
        "cost_usd": 0.001,
        "retrieved_sources": [],
        "cited_source_indices": [],
        "web_sources": [],
        "transcribed_text": "",
        "rate_limit_exceeded": False,
        "remaining_daily": 0,
        "rate_limit_warning": "",
        "image_message": None,
        "provider_used": "",
        # Cost tracking fields (Story 7.1)
        "tokens_input": 0,
        "tokens_output": 0,
        "tokens_cache_read": 0,
        "tokens_cache_creation": 0,
        "model_used": "",
        "tool_executions": [],
    }
    state.update(overrides)
    return state
