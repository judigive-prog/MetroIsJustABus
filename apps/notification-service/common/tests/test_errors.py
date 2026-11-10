import pytest
from rest_framework.exceptions import NotAuthenticated, ValidationError

from common.errors import DomainError, error_body, exception_handler


class CustomDomainError(DomainError):
    code = "SUBSCRIPTION_ALREADY_EXISTS"
    http_status = 409
    message = "You are already subscribed to this entity."


@pytest.mark.unit
@pytest.mark.req("NFR-006")
def test_error_body_structure() -> None:
    body = error_body("TEST_CODE", "Test message")
    assert "error" in body
    assert body["error"]["code"] == "TEST_CODE"
    assert body["error"]["message"] == "Test message"
    assert "correlationId" in body["error"]


@pytest.mark.unit
@pytest.mark.req("NFR-006")
def test_exception_handler_handles_domain_error() -> None:
    exc = CustomDomainError()
    response = exception_handler(exc, {})

    assert response.status_code == 409
    assert response.data["error"]["code"] == "SUBSCRIPTION_ALREADY_EXISTS"
    assert response.data["error"]["message"] == "You are already subscribed to this entity."


@pytest.mark.unit
@pytest.mark.req("NFR-006")
def test_exception_handler_handles_drf_validation_error() -> None:
    exc = ValidationError("Field required")
    response = exception_handler(exc, {})

    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"
    assert response.data["error"]["message"] == "The request is not valid."


@pytest.mark.unit
@pytest.mark.req("NFR-006")
def test_exception_handler_handles_not_authenticated() -> None:
    exc = NotAuthenticated()
    response = exception_handler(exc, {})

    assert response.status_code == 401
    assert response.data["error"]["code"] == "NOT_AUTHENTICATED"
    assert response.data["error"]["message"] == "Please sign in to continue."


@pytest.mark.unit
@pytest.mark.req("NFR-006")
def test_exception_handler_handles_unexpected_error() -> None:
    exc = RuntimeError("Unexpected failure")
    response = exception_handler(exc, {})

    assert response.status_code == 500
    assert response.data["error"]["code"] == "INTERNAL_ERROR"
