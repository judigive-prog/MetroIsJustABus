"""Standard event envelope (conventions.md, Events)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class EventEnvelope(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, frozen=True)

    event_id: UUID
    type: str
    version: int
    producer: str
    occurred_at: datetime
    correlation_id: str
    # Any: the payload is the JSON form of a versioned event model, validated by that model.
    payload: dict[str, Any]
