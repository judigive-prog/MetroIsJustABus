import uuid

import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from metro_common.correlation import HEADER

from common.correlation import CorrelationIdMiddleware


@pytest.mark.unit
@pytest.mark.req("NFR-070")
def test_correlation_id_is_created_when_missing() -> None:
    request = RequestFactory().get("/health/live")

    middleware = CorrelationIdMiddleware(lambda _req: HttpResponse(b"ok"))
    response = middleware(request)

    assert HEADER in response
    uuid.UUID(response[HEADER])


@pytest.mark.unit
@pytest.mark.req("NFR-070")
def test_valid_incoming_correlation_id_is_preserved() -> None:
    custom_cid = "core-corr-id-12345"
    request = RequestFactory().get("/health/live", HTTP_X_CORRELATION_ID=custom_cid)

    middleware = CorrelationIdMiddleware(lambda _req: HttpResponse(b"ok"))
    response = middleware(request)

    assert response[HEADER] == custom_cid


@pytest.mark.unit
@pytest.mark.req("NFR-070")
def test_malformed_correlation_id_is_replaced() -> None:
    malformed_cid = "invalid correlation id &!@#"
    request = RequestFactory().get("/health/live", HTTP_X_CORRELATION_ID=malformed_cid)

    middleware = CorrelationIdMiddleware(lambda _req: HttpResponse(b"ok"))
    response = middleware(request)

    assert response[HEADER] != malformed_cid
    uuid.UUID(response[HEADER])
