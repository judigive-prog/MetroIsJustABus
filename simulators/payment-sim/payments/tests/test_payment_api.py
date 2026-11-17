import uuid
from unittest.mock import Mock

import pytest
from django.conf import LazySettings
from rest_framework.response import Response
from rest_framework.test import APIClient

from payments import services
from payments.models import Payment

pytestmark = [pytest.mark.integration, pytest.mark.django_db, pytest.mark.req("FR-037")]

PAYMENTS = "/api/payment-sim/v1/payments"


@pytest.fixture
def service_client(settings: LazySettings) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {settings.SERVICE_TOKEN}")
    return client


def pay(client: APIClient, key: uuid.UUID, token: str, *, amount: int = 150) -> Response:
    return client.post(
        PAYMENTS,
        {"amountCents": amount, "currency": "EUR", "paymentMethodToken": token},
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(key),
    )


@pytest.mark.req("NFR-013")
def test_same_key_replays_one_charge_and_different_payload_conflicts(service_client: APIClient) -> None:
    key = uuid.uuid4()

    first = pay(service_client, key, "sim_approve")
    replay = pay(service_client, key, "sim_approve")
    conflict = pay(service_client, key, "sim_approve", amount=151)

    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert service_client.get(f"{PAYMENTS}/{key}").json() == {
        "paymentId": first.json()["paymentId"],
        "status": "APPROVED",
        "requestCount": 2,
        "chargeCount": 1,
    }
    assert Payment.objects.count() == 1


@pytest.mark.parametrize(
    ("token", "reason"),
    [("sim_decline", "DECLINED"), ("invalid-test-token", "INVALID_PAYMENT_METHOD")],
)
def test_declined_payment_has_no_charge(service_client: APIClient, token: str, reason: str) -> None:
    key = uuid.uuid4()

    response = pay(service_client, key, token)

    assert response.status_code == 200
    assert response.json()["status"] == "DECLINED"
    assert response.json()["reason"] == reason
    assert service_client.get(f"{PAYMENTS}/{key}").json()["chargeCount"] == 0


@pytest.mark.req("NFR-013")
def test_transient_error_can_replay_and_charge_once(service_client: APIClient) -> None:
    key = uuid.uuid4()

    failed = pay(service_client, key, "sim_error")
    errored = service_client.get(f"{PAYMENTS}/{key}").json()
    assert failed.status_code == 500
    assert failed.json()["error"]["code"] == "SIMULATED_ERROR"
    assert errored["status"] == "ERRORED"
    assert errored["chargeCount"] == 0

    recovered = pay(service_client, key, "sim_error")
    assert recovered.status_code == 200
    assert recovered.json() == {"paymentId": errored["paymentId"], "status": "APPROVED"}
    state = service_client.get(f"{PAYMENTS}/{key}").json()
    assert state["chargeCount"] == 1
    assert state["requestCount"] == 2
    assert Payment.objects.count() == 1


@pytest.mark.req("NFR-013")
def test_slow_approval_is_recorded_before_response_and_retry_has_no_delay(
    service_client: APIClient, settings: LazySettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    key = uuid.uuid4()
    settings.SIM_SLOW_SECONDS = 4

    def inspect_before_response(seconds: float) -> None:
        assert seconds == settings.SIM_SLOW_SECONDS
        payment = Payment.objects.get(idempotency_key=key)
        assert payment.status == Payment.Status.APPROVED
        assert payment.charge_count == 1

    sleep = Mock(side_effect=inspect_before_response)
    monkeypatch.setattr(services.time, "sleep", sleep)

    first = pay(service_client, key, "sim_slow")
    replay = pay(service_client, key, "sim_slow")

    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    sleep.assert_called_once_with(settings.SIM_SLOW_SECONDS)
    assert service_client.get(f"{PAYMENTS}/{key}").json()["chargeCount"] == 1


@pytest.mark.parametrize("credentials", [{}, {"HTTP_AUTHORIZATION": "Bearer invalid-test-credential"}])
def test_payment_requires_service_token(credentials: dict[str, str]) -> None:
    client = APIClient()
    client.credentials(**credentials)

    response = pay(client, uuid.uuid4(), "sim_approve")

    assert response.status_code == 401
    assert not Payment.objects.exists()
