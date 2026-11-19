from typing import Any, TypeVar

from django.core.management.base import BaseCommand

from network.models import Line, NetworkStatus, PatternStop, RoutePattern, Stop

_NetworkModel = TypeVar("_NetworkModel", Line, Stop)

LINES_SEED = [
    {"code": "L1", "name": "University - Central Station"},
    {"code": "L2", "name": "Hospital - Riverside"},
]

STOPS_SEED = [
    {"code": "S-UNI", "name": "University Campus"},
    {"code": "S-CEN", "name": "Central Station"},
    {"code": "S-HOS", "name": "Regional Hospital"},
    {"code": "S-RIV", "name": "Riverside Terminal"},
]

PATTERNS_SEED: list[tuple[str, str, list[str]]] = [
    ("L1", "Outbound", ["S-UNI", "S-CEN", "S-HOS"]),
    ("L1", "Inbound", ["S-HOS", "S-CEN", "S-UNI"]),
    ("L2", "Loop", ["S-HOS", "S-RIV", "S-CEN", "S-HOS"]),
]


class Command(BaseCommand):
    help = "Create or update deterministic demo network lines, stops and patterns. Safe to run more than once."

    def _seed_entities(self, model: type[_NetworkModel], items: list[dict[str, str]]) -> dict[str, _NetworkModel]:
        seeded: dict[str, _NetworkModel] = {}
        for item in items:
            entity, created = model.objects.update_or_create(
                code=item["code"],
                defaults={"name": item["name"], "status": NetworkStatus.ACTIVE},
            )
            seeded[entity.code] = entity
            action = "created" if created else "updated"
            self.stdout.write(f"{action} {model.__name__.lower()} {entity.code} {entity.id}")
        return seeded

    def _seed_patterns(self, lines_by_code: dict[str, Line], stops_by_code: dict[str, Stop]) -> None:
        for line_code, direction_label, stop_codes in PATTERNS_SEED:
            pattern, created = RoutePattern.objects.update_or_create(
                line=lines_by_code[line_code],
                direction_label=direction_label,
                revision=1,
                defaults={"status": RoutePattern.Status.PUBLISHED},
            )
            for position, stop_code in enumerate(stop_codes, start=1):
                PatternStop.objects.update_or_create(
                    pattern=pattern,
                    position=position,
                    defaults={"stop": stops_by_code[stop_code]},
                )
            PatternStop.objects.filter(pattern=pattern, position__gt=len(stop_codes)).delete()
            action = "created" if created else "updated"
            self.stdout.write(f"{action} pattern {line_code}:{direction_label} {pattern.id}")

    def handle(self, *args: Any, **options: Any) -> None:  # Any: Django BaseCommand accepts dynamic options
        lines_by_code = self._seed_entities(Line, LINES_SEED)
        stops_by_code = self._seed_entities(Stop, STOPS_SEED)
        self._seed_patterns(lines_by_code, stops_by_code)
