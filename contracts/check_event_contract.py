"""Validate a real producer message with an isolated schema-only receiver probe.

No notification application or broker is implemented by this contract test.
"""

import json
import subprocess
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from generate_openapi import ROOT, configure_schema_generation

CONTRACTS = Path(__file__).resolve().parent


def main() -> None:
    configure_schema_generation("ticketing")
    from purchases.models import Purchase
    from purchases.services import _ticket_purchased_envelope
    from tickets.models import Ticket

    seed = json.loads((CONTRACTS / "examples/ticket-purchased.v1.json").read_text(encoding="utf-8"))
    payload = seed["payload"]
    purchase = Purchase(
        id=UUID(payload["purchaseId"]),
        passenger_id=UUID(payload["passengerId"]),
        ticket_type_id=UUID(payload["ticketTypeId"]),
        price_cents=payload["priceCents"],
        currency=payload["currency"],
        correlation_id=seed["correlationId"],
    )
    ticket = Ticket(id=UUID(payload["ticketId"]))
    # Unsaved model instances: only the existing message builder executes.
    envelope = _ticket_purchased_envelope(purchase, ticket, issued_at=datetime.fromisoformat(payload["issuedAt"]))
    emitted = envelope.model_dump(mode="json", by_alias=True)
    assert emitted["payload"] == payload
    receiver_python = (
        ROOT / "packages/metro_common/.venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    )
    if not receiver_python.is_file():
        raise SystemExit("Prepare metro_common and its contracts dependency group first.")

    # Any: the transmitted event is heterogeneous JSON validated in the other process.
    def receive(message: dict[str, Any]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(receiver_python), str(CONTRACTS / "validate_events.py"), "--stdin"],
            input=json.dumps(message),
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )

    accepted = receive(emitted)
    assert accepted.returncode == 0, accepted.stderr or accepted.stdout
    receipt = json.loads(accepted.stdout)
    assert receipt == {"valid": True, "eventId": emitted["eventId"], "type": "TicketPurchased", "version": 1}
    print("PASS: existing ticketing producer message accepted by isolated schema-only receiver probe")
    print("Exchanged synthetic event: " + json.dumps(emitted, sort_keys=True))

    additive = deepcopy(emitted)
    additive["payload"]["futureField"] = True
    accepted = receive(additive)
    assert accepted.returncode == 0, accepted.stderr or accepted.stdout
    print("PASS: receiver probe tolerates an additive payload field")

    unsupported = deepcopy(emitted)
    unsupported["version"] = 2
    rejected = receive(unsupported)
    assert rejected.returncode == 2, rejected.stderr or rejected.stdout
    rejection = json.loads(rejected.stdout)
    assert rejection["valid"] is False and "const" in rejection["violatedKeywords"]
    print("PASS: receiver probe rejects unsupported event version 2")
    print("Passed 3 producer/receiver contract cases for TicketPurchased v1 (JSON Schema Draft 2020-12).")
    print("Receiver is a schema-only probe, not notification-service. No database, broker or released-version check.")


if __name__ == "__main__":
    main()
