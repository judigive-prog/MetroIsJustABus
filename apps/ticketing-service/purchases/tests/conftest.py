import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.conf import LazySettings
from rest_framework.test import APIClient

from purchases.clients import PaymentClient, PaymentOutcome, PaymentResult
from ticket_types.models import TicketType


@pytest.fixture(scope="session")
def signing_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def api_client_for(settings: LazySettings, signing_key: rsa.RSAPrivateKey) -> Callable[[uuid.UUID, str], APIClient]:
    settings.JWT_PUBLIC_KEY = signing_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    settings.JWT_ISSUER = "ticketing-test"
    issuer = settings.JWT_ISSUER

    def build(passenger_id: uuid.UUID, role: str = "passenger") -> APIClient:
        token = jwt.encode(
            {
                "sub": str(passenger_id),
                "role": role,
                "iss": issuer,
                "exp": datetime.now(UTC) + timedelta(minutes=5),
            },
            signing_key,
            algorithm="RS256",
        )
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client

    return build


@pytest.fixture
def passenger(api_client_for: Callable[[uuid.UUID, str], APIClient]) -> APIClient:
    return api_client_for(uuid.uuid4(), "passenger")


@pytest.fixture
def ticket_type() -> TicketType:
    return TicketType.objects.create(
        code="SINGLE",
        name="Single journey",
        description="One journey on any line.",
        price_cents=150,
        currency="EUR",
        terms={"journeys": 1},
    )


@pytest.fixture
def payment(monkeypatch: pytest.MonkeyPatch) -> Mock:
    client = Mock(spec=PaymentClient)
    client.pay.return_value = PaymentResult(PaymentOutcome.APPROVED, payment_id=str(uuid.uuid4()))
    monkeypatch.setattr("purchases.api.views.get_payment_client", lambda: client)
    return client
