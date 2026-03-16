"""Trace ID middleware for request correlation."""

import uuid

import structlog
from asgiref.sync import iscoroutinefunction, markcoroutinefunction
from django.http import HttpRequest, HttpResponse

logger = structlog.get_logger(__name__)


class TraceIDMiddleware:
    """Generate a UUID trace_id per request and propagate via structlog contextvars.

    Adds X-Trace-ID header to all responses for request correlation.
    """

    async_capable = True
    sync_capable = True

    def __init__(self, get_response: object) -> None:
        self.get_response = get_response
        if iscoroutinefunction(self.get_response):
            markcoroutinefunction(self)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if iscoroutinefunction(self):
            return self.__acall__(request)  # type: ignore[return-value]
        trace_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(trace_id=trace_id)
        try:
            response: HttpResponse = self.get_response(request)  # type: ignore[assignment]
            response["X-Trace-ID"] = trace_id
            return response
        finally:
            structlog.contextvars.unbind_contextvars("trace_id")

    async def __acall__(self, request: HttpRequest) -> HttpResponse:
        trace_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(trace_id=trace_id)
        try:
            response: HttpResponse = await self.get_response(request)  # type: ignore[misc]
            response["X-Trace-ID"] = trace_id
            return response
        finally:
            structlog.contextvars.unbind_contextvars("trace_id")
