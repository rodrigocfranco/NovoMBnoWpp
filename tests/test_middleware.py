"""Tests for WebhookSignatureMiddleware and TraceIDMiddleware."""

import hashlib
import hmac
import uuid

import structlog
from django.test import RequestFactory, override_settings

from workflows.middleware.trace_id import TraceIDMiddleware
from workflows.middleware.webhook_signature import WebhookSignatureMiddleware

WEBHOOK_SECRET = "test-webhook-secret"


def _make_sync_response(request):
    """Sync get_response for middleware testing."""
    from django.http import HttpResponse

    return HttpResponse("OK", status=200)


def _sign_payload(body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    """Generate valid HMAC SHA-256 signature for a payload."""
    return (
        "sha256="
        + hmac.new(
            secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
    )


class TestWebhookSignatureMiddleware:
    """Tests for HMAC SHA-256 webhook signature validation."""

    @override_settings(WHATSAPP_WEBHOOK_SECRET=WEBHOOK_SECRET)
    def test_valid_hmac_returns_200(self):
        """AC1: Valid HMAC signature allows request through."""
        factory = RequestFactory()
        body = b'{"test": "payload"}'
        signature = _sign_payload(body)

        request = factory.post(
            "/webhook/whatsapp/",
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=signature,
        )

        middleware = WebhookSignatureMiddleware(_make_sync_response)
        response = middleware(request)
        assert response.status_code == 200

    @override_settings(WHATSAPP_WEBHOOK_SECRET=WEBHOOK_SECRET)
    def test_invalid_hmac_returns_401(self):
        """AC2: Invalid HMAC signature returns 401."""
        factory = RequestFactory()
        body = b'{"test": "payload"}'

        request = factory.post(
            "/webhook/whatsapp/",
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256="sha256=invalid_signature_here",
        )

        middleware = WebhookSignatureMiddleware(_make_sync_response)
        response = middleware(request)
        assert response.status_code == 401

    @override_settings(WHATSAPP_WEBHOOK_SECRET=WEBHOOK_SECRET)
    def test_missing_hmac_returns_401(self):
        """AC2: Missing HMAC signature returns 401."""
        factory = RequestFactory()
        body = b'{"test": "payload"}'

        request = factory.post(
            "/webhook/whatsapp/",
            data=body,
            content_type="application/json",
        )

        middleware = WebhookSignatureMiddleware(_make_sync_response)
        response = middleware(request)
        assert response.status_code == 401

    @override_settings(WHATSAPP_WEBHOOK_SECRET=WEBHOOK_SECRET)
    def test_non_webhook_route_skips_validation(self):
        """Middleware only applies to /webhook/ routes."""
        factory = RequestFactory()

        request = factory.post(
            "/admin/",
            data=b"no signature needed",
            content_type="application/json",
        )

        middleware = WebhookSignatureMiddleware(_make_sync_response)
        response = middleware(request)
        assert response.status_code == 200

    @override_settings(WHATSAPP_WEBHOOK_SECRET=WEBHOOK_SECRET)
    def test_hmac_uses_raw_body(self):
        """HMAC is computed against raw body bytes, not parsed data."""
        factory = RequestFactory()
        body = b'{"emoji": "\\u2764"}'  # Unicode escaped
        signature = _sign_payload(body)

        request = factory.post(
            "/webhook/whatsapp/",
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=signature,
        )

        middleware = WebhookSignatureMiddleware(_make_sync_response)
        response = middleware(request)
        assert response.status_code == 200


class TestTraceIDMiddleware:
    """Tests for TraceIDMiddleware."""

    def test_trace_id_generated_and_in_response_header(self):
        """AC4: UUID trace_id is generated and added to response header."""
        factory = RequestFactory()
        request = factory.get("/webhook/whatsapp/")

        middleware = TraceIDMiddleware(_make_sync_response)
        response = middleware(request)

        trace_id = response.get("X-Trace-ID")
        assert trace_id is not None
        uuid.UUID(trace_id)  # Validates it's a proper UUID

    def test_trace_id_is_unique_per_request(self):
        """Each request gets a unique trace_id."""
        factory = RequestFactory()
        middleware = TraceIDMiddleware(_make_sync_response)

        request1 = factory.get("/any-path/")
        response1 = middleware(request1)

        request2 = factory.get("/any-path/")
        response2 = middleware(request2)

        assert response1["X-Trace-ID"] != response2["X-Trace-ID"]

    def test_trace_id_bound_to_structlog_contextvars(self):
        """AC4: trace_id is propagated via structlog contextvars during request."""
        factory = RequestFactory()
        request = factory.get("/any-path/")

        captured_trace_id = None

        def capture_contextvars(req):
            nonlocal captured_trace_id
            ctx = structlog.contextvars.get_contextvars()
            captured_trace_id = ctx.get("trace_id")
            from django.http import HttpResponse

            return HttpResponse("OK", status=200)

        middleware = TraceIDMiddleware(capture_contextvars)
        response = middleware(request)

        assert captured_trace_id is not None
        assert captured_trace_id == response["X-Trace-ID"]

    def test_trace_id_unbound_after_request(self):
        """trace_id is cleaned up after request to prevent context leak."""
        factory = RequestFactory()
        request = factory.get("/any-path/")

        middleware = TraceIDMiddleware(_make_sync_response)
        middleware(request)

        ctx = structlog.contextvars.get_contextvars()
        assert "trace_id" not in ctx
