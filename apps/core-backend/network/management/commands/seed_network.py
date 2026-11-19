from typing import Any

from django.core.management.base import BaseCommand

from network.models import Line, NetworkStatus, Stop

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


class Command(BaseCommand):
    help = "Create or update deterministic demo network lines and stops. Safe to run more than once."

    def _seed_entities(self, model: type[Line] | type[Stop], items: list[dict[str, str]]) -> None:
        for item in items:
            entity, created = model.objects.update_or_create(
                code=item["code"],
                defaults={"name": item["name"], "status": NetworkStatus.ACTIVE},
            )
            action = "created" if created else "updated"
            self.stdout.write(f"{action} {model.__name__.lower()} {entity.code} {entity.id}")

    def handle(self, *args: Any, **options: Any) -> None:  # Any: Django BaseCommand accepts dynamic options
        self._seed_entities(Line, LINES_SEED)
        self._seed_entities(Stop, STOPS_SEED)
