"""`TicketPurchased` v1 (ticket-purchase design §5.3).

Semantics: activity event, one per purchase, processed once per `eventId`.
Not a state snapshot, so it carries no entity version. UUIDs only, no personal data.
"""

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class TicketPurchasedV1(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, frozen=True)

    TYPE: ClassVar[str] = "TicketPurchased"
    VERSION: ClassVar[int] = 1
    ROUTING_KEY: ClassVar[str] = "ticketing.ticket.purchased"

    purchase_id: UUID
    ticket_id: UUID
    passenger_id: UUID
    ticket_type_id: UUID
    price_cents: int
    currency: str
    issued_at: datetime
