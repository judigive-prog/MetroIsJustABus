import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from ticket_types.models import TicketType

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

CATALOGUE = "/api/ticketing/v1/ticket-types"


@pytest.mark.req("FR-030")
@pytest.mark.req("FR-031")
def test_catalogue_shows_distinct_active_offers_and_hides_retired_types() -> None:
    call_command("seed_ticket_types")
    TicketType.objects.create(
        code="RETIRED",
        name="Retired pass",
        description="Previously sold",
        price_cents=500,
        currency="EUR",
        status=TicketType.Status.RETIRED,
    )

    response = APIClient().get(CATALOGUE)

    assert response.status_code == 200
    assert {
        item["code"]: (item["priceCents"], item["currency"], item["description"]) for item in response.json()["results"]
    } == {
        "SINGLE": (150, "EUR", "One journey on any line."),
        "TEN_JOURNEYS": (1200, "EUR", "Ten journeys on any line."),
    }


@pytest.mark.req("FR-031")
def test_catalogue_cursor_returns_the_next_type() -> None:
    call_command("seed_ticket_types")
    client = APIClient()

    first = client.get(CATALOGUE, {"limit": 1})
    assert first.status_code == 200
    assert len(first.json()["results"]) == 1
    next_page = client.get(first.json()["next"])
    assert next_page.status_code == 200
    assert len(next_page.json()["results"]) == 1
    assert next_page.json()["next"] is None
    assert {first.json()["results"][0]["code"], next_page.json()["results"][0]["code"]} == {"SINGLE", "TEN_JOURNEYS"}
