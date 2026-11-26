"""Read queries for public network consultation (conventions.md, Code)."""

import uuid
from typing import Any  # Any: nested line-pattern-stops JSON response structure

from django.db.models import Prefetch, QuerySet

from network.models import Line, PatternStop, RoutePattern, Stop


def active_lines() -> QuerySet[Line]:
    return Line.objects.filter(status=Line.Status.ACTIVE)


def active_stops() -> QuerySet[Stop]:
    return Stop.objects.filter(status=Stop.Status.ACTIVE)


def find_active_line(line_id: uuid.UUID) -> Line | None:
    return active_lines().filter(id=line_id).first()


def line_ordered_stops_body(line: Line) -> dict[str, Any]:
    """Return published directional stop sequences for an active line (FR-002)."""
    patterns = (
        RoutePattern.objects.filter(line=line, status=RoutePattern.Status.PUBLISHED)
        .prefetch_related(
            Prefetch(
                "pattern_stops",
                queryset=PatternStop.objects.select_related("stop").order_by("position", "id"),
            )
        )
        .order_by("direction_label", "revision", "id")
    )
    return {
        "lineId": str(line.id),
        "lineCode": line.code,
        "lineName": line.name,
        "patterns": [
            {
                "id": str(pattern.id),
                "directionLabel": pattern.direction_label,
                "revision": pattern.revision,
                "stops": [
                    {
                        "position": item.position,
                        "stopId": str(item.stop.id),
                        "code": item.stop.code,
                        "name": item.stop.name,
                    }
                    for item in pattern.pattern_stops.all()
                ],
            }
            for pattern in patterns
        ],
    }
