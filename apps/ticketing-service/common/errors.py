"""Single error shape and the one exception handler that produces it (conventions.md, API)."""

from typing import Any

import structlog
from django.http import Http404
from metro_common.correlation import get_correlation_id
from rest_framework import exceptions
from rest_framework.response import Response

logger = structlog.get_logger(__name__)


class DomainError(Exception):
    """Base for business errors. Subclasses set `code`, `http_status` and a passenger-readable `message`."""

    code = "BUSINESS_RULE_VIOLATED"
    http_status = 422
    message = "The request could not be completed."


def error_body(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "correlationId": get_correlation_id()}}


_DRF_CODES: list[tuple[type[exceptions.APIException], str, str]] = [
    (exceptions.ValidationError, "VALIDATION_ERROR", "The request is not valid."),
    (exceptions.ParseError, "MALFORMED_REQUEST", "The request body could not be read."),
    (exceptions.NotAuthenticated, "NOT_AUTHENTICATED", "Please sign in to continue."),
    (exceptions.AuthenticationFailed, "NOT_AUTHENTICATED", "Please sign in to continue."),
    (exceptions.PermissionDenied, "PERMISSION_DENIED", "You are not allowed to do this."),
    (exceptions.NotFound, "NOT_FOUND", "The requested item was not found."),
    (exceptions.MethodNotAllowed, "METHOD_NOT_ALLOWED", "This operation is not supported."),
    (exceptions.UnsupportedMediaType, "UNSUPPORTED_MEDIA_TYPE", "Send the request as JSON."),
    (exceptions.Throttled, "THROTTLED", "Too many requests. Please try again later."),
]


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response:
    if isinstance(exc, DomainError):
        return Response(error_body(exc.code, exc.message), status=exc.http_status)

    if isinstance(exc, Http404):
        exc = exceptions.NotFound()

    if isinstance(exc, exceptions.APIException):
        headers: dict[str, str] = {}
        auth_header = getattr(exc, "auth_header", None)
        if auth_header:
            headers["WWW-Authenticate"] = auth_header
        wait = getattr(exc, "wait", None)
        if wait:
            headers["Retry-After"] = str(int(wait))
        for exc_type, code, message in _DRF_CODES:
            if isinstance(exc, exc_type):
                return Response(error_body(code, message), status=exc.status_code, headers=headers)
        return Response(
            error_body("REQUEST_FAILED", "The request could not be completed."),
            status=exc.status_code,
            headers=headers,
        )

    logger.exception("unexpected_failure")
    return Response(error_body("INTERNAL_ERROR", "Something went wrong. Please try again later."), status=500)
