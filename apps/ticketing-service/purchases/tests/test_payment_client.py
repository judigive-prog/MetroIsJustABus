import json
import uuid

import httpx
import pytest
from metro_common.correlation import reset_correlation_id, set_correlation_id

from common.http import ServiceHttpClient
from purchases.clients import HttpPaymentClient, PaymentOutcome, PaymentResult

pytestmark = [pytest.mark.unit, pytest.mark.req("FR-037")]


def test_payment_http_client_sends_simulator_contract_and_correlation_id() -> None:
    purchase_id = uuid.uuid4()
    payment_id = str(uuid.uuid4())

    def receive(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/payment-sim/v1/payments"
        assert request.headers["Idempotency-Key"] == str(purchase_id)
        assert request.headers["Authorization"] == "Bearer fake-service-token"
        assert request.headers["X-Correlation-Id"] == "payment-client-test"
        assert json.loads(request.content) == {
            "amountCents": 150,
            "currency": "EUR",
            "paymentMethodToken": "sim_approve",
        }
        return httpx.Response(200, json={"status": "APPROVED", "paymentId": payment_id})

    client = HttpPaymentClient(
        ServiceHttpClient("http://payment.test", "fake-service-token", transport=httpx.MockTransport(receive))
    )
    token = set_correlation_id("payment-client-test")
    try:
        result = client.pay(
            idempotency_key=purchase_id, amount_cents=150, currency="EUR", payment_method_token="sim_approve"
        )
    finally:
        reset_correlation_id(token)
    assert result == PaymentResult(PaymentOutcome.APPROVED, payment_id=payment_id)


@pytest.mark.req("NFR-013")
@pytest.mark.parametrize("error_type", [httpx.ReadTimeout, httpx.ConnectError])
def test_payment_transport_failure_is_uncertain_after_one_attempt(error_type: type[httpx.HTTPError]) -> None:
    requests: list[httpx.Request] = []

    def fail(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        raise error_type("deliberate test failure")

    client = HttpPaymentClient(
        ServiceHttpClient("http://payment.test", "fake-service-token", transport=httpx.MockTransport(fail))
    )

    result = client.pay(
        idempotency_key=uuid.uuid4(), amount_cents=150, currency="EUR", payment_method_token="sim_approve"
    )

    assert result == PaymentResult(PaymentOutcome.UNCERTAIN)
    assert len(requests) == 1
