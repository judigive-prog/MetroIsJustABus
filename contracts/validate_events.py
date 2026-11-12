"""Validate the TicketPurchased example and meaningful rejection cases (NFR-006).

This is local schema validation, not evidence of an implemented notification
consumer, broker transport, business-rule correctness or release compatibility.
"""

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

CONTRACTS = Path(__file__).resolve().parent


def main() -> None:
    schema = json.loads((CONTRACTS / "events/ticket-purchased.v1.schema.json").read_text(encoding="utf-8"))
    # Any: examples are arbitrary JSON; JSON Schema validates their structure.
    example: dict[str, Any] = json.loads((CONTRACTS / "examples/ticket-purchased.v1.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    # Format validation is explicit: type=string alone does not verify UUID/time.
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    validator.validate(example)
    print("PASS: complete synthetic TicketPurchased v1 example")

    additive = deepcopy(example)
    additive["futureMetadata"] = "synthetic additive field"
    additive["payload"]["futureField"] = True
    validator.validate(additive)
    print("PASS: unknown additive envelope and payload fields remain accepted")

    invalid = deepcopy(example)
    del invalid["payload"]["ticketId"]
    cases = [("missing required payload.ticketId", invalid)]
    for field, value in (("version", 2), ("type", "TicketValidated"), ("producer", "another-service")):
        invalid = deepcopy(example)
        invalid[field] = value
        cases.append((f"unsupported {field}", invalid))
    for path, value in (
        (("payload", "priceCents"), "250"),
        (("payload", "passengerId"), "not-a-uuid"),
        (("occurredAt",), "not-a-timestamp"),
    ):
        invalid = deepcopy(example)
        target = invalid
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = value
        cases.append((f"invalid {'.'.join(path)}", invalid))

    for label, invalid in cases:
        errors = list(validator.iter_errors(invalid))
        if not errors:
            raise SystemExit(f"FAIL: schema unexpectedly accepted {label}")
        print(f"PASS: rejected {label}")
    print(f"Passed {2 + len(cases)} event contract cases; no services or databases were used.")


def validate_stdin() -> None:
    """Schema-only receiver probe; imports no producer or notification code."""
    schema = json.loads((CONTRACTS / "events/ticket-purchased.v1.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    message = json.load(sys.stdin)
    errors = list(validator.iter_errors(message))
    if errors:
        print(json.dumps({"valid": False, "violatedKeywords": sorted({error.validator for error in errors})}))
        raise SystemExit(2)
    print(
        json.dumps(
            {"valid": True, "eventId": message["eventId"], "type": message["type"], "version": message["version"]}
        )
    )


if __name__ == "__main__":
    if sys.argv[1:] == ["--stdin"]:
        validate_stdin()
    elif not sys.argv[1:]:
        main()
    else:
        raise SystemExit("Usage: validate_events.py [--stdin]")
