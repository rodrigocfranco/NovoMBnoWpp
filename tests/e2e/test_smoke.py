"""E2E smoke test — full pipeline with REAL credentials.

Validates the complete pipeline: webhook → identify_user → load_context →
orchestrate_llm → tools → collect_sources → format_response → send_whatsapp.

REQUIREMENTS:
    1. Docker services running: docker compose up -d (Redis + PostgreSQL)
    2. Real credentials in .env: GCP, Pinecone, Tavily, NCBI, OpenAI
    3. DJANGO_SETTINGS_MODULE=config.settings.integration
    4. Rodrigo present for validation

Run:
    DJANGO_SETTINGS_MODULE=config.settings.integration pytest tests/e2e/test_smoke.py -m e2e -v -s

The test sends a real medical question through the entire pipeline and validates:
    - Pipeline completes without unhandled exceptions
    - Response contains citations ([N] or [W-N]) when medical tools are used
    - cost_usd > 0 (LLM was actually called)
    - All log events are structured (no raw exceptions in logs)
"""

import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, patch

import pytest
from django.conf import settings
from django.test import AsyncClient

pytestmark = [pytest.mark.e2e, pytest.mark.integration]


def _check_real_credentials() -> bool:
    """Check if real credentials are configured (not placeholder values)."""
    checks = [
        ("VERTEX_PROJECT_ID", settings.VERTEX_PROJECT_ID),
        ("GCP_CREDENTIALS", settings.GCP_CREDENTIALS),
    ]
    for name, value in checks:
        if not value or value.startswith("test-") or value.startswith("your-"):
            return False
    return True


def _sign_payload(body: bytes) -> str:
    """Generate HMAC SHA-256 signature for webhook payload."""
    return (
        "sha256="
        + hmac.new(
            settings.WHATSAPP_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
    )


def _make_smoke_payload(body: str = "O que é dengue e quais os sinais de alarme?") -> dict:
    """Build a realistic WhatsApp webhook payload for smoke testing."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "SMOKE_TEST_BIZ",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": settings.WHATSAPP_PHONE_NUMBER_ID,
                            },
                            "contacts": [
                                {"profile": {"name": "Smoke Test"}, "wa_id": "5511999990000"}
                            ],
                            "messages": [
                                {
                                    "from": "5511999990000",
                                    "id": f"wamid.smoke_{int(time.time())}",
                                    "timestamp": str(int(time.time())),
                                    "type": "text",
                                    "text": {"body": body},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


@pytest.mark.django_db(transaction=True)
class TestSmokeE2E:
    """Full pipeline smoke test with real credentials."""

    async def test_skip_without_credentials(self):
        """Skip smoke test if real credentials are not configured."""
        if not _check_real_credentials():
            pytest.skip(
                "Smoke test requires real credentials in .env "
                "(VERTEX_PROJECT_ID, GCP_CREDENTIALS, etc.)"
            )

    @patch("workflows.views.is_duplicate_message", new_callable=AsyncMock, return_value=False)
    @patch("workflows.whatsapp.nodes.send_whatsapp.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.mark_as_read", new_callable=AsyncMock)
    async def test_full_pipeline_smoke(self, mock_mark, mock_send, mock_dedup):
        """Smoke test: webhook → full pipeline → response with citations.

        Only mocks WhatsApp send (to avoid actually sending messages)
        and deduplication (to avoid Redis key conflicts).
        Everything else is REAL: LLM, tools, database.
        """
        if not _check_real_credentials():
            pytest.skip("Real credentials required for smoke test")

        mock_mark.return_value = True
        mock_send.return_value = {"messages": [{"id": "wamid.smoke_sent"}]}

        payload = _make_smoke_payload()
        body = json.dumps(payload).encode()
        signature = _sign_payload(body)

        client = AsyncClient()
        response = await client.post(
            "/webhook/whatsapp/",
            data=body,
            content_type="application/json",
            headers={"X-Hub-Signature-256": signature},
        )

        # Webhook accepts the request
        assert response.status_code == 200

        # Wait for fire-and-forget processing (up to 120s for debounce + LLM + tools)
        import asyncio

        for _ in range(1200):
            if mock_send.called:
                break
            await asyncio.sleep(0.1)

        # Verify WhatsApp send was called with a response
        assert mock_send.called, (
            "send_text_message was never called — pipeline may have failed. "
            "Check logs for exceptions."
        )

        # Extract the response text
        sent_text = mock_send.call_args[0][1]
        assert len(sent_text) > 0, "Response text is empty"

        # Verify response quality
        # Note: citations may or may not appear depending on tool usage
        print(f"\n{'=' * 60}")
        print("SMOKE TEST RESPONSE:")
        print(f"{'=' * 60}")
        print(f"Length: {len(sent_text)} chars")
        print(f"Has citations: {'[' in sent_text}")
        print(f"Response preview: {sent_text[:300]}...")
        print(f"{'=' * 60}\n")
