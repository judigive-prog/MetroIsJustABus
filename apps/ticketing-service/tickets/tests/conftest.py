import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.conf import LazySettings
from rest_framework.test import APIClient

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
def passenger_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def passenger(api_client_for: Callable[[uuid.UUID, str], APIClient], passenger_id: uuid.UUID) -> APIClient:
    return api_client_for(passenger_id, "passenger")


@pytest.fixture
def other_passenger_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def other_passenger(api_client_for: Callable[[uuid.UUID, str], APIClient], other_passenger_id: uuid.UUID) -> APIClient:
    return api_client_for(other_passenger_id, "passenger")


@pytest.fixture
def ticket_type() -> TicketType:
    return TicketType.objects.create(
        code="TEN_JOURNEYS",
        name="10-Journey Ticket",
        description="Ten journeys on any line.",
        price_cents=1200,
        currency="EUR",
        terms={"journeys": 10},
    )


@pytest.fixture
def period_ticket_type() -> TicketType:
    return TicketType.objects.create(
        code="DAILY_PASS",
        name="24-Hour Pass",
        description="Unlimited journeys for 24 hours.",
        price_cents=600,
        currency="EUR",
        terms={"period_minutes": 1440},
    )
