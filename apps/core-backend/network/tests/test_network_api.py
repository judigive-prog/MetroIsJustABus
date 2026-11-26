import json
import uuid
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from network.models import Line, PatternStop, RoutePattern, Stop

LINES_URL = "/api/core/v1/lines"
STOPS_URL = "/api/core/v1/stops"


def _line_stops_url(line_id: uuid.UUID) -> str:
    return f"/api/core/v1/lines/{line_id}/stops"


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
@pytest.mark.req("FR-002")
@pytest.mark.req("FR-024")
@pytest.mark.req("NFR-070")
def test_line_ordered_stops_preserves_non_alphabetical_sequences_directions_and_loops() -> None:
    call_command("seed_network")
    l1 = Line.objects.get(code="L1")
    l2 = Line.objects.get(code="L2")
    client = APIClient()

    l1_resp = client.get(_line_stops_url(l1.id), HTTP_X_CORRELATION_ID="corr-l1-stops")
    l2_resp = client.get(
        _line_stops_url(l2.id),
        HTTP_X_CORRELATION_ID="corr-l2-stops",
        HTTP_AUTHORIZATION="Bearer not-required-for-public-network",
    )

    assert l1_resp.status_code == 200
    assert l1_resp["X-Correlation-Id"] == "corr-l1-stops"
    l1_body = l1_resp.json()
    assert l1_body["lineId"] == str(l1.id)
    assert l1_body["lineCode"] == "L1"
    assert [(p["directionLabel"], [s["code"] for s in p["stops"]]) for p in l1_body["patterns"]] == [
        ("Inbound", ["S-HOS", "S-CEN", "S-UNI"]),
        ("Outbound", ["S-UNI", "S-CEN", "S-HOS"]),
    ]
    assert [s["position"] for s in l1_body["patterns"][1]["stops"]] == [1, 2, 3]

    assert l2_resp.status_code == 200
    assert l2_resp["X-Correlation-Id"] == "corr-l2-stops"
    l2_body = l2_resp.json()
    assert [(p["directionLabel"], [s["code"] for s in p["stops"]]) for p in l2_body["patterns"]] == [
        ("Loop", ["S-HOS", "S-RIV", "S-CEN", "S-HOS"]),
    ]
    loop_stops = l2_body["patterns"][0]["stops"]
    assert [s["position"] for s in loop_stops] == [1, 2, 3, 4]
    assert loop_stops[0]["stopId"] == loop_stops[3]["stopId"]


@pytest.mark.django_db
@pytest.mark.req("FR-002")
@pytest.mark.req("FR-103")
def test_line_ordered_stops_excludes_draft_and_retired_patterns_and_handles_empty_line() -> None:
    line = Line.objects.create(code="L-NEW", name="New Line")
    stop = Stop.objects.create(code="S-1", name="Stop One")
    draft = RoutePattern.objects.create(line=line, direction_label="Outbound", revision=2, status="DRAFT")
    retired = RoutePattern.objects.create(line=line, direction_label="Outbound", revision=1, status="RETIRED")
    PatternStop.objects.create(pattern=draft, stop=stop, position=1)
    PatternStop.objects.create(pattern=retired, stop=stop, position=1)

    response = APIClient().get(_line_stops_url(line.id))

    assert response.status_code == 200
    assert response.json()["patterns"] == []


@pytest.mark.django_db
@pytest.mark.req("FR-002")
@pytest.mark.req("FR-103")
@pytest.mark.req("NFR-063")
def test_line_ordered_stops_returns_404_for_missing_or_inactive_line() -> None:
    inactive_line = Line.objects.create(code="L-OFF", name="Inactive Line", status=Line.Status.INACTIVE)
    client = APIClient()

    missing_resp = client.get(_line_stops_url(uuid.uuid4()), HTTP_X_CORRELATION_ID="corr-missing-line")
    inactive_resp = client.get(_line_stops_url(inactive_line.id), HTTP_X_CORRELATION_ID="corr-inactive-line")

    assert missing_resp.status_code == 404
    assert missing_resp.json()["error"]["code"] == "NOT_FOUND"
    assert missing_resp.json()["error"]["correlationId"] == "corr-missing-line"

    assert inactive_resp.status_code == 404
    assert inactive_resp.json()["error"]["code"] == "NOT_FOUND"
    assert inactive_resp.json()["error"]["correlationId"] == "corr-inactive-line"


@pytest.mark.django_db
@pytest.mark.req("FR-001")
@pytest.mark.req("FR-002")
def test_network_models_enforce_code_uniqueness_positions_and_non_empty_constraints() -> None:
    line = Line.objects.create(code="L1", name="Line One")
    stop = Stop.objects.create(code="S1", name="Stop One")
    pattern = RoutePattern.objects.create(line=line, direction_label="Outbound", revision=1)
    PatternStop.objects.create(pattern=pattern, stop=stop, position=1)

    with pytest.raises(IntegrityError), transaction.atomic():
        Line.objects.create(code="L1", name="Duplicate Line")

    with pytest.raises(IntegrityError), transaction.atomic():
        Stop.objects.create(code="S1", name="Duplicate Stop")

    with pytest.raises(IntegrityError), transaction.atomic():
        Line.objects.create(code="", name="Missing Code")

    with pytest.raises(IntegrityError), transaction.atomic():
        Stop.objects.create(code="S2", name="")

    with pytest.raises(IntegrityError), transaction.atomic():
        RoutePattern.objects.create(line=line, direction_label="", revision=1)

    with pytest.raises(IntegrityError), transaction.atomic():
        RoutePattern.objects.create(line=line, direction_label="Outbound", revision=2, status="PUBLISHED")

    with pytest.raises(IntegrityError), transaction.atomic():
        PatternStop.objects.create(pattern=pattern, stop=stop, position=1)

    with pytest.raises(IntegrityError), transaction.atomic():
        PatternStop.objects.create(pattern=pattern, stop=stop, position=0)


@pytest.mark.unit
@pytest.mark.req("FR-001")
@pytest.mark.req("FR-002")
def test_openapi_schema_includes_network_endpoints_without_warnings() -> None:
    output = StringIO()
    call_command("spectacular", format="openapi-json", validate=True, fail_on_warn=True, stdout=output)
    schema = json.loads(output.getvalue())

    assert "200" in schema["paths"][LINES_URL]["get"]["responses"]
    assert "200" in schema["paths"][STOPS_URL]["get"]["responses"]
    line_stops_op = schema["paths"]["/api/core/v1/lines/{line_id}/stops"]["get"]
    assert "200" in line_stops_op["responses"]
    assert "404" in line_stops_op["responses"]
