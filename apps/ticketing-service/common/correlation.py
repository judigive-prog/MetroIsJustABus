import re
import uuid
from collections.abc import Callable

import structlog
from django.http import HttpRequest, HttpResponse
from metro_common.correlation import HEADER, reset_correlation_id, set_correlation_id

_ALLOWED = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class CorrelationIdMiddleware:
    """Reads `X-Correlation-Id`, creates one when missing or unusable, and returns it (NFR-070)."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming = request.headers.get(HEADER, "")
        correlation_id = incoming if _ALLOWED.match(incoming) else str(uuid.uuid4())
        token = set_correlation_id(correlation_id)
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        try:
            response = self.get_response(request)
        finally:
            structlog.contextvars.unbind_contextvars("correlation_id")
            reset_correlation_id(token)
        response[HEADER] = correlation_id
        return response
