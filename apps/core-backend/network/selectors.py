"""Read queries for public network consultation (conventions.md, Code)."""

from django.db.models import QuerySet

from network.models import Line, Stop


def active_lines() -> QuerySet[Line]:
    return Line.objects.filter(status=Line.Status.ACTIVE)


def active_stops() -> QuerySet[Stop]:
    return Stop.objects.filter(status=Stop.Status.ACTIVE)
