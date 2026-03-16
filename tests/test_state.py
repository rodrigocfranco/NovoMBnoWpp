"""Tests for WhatsAppState TypedDict (AC4)."""

from langchain_core.messages import AIMessage, HumanMessage

from workflows.whatsapp.state import WhatsAppState


class TestWhatsAppState:
    """AC4: WhatsAppState contém todos os campos necessários."""

    def test_state_accepts_all_defined_fields(self):
        """WhatsAppState aceita todos os campos do pipeline."""
        state: WhatsAppState = {
            # Input
            "phone_number": "5511999999999",
            "user_message": "Olá Medbrain!",
            "message_type": "text",
            "media_url": None,
            "wamid": "wamid.test123",
            # Identification
            "user_id": "42",
            "subscription_tier": "free",
            # Context (add_messages reducer)
            "messages": [HumanMessage(content="Olá")],
            # Output (placeholder)
            "formatted_response": "",
            "response_sent": False,
            # Observability
            "trace_id": "trace-abc-123",
            "cost_usd": 0.0,
            # Citation (placeholder)
            "retrieved_sources": [],
            "cited_source_indices": [],
            "web_sources": [],
            # Audio transcription (placeholder)
            "transcribed_text": "",
        }
        assert state["phone_number"] == "5511999999999"
        assert state["user_id"] == "42"
        assert state["subscription_tier"] == "free"
        assert len(state["messages"]) == 1
        assert state["response_sent"] is False

    def test_messages_field_accepts_langchain_messages(self):
        """AC4: Campo messages aceita HumanMessage e AIMessage."""
        state: WhatsAppState = {
            "phone_number": "5511999999999",
            "user_message": "",
            "message_type": "text",
            "media_url": None,
            "wamid": "wamid.1",
            "user_id": "1",
            "subscription_tier": "free",
            "messages": [
                HumanMessage(content="Qual a dose de dipirona?"),
                AIMessage(content="A dose usual de dipirona..."),
            ],
            "formatted_response": "",
            "response_sent": False,
            "trace_id": "",
            "cost_usd": 0.0,
            "retrieved_sources": [],
            "cited_source_indices": [],
            "web_sources": [],
            "transcribed_text": "",
        }
        assert isinstance(state["messages"][0], HumanMessage)
        assert isinstance(state["messages"][1], AIMessage)

    def test_state_partial_update_dict(self):
        """Nós retornam dict parcial (apenas campos alterados)."""
        partial: dict = {"user_id": "99", "subscription_tier": "premium"}
        assert partial["user_id"] == "99"
        assert partial["subscription_tier"] == "premium"
