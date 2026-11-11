"""Validate AsyncAPI structure, references and event consistency (NFR-006).

Downloads only a pinned official validation schema over HTTPS. No broker,
service credentials, database or application endpoint is contacted.
"""

import hashlib
import json
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from generate_events import render_asyncapi, render_schema
from jsonschema import Draft7Validator, Draft202012Validator, FormatChecker
from metro_common.events import TicketPurchasedV1
from referencing import Registry, Resource

CONTRACTS = Path(__file__).resolve().parent
OFFICIAL_SCHEMA_URL = (
    "https://raw.githubusercontent.com/asyncapi/spec-json-schemas/"
    "eee8d2217d23b22c475090c0e12f20801f531f11/schemas/3.0.0.json"
)
OFFICIAL_SCHEMA_SHA256 = "1786a007ac00344a8f529e5a6fc5db786b0be6757e0b94a8b95a8a6a52b7fe9a"


def main() -> None:
    description_path = CONTRACTS / "events/ticketing.asyncapi.v1.json"
    description = description_path.read_text(encoding="utf-8")
    if description != render_asyncapi():
        raise SystemExit("AsyncAPI is stale; regenerate it with generate_events.py --asyncapi.")
    document = json.loads(description)
    try:
        with urlopen(OFFICIAL_SCHEMA_URL, timeout=20) as response:
            official_bytes = response.read()
    except (URLError, TimeoutError) as exc:
        raise SystemExit(f"Cannot download the pinned official AsyncAPI validation schema: {exc}") from exc
    if hashlib.sha256(official_bytes).hexdigest() != OFFICIAL_SCHEMA_SHA256:
        raise SystemExit("Official validation schema checksum mismatch; validation was not performed.")
    official = json.loads(official_bytes)
    registry = Registry().with_resource(official["$id"], Resource.from_contents(official)).crawl()
    Draft7Validator(official, registry=registry, format_checker=FormatChecker()).validate(document)
    print("PASS: AsyncAPI 3.0.0 structure against pinned official schema (SHA-256 verified)")

    # Resolve all local AsyncAPI JSON pointers. External payload schema refs
    # belong to a different document and are checked separately below.
    pending = [document]
    count = 0
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            ref = item.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/"):
                target = document
                for part in ref[2:].split("/"):
                    target = target[part.replace("~1", "/").replace("~0", "~")]
                count += 1
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    print(f"PASS: {count} internal AsyncAPI references resolve")

    channel = document["channels"]["ticketPurchased"]
    assert channel["address"] == TicketPurchasedV1.ROUTING_KEY
    assert document["operations"]["publishTicketPurchased"]["action"] == "send"
    assert channel["bindings"]["amqp"] == {
        "is": "routingKey",
        "exchange": {"name": "metro.events", "type": "topic", "durable": True, "autoDelete": False},
        "bindingVersion": "0.3.0",
    }
    message = document["components"]["messages"]["TicketPurchasedV1"]
    assert message["name"] == TicketPurchasedV1.TYPE
    assert message["payload"]["schemaFormat"] == "application/schema+json;version=draft-2020-12"
    assert message["payload"]["schema"]["$ref"] == "./ticket-purchased.v1.schema.json"
    schema_path = description_path.parent / message["payload"]["schema"]["$ref"]
    if schema_path.read_text(encoding="utf-8") != render_schema():
        raise SystemExit("Referenced event JSON Schema is stale; regenerate it first.")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert schema["properties"]["version"]["const"] == TicketPurchasedV1.VERSION
    print("PASS: routing key, publisher operation, AMQP design binding and event schema are consistent")

    example = json.loads((CONTRACTS / "examples/ticket-purchased.v1.json").read_text(encoding="utf-8"))
    assert message["examples"][0]["payload"] == example
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(example)
    assert message["correlationId"]["location"] == "$message.payload#/correlationId"
    assert isinstance(example["correlationId"], str)
    print("PASS: embedded example matches the standalone example, event schema and correlation location")
    print("AsyncAPI checks passed; broker topology and independent event consumers remain unverified.")


if __name__ == "__main__":
    main()
