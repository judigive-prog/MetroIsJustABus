import pytest
from rest_framework.exceptions import NotAuthenticated, ValidationError

from common.errors import DomainError, error_body, exception_handler


class CustomDomainError(DomainError):
    code = "INVALID_CREDENTIALS"
    http_status = 401
    message = "Invalid email or password."


@pytest.mark.unit
@pytest.mark.req("NFR-063")
def test_error_body_structure() -> None:
    body = error_body("TEST_CODE", "Test message")
    assert body["error"]["code"] == "TEST_CODE"
    assert body["error"]["message"] == "Test message"
    assert "correlationId" in body["error"]


@pytest.mark.unit
@pytest.mark.req("NFR-063")
def test_exception_handler_handles_domain_error() -> None:
    response = exception_handler(CustomDomainError(), {})

    assert response.status_code == 401
    assert response.data["error"]["code"] == "INVALID_CREDENTIALS"
    assert response.data["error"]["message"] == "Invalid email or password."


@pytest.mark.unit
@pytest.mark.req("NFR-063")
def test_exception_handler_handles_drf_validation_error() -> None:
    response = exception_handler(ValidationError("Field required"), {})

    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.unit
@pytest.mark.req("NFR-063")
def test_exception_handler_handles_not_authenticated() -> None:
    response = exception_handler(NotAuthenticated(), {})

    assert response.status_code == 401
    assert response.data["error"]["code"] == "NOT_AUTHENTICATED"


@pytest.mark.unit
@pytest.mark.req("NFR-063")
def test_exception_handler_hides_unexpected_error_internals() -> None:
    response = exception_handler(RuntimeError("raw sql trace secret"), {})

    assert response.status_code == 500
    assert response.data["error"]["code"] == "INTERNAL_ERROR"
    assert "raw sql trace secret" not in response.data["error"]["message"]
