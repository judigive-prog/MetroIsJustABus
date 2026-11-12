import uuid

import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from metro_common.correlation import HEADER

from common.correlation import CorrelationIdMiddleware


@pytest.mark.unit
@pytest.mark.req("NFR-070")
def test_correlation_id_is_created_when_missing() -> None:
    factory = RequestFactory()
    request = factory.get("/health/live")

    def get_response(req: object) -> HttpResponse:
        return HttpResponse(b"ok")

    middleware = CorrelationIdMiddleware(get_response)
    response = middleware(request)

    assert HEADER in response
    # Should be a valid UUIDv4
    uuid.UUID(response[HEADER])


@pytest.mark.unit
@pytest.mark.req("NFR-070")
def test_valid_incoming_correlation_id_is_preserved() -> None:
    factory = RequestFactory()
    custom_cid = "test-corr-id-12345"
    request = factory.get("/health/live", HTTP_X_CORRELATION_ID=custom_cid)

    def get_response(req: object) -> HttpResponse:
        return HttpResponse(b"ok")

    middleware = CorrelationIdMiddleware(get_response)
    response = middleware(request)

    assert response[HEADER] == custom_cid


@pytest.mark.unit
@pytest.mark.req("NFR-070")
def test_malformed_correlation_id_is_replaced() -> None:
    factory = RequestFactory()
    malformed_cid = "invalid correlation id with spaces &!@#"
    request = factory.get("/health/live", HTTP_X_CORRELATION_ID=malformed_cid)

    def get_response(req: object) -> HttpResponse:
        return HttpResponse(b"ok")

    middleware = CorrelationIdMiddleware(get_response)
    response = middleware(request)

    assert response[HEADER] != malformed_cid
    uuid.UUID(response[HEADER])
