"""Webhook signature validation middleware (HMAC SHA-256)."""

import hashlib
import hmac

import structlog
from asgiref.sync import iscoroutinefunction, markcoroutinefunction
from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse

logger = structlog.get_logger(__name__)


class WebhookSignatureMiddleware:
    """Validate X-Hub-Signature-256 header for webhook routes only.

    Async-capable middleware that validates HMAC SHA-256 signatures
    on incoming webhook requests from Meta. Applies only to /webhook/ routes.
    """

    async_capable = True
    sync_capable = True

    def __init__(self, get_response: object) -> None:
        self.get_response = get_response
        if iscoroutinefunction(self.get_response):
            markcoroutinefunction(self)

    def _should_validate(self, request: HttpRequest) -> bool:
        """Only validate POST requests to /webhook/ routes."""
        return request.method == "POST" and request.path.startswith("/webhook/")

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if iscoroutinefunction(self):
            return self.__acall__(request)  # type: ignore[return-value]
        if self._should_validate(request):
            error_response = self._validate_signature(request)
            if error_response:
                return error_response
        return self.get_response(request)  # type: ignore[return-value]

    async def __acall__(self, request: HttpRequest) -> HttpResponse:
        if self._should_validate(request):
            error_response = self._validate_signature(request)
            if error_response:
                return error_response
        return await self.get_response(request)  # type: ignore[misc]

    def _validate_signature(self, request: HttpRequest) -> HttpResponse | None:
        """Validate HMAC SHA-256 signature against raw body.

        Returns JsonResponse(401) if invalid, None if valid.
        """
        signature = request.META.get("HTTP_X_HUB_SIGNATURE_256")

        if not signature:
            logger.warning("webhook_signature_invalid", reason="missing_signature")
            return JsonResponse({"error": "Missing signature"}, status=401)

        expected = (
            "sha256="
            + hmac.new(
                settings.WHATSAPP_WEBHOOK_SECRET.encode(),
                request.body,
                hashlib.sha256,
            ).hexdigest()
        )

        if not hmac.compare_digest(signature, expected):
            logger.warning("webhook_signature_invalid", reason="invalid_signature")
            return JsonResponse({"error": "Invalid signature"}, status=401)

        return None
