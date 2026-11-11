"""Generate the existing TicketPurchased v1 wire contract (NFR-006).

Run from the repository root using the metro_common environment. This module
only describes the contract; it does not publish events or modify runtime models.
"""

import argparse
import json
from pathlib import Path

from metro_common.events import EventEnvelope, TicketPurchasedV1
from pydantic import create_model

CONTRACTS = Path(__file__).resolve().parent
TARGET = CONTRACTS / "events" / "ticket-purchased.v1.schema.json"
ASYNCAPI_TARGET = CONTRACTS / "events" / "ticketing.asyncapi.v1.json"


def render_schema() -> str:
    # Bind the generic envelope to its concrete payload for schema generation.
    # This temporary model is not installed into the publishing service.
    event_model = create_model(
        "TicketPurchasedEventV1",
        __base__=EventEnvelope,
        payload=(TicketPurchasedV1, ...),
    )
    schema = event_model.model_json_schema(by_alias=True, mode="serialization")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["description"] = (
        "TicketPurchased v1 activity event. Deduplicate by eventId; "
        "this is not an entity-state snapshot. Additional fields are tolerated."
    )
    # The envelope is generic; these constants identify this specific contract.
    schema["properties"]["type"]["const"] = TicketPurchasedV1.TYPE
    schema["properties"]["version"]["const"] = TicketPurchasedV1.VERSION
    # Producer identity matches PRODUCER in ticketing purchases/services.py.
    schema["properties"]["producer"]["const"] = "ticketing-service"
    schema["x-routing-key"] = TicketPurchasedV1.ROUTING_KEY
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def render_asyncapi() -> str:
    """Describe the proposed publisher transport; no broker topology is created."""
    example = json.loads((CONTRACTS / "examples/ticket-purchased.v1.json").read_text(encoding="utf-8"))
    document = {
        "asyncapi": "3.0.0",
        "info": {
            "title": "MetroIsJustABus ticketing events",
            "version": "1.0.0",
            "description": (
                "TicketPurchased contract based on existing payload/outbox code and adopted AMQP design. "
                "Broker topology, relay deployment and notification consumer remain unimplemented/unverified. "
                "No broker address or credentials are specified."
            ),
        },
        "defaultContentType": "application/json",
        "channels": {
            "ticketPurchased": {
                "address": TicketPurchasedV1.ROUTING_KEY,
                "messages": {"TicketPurchasedV1": {"$ref": "#/components/messages/TicketPurchasedV1"}},
                "bindings": {
                    "amqp": {
                        "is": "routingKey",
                        "exchange": {"name": "metro.events", "type": "topic", "durable": True, "autoDelete": False},
                        "bindingVersion": "0.3.0",
                    }
                },
            }
        },
        "operations": {
            "publishTicketPurchased": {
                "action": "send",
                "channel": {"$ref": "#/channels/ticketPurchased"},
                "messages": [{"$ref": "#/channels/ticketPurchased/messages/TicketPurchasedV1"}],
                "summary": "Publish committed purchase activity through a future outbox relay",
            }
        },
        "components": {
            "messages": {
                "TicketPurchasedV1": {
                    "name": TicketPurchasedV1.TYPE,
                    "contentType": "application/json",
                    "description": (
                        "Envelope and payload form one JSON message. Deduplicate activity by eventId; "
                        "do not apply entity-state snapshot ordering. Delivery is designed as at least once."
                    ),
                    "correlationId": {"location": "$message.payload#/correlationId"},
                    "payload": {
                        "schemaFormat": "application/schema+json;version=draft-2020-12",
                        "schema": {"$ref": "./ticket-purchased.v1.schema.json"},
                    },
                    "examples": [{"name": "SyntheticPurchase", "payload": example}],
                }
            }
        },
        "x-requirement": "NFR-006",
        "x-status": "Draft for team review; transport and consumers not verified",
    }
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asyncapi", action="store_true", help="generate/check the publisher AsyncAPI description")
    parser.add_argument("--check", action="store_true", help="fail if the committed schema differs; do not write")
    args = parser.parse_args()
    target = ASYNCAPI_TARGET if args.asyncapi else TARGET
    expected = render_asyncapi() if args.asyncapi else render_schema()
    if args.check:
        if not target.is_file() or target.read_text(encoding="utf-8") != expected:
            raise SystemExit(f"Contract missing or stale: {target.relative_to(CONTRACTS)}")
        if args.asyncapi:
            print("Ticketing AsyncAPI matches the event metadata and synthetic example.")
        else:
            print("TicketPurchased v1 schema matches the source models.")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(expected, encoding="utf-8")
    print(f"Generated {target.relative_to(CONTRACTS)}")


if __name__ == "__main__":
    main()
