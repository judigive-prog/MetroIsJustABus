"""Check the existing ticketing client against payment-sim in separate processes.

Only the provider's payment business operation is stubbed. HTTP serialization,
routing, authentication, request validation and client response parsing are real.
No socket, database or real payment is used. This is not a deployment test.
"""

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import UUID

from generate_openapi import ROOT, configure_schema_generation

CONTRACTS = Path(__file__).resolve().parent
SYNTHETIC_TOKEN = "met-88-synthetic-token-not-a-credential"


def provider() -> None:
    """Exercise the real provider HTTP boundary in its own Python environment."""
    configure_schema_generation("payment-sim")
    from unittest.mock import patch

    from django.test import override_settings
    from django.urls import resolve
    from rest_framework.test import APIRequestFactory

    from payments.services import SimResponse

    data = json.load(sys.stdin)
    request = data["request"]
    response = data["response"]
    headers = {"HTTP_" + key.upper().replace("-", "_"): value for key, value in request["headers"].items()}
    with override_settings(SERVICE_TOKEN=SYNTHETIC_TOKEN):
        with patch(
            "payments.services.process_payment", return_value=SimResponse(response["status"], response["body"])
        ) as pay:
            incoming = APIRequestFactory().generic(
                request["method"],
                request["path"],
                data=json.dumps(request["body"]),
                content_type="application/json",
                **headers,
            )
            match = resolve(request["path"])
            outgoing = match.func(incoming, *match.args, **match.kwargs)
            outgoing.render()
            pay.assert_called_once_with(
                key=UUID(request["headers"]["Idempotency-Key"]),
                amount_cents=request["body"]["amountCents"],
                currency=request["body"]["currency"],
                token=request["body"]["paymentMethodToken"],
            )
    print(json.dumps({"status": outgoing.status_code, "body": json.loads(outgoing.content)}))


def check() -> None:
    configure_schema_generation("ticketing")
    import httpx
    from jsonschema import Draft4Validator, FormatChecker, ValidationError
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT4

    from common.http import ServiceHttpClient
    from purchases.clients import HttpPaymentClient

    fixture = json.loads((CONTRACTS / "examples/payment.v1.json").read_text(encoding="utf-8"))
    document = json.loads((CONTRACTS / fixture["contract"]).read_text(encoding="utf-8"))
    if document["info"]["version"] != fixture["contractVersion"]:
        raise SystemExit("Example contract version does not match the provider contract.")
    # The tested request/response schemas use the Draft 4-compatible OpenAPI 3.0
    # subset (no nullable/readOnly/writeOnly semantics). This is not a general
    # OpenAPI instance validator for every schema in the repository.
    uri = "urn:metro:payment-openapi-v1"
    registry = Registry().with_resource(uri, Resource.from_contents(document, default_specification=DRAFT4))
    root_validator = Draft4Validator({"$ref": uri}, registry=registry, format_checker=FormatChecker())
    provider_python = (
        ROOT / "simulators/payment-sim/.venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    )
    if not provider_python.is_file():
        raise SystemExit("Prepare payment-sim first: uv sync --project simulators/payment-sim --python 3.13")

    # Any: HTTP bodies, schemas and fixtures are heterogeneous JSON; validate
    # their structure before passing them across the component boundary.
    def validate(schema: dict[str, Any], value: Any) -> None:
        # Enter the document first so local component references resolve there.
        validator = root_validator.evolve(schema={"$ref": uri})
        ref = schema.get("$ref")
        if ref is not None:
            validator = root_validator.evolve(schema={"$ref": uri + ref})
        else:
            validator = root_validator.evolve(schema=schema)
        validator.validate(value)

    operation = document["paths"][fixture["request"]["path"]]["post"]
    body_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    for label, decision, extra in (
        ("approval", "APPROVED", False),
        ("decline", "DECLINED", False),
        ("additive response field", "APPROVED", True),
    ):
        expected = deepcopy(fixture)
        expected["response"]["body"]["status"] = decision
        if decision == "DECLINED":
            expected["response"]["body"]["reason"] = "DECLINED"
            expected["request"]["body"]["paymentMethodToken"] = "sim_decline"
        if extra:
            expected["response"]["body"]["futureProviderField"] = True

        def exchange(request: httpx.Request) -> httpx.Response:
            assert request.method == expected["request"]["method"]
            assert request.url.path == expected["request"]["path"]
            assert request.headers["Content-Type"].startswith("application/json")
            assert request.headers["Authorization"] == f"Bearer {SYNTHETIC_TOKEN}"
            assert operation["security"] == [{"serviceBearer": []}]
            for parameter in operation.get("parameters", []):
                if parameter["in"] == "header":
                    validate(parameter["schema"], request.headers[parameter["name"]])
            body = json.loads(request.content)
            validate(body_schema, body)
            assert body == expected["request"]["body"]
            assert request.headers["Idempotency-Key"] == expected["request"]["headers"]["Idempotency-Key"]
            transported = {
                "request": {
                    "method": request.method,
                    "path": request.url.path,
                    "headers": {
                        "Authorization": request.headers["Authorization"],
                        "Idempotency-Key": request.headers["Idempotency-Key"],
                    },
                    "body": body,
                },
                "response": expected["response"],
            }
            completed = subprocess.run(
                [str(provider_python), str(Path(__file__).resolve()), "--provider"],
                input=json.dumps(transported),
                text=True,
                capture_output=True,
                check=True,
                timeout=30,
            )
            received = json.loads(completed.stdout)
            assert received["status"] == expected["response"]["status"]
            response_schema = operation["responses"][str(received["status"])]["content"]["application/json"]["schema"]
            validate(response_schema, received["body"])
            return httpx.Response(received["status"], json=received["body"])

        client = HttpPaymentClient(
            ServiceHttpClient("https://payment-sim.invalid", SYNTHETIC_TOKEN, transport=httpx.MockTransport(exchange))
        )
        result = client.pay(
            idempotency_key=UUID(expected["request"]["headers"]["Idempotency-Key"]),
            amount_cents=expected["request"]["body"]["amountCents"],
            currency=expected["request"]["body"]["currency"],
            payment_method_token=expected["request"]["body"]["paymentMethodToken"],
        )
        assert result.outcome.value == decision
        if decision == "APPROVED":
            assert result.payment_id == expected["response"]["body"]["paymentId"]
        else:
            assert result.reason == "DECLINED"
        print(f"PASS: real ticketing client and isolated payment-sim view — {label}")

    broken = deepcopy(fixture["request"]["body"])
    del broken["currency"]
    try:
        validate(body_schema, broken)
    except ValidationError:
        print("PASS: provider contract rejects a request missing currency")
    else:
        raise SystemExit("FAIL: missing required currency was accepted")
    print("Passed 4 HTTP contract cases against payment-sim contract 1.0.0.")
    print("Provider payment operation was stubbed; no network, database or released-version compatibility was tested.")


if __name__ == "__main__":
    if sys.argv[1:] == ["--provider"]:
        provider()
    elif not sys.argv[1:]:
        check()
    else:
        raise SystemExit("Usage: check_payment_contract.py [--provider]")
