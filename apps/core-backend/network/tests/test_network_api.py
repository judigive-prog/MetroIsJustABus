import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from network.models import Line, Stop

LINES_URL = "/api/core/v1/lines"
STOPS_URL = "/api/core/v1/stops"


def _collect_paginated_codes(client: APIClient, path: str, limit: int) -> list[str]:
    codes: list[str] = []
    next_url: str | None = path
    params: dict[str, int] | None = {"limit": limit}
    while next_url is not None:
        response = client.get(next_url, params) if params is not None else client.get(next_url)
        assert response.status_code == 200
        body = response.json()
        assert len(body["results"]) <= limit
        codes.extend(item["code"] for item in body["results"])
        next_url = body["next"]
        params = None
    return codes


@pytest.mark.django_db
@pytest.mark.req("FR-001")
@pytest.mark.req("FR-024")
@pytest.mark.req("NFR-070")
def test_empty_network_lists_return_empty_results_for_visitor() -> None:
    client = APIClient()

    lines_resp = client.get(LINES_URL, HTTP_X_CORRELATION_ID="net-empty-lines")
    stops_resp = client.get(STOPS_URL, HTTP_X_CORRELATION_ID="net-empty-stops")

    assert lines_resp.status_code == 200
    assert lines_resp["X-Correlation-Id"] == "net-empty-lines"
    assert lines_resp.json() == {"next": None, "previous": None, "results": []}

    assert stops_resp.status_code == 200
    assert stops_resp["X-Correlation-Id"] == "net-empty-stops"
    assert stops_resp.json() == {"next": None, "previous": None, "results": []}


@pytest.mark.django_db
@pytest.mark.req("FR-001")
@pytest.mark.req("FR-024")
@pytest.mark.req("FR-103")
def test_visitor_lists_seeded_lines_and_stops_and_excludes_inactive() -> None:
    call_command("seed_network")
    call_command("seed_network")
    Line.objects.create(code="L-OLD", name="Retired Line", status=Line.Status.INACTIVE)
    Stop.objects.create(code="S-OLD", name="Closed Stop", status=Stop.Status.INACTIVE)

    client = APIClient()
    lines_resp = client.get(LINES_URL)
    stops_resp = client.get(STOPS_URL)

    assert lines_resp.status_code == 200
    assert stops_resp.status_code == 200

    expected_lines = {line.code: (str(line.id), line.name) for line in Line.objects.filter(status=Line.Status.ACTIVE)}
    expected_stops = {stop.code: (str(stop.id), stop.name) for stop in Stop.objects.filter(status=Stop.Status.ACTIVE)}

    assert {item["code"]: (item["id"], item["name"]) for item in lines_resp.json()["results"]} == expected_lines
    assert len(expected_lines) == 2
    assert {item["code"]: (item["id"], item["name"]) for item in stops_resp.json()["results"]} == expected_stops
    assert len(expected_stops) == 4


@pytest.mark.django_db
@pytest.mark.req("FR-001")
@pytest.mark.req("FR-024")
def test_public_network_lists_ignore_unneeded_bearer_header() -> None:
    call_command("seed_network")
    client = APIClient()

    lines_resp = client.get(LINES_URL, HTTP_AUTHORIZATION="Bearer not-required-for-public-network")
    stops_resp = client.get(STOPS_URL, HTTP_AUTHORIZATION="Bearer not-required-for-public-network")

    assert lines_resp.status_code == 200
    assert len(lines_resp.json()["results"]) == 2
    assert stops_resp.status_code == 200
    assert len(stops_resp.json()["results"]) == 4


@pytest.mark.django_db
@pytest.mark.req("FR-001")
def test_network_lists_support_limit_and_cursor_pagination() -> None:
    call_command("seed_network")
    client = APIClient()

    line_codes = _collect_paginated_codes(client, LINES_URL, limit=1)
    stop_codes = _collect_paginated_codes(client, STOPS_URL, limit=2)

    assert set(line_codes) == {"L1", "L2"}
    assert len(line_codes) == 2
    assert set(stop_codes) == {"S-UNI", "S-CEN", "S-HOS", "S-RIV"}
    assert len(stop_codes) == 4


@pytest.mark.django_db
@pytest.mark.req("FR-001")
def test_network_models_enforce_code_uniqueness_and_non_empty_constraints() -> None:
    Line.objects.create(code="L1", name="Line One")
    Stop.objects.create(code="S1", name="Stop One")

    with pytest.raises(IntegrityError), transaction.atomic():
        Line.objects.create(code="L1", name="Duplicate Line")

    with pytest.raises(IntegrityError), transaction.atomic():
        Stop.objects.create(code="S1", name="Duplicate Stop")

    with pytest.raises(IntegrityError), transaction.atomic():
        Line.objects.create(code="", name="Missing Code")

    with pytest.raises(IntegrityError), transaction.atomic():
        Stop.objects.create(code="S2", name="")


@pytest.mark.unit
@pytest.mark.req("FR-001")
def test_openapi_schema_includes_network_list_endpoints_without_warnings() -> None:
    output = StringIO()
    call_command("spectacular", format="openapi-json", validate=True, fail_on_warn=True, stdout=output)
    schema = json.loads(output.getvalue())

    assert "200" in schema["paths"][LINES_URL]["get"]["responses"]
    assert "200" in schema["paths"][STOPS_URL]["get"]["responses"]
