from typing import Any

from django.core.management.base import BaseCommand

from ticket_types.models import TicketType

# Demo data for development and the purchase scenarios (OQ-09: one currency, EUR).
# `terms` stays empty: its shape belongs to the ticket-type and validation features.
SEED = [
    {"code": "SINGLE", "name": "Single journey", "description": "One journey on any line.", "price_cents": 150},
    {"code": "TEN_JOURNEYS", "name": "10 journeys", "description": "Ten journeys on any line.", "price_cents": 1200},
]


class Command(BaseCommand):
    help = "Create or update the demo ticket types. Safe to run more than once."

    def handle(self, *args: Any, **options: Any) -> None:
        for item in SEED:
            ticket_type, created = TicketType.objects.update_or_create(
                code=item["code"],
                defaults={**item, "currency": "EUR", "terms": {}, "status": TicketType.Status.ACTIVE},
            )
            self.stdout.write(f"{'created' if created else 'updated'} {ticket_type.code} {ticket_type.id}")
