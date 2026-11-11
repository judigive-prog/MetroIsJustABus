"""Generate service OpenAPI without runtime secrets or a database (NFR-006).

Only literal schema-relevant settings are read from the service settings file.
The module is never executed, so config.env and its secret files are not loaded.
Dynamic settings require an explicit update to this tool, not a silent fallback.
"""

import argparse
import ast
import json
import sys
from io import StringIO
from pathlib import Path
from typing import Any

CONTRACTS = Path(__file__).resolve().parent
ROOT = CONTRACTS.parent
SERVICES = {
    "ticketing": ROOT / "apps/ticketing-service",
    "payment-sim": ROOT / "simulators/payment-sim",
}
SCHEMA_SETTINGS = {
    "INSTALLED_APPS",
    "ROOT_URLCONF",
    "REST_FRAMEWORK",
    "SPECTACULAR_SETTINGS",
    "USE_TZ",
    "TIME_ZONE",
    "USE_I18N",
    "DEFAULT_AUTO_FIELD",
}


def configure_schema_generation(service_name: str = "ticketing") -> None:
    import django
    from django.conf import settings

    # Any: Django setting values include heterogeneous dicts, lists and scalars.
    values: dict[str, Any] = {}
    service = SERVICES[service_name]
    source = ast.parse((service / "config/settings.py").read_text(encoding="utf-8"))
    for statement in source.body:
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name) and target.id in SCHEMA_SETTINGS:
                    values[target.id] = ast.literal_eval(statement.value)
    missing = SCHEMA_SETTINGS - values.keys()
    if missing:
        raise SystemExit(f"Schema settings must be explicitly available: {sorted(missing)}")
    sys.path.insert(0, str(service))
    settings.configure(
        **values,
        SECRET_KEY="schema-generation-only-not-a-runtime-secret",
        DATABASES={"default": {"ENGINE": "django.db.backends.dummy"}},
    )
    django.setup()


def render_schema(service_name: str = "ticketing") -> str:
    configure_schema_generation(service_name)
    from django.core.management import call_command

    output = StringIO()
    call_command(
        "spectacular",
        format="openapi-json",
        validate=True,
        fail_on_warn=True,
        stdout=output,
    )
    return json.dumps(json.loads(output.getvalue()), indent=2, sort_keys=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service", choices=SERVICES, default="ticketing", help="service to describe")
    parser.add_argument("--check", action="store_true", help="compare generated content without writing")
    args = parser.parse_args()
    target = CONTRACTS / f"openapi/{args.service}.v1.json"
    expected = render_schema(args.service)
    if args.check:
        if not target.is_file() or target.read_text(encoding="utf-8") != expected:
            raise SystemExit(f"{args.service} OpenAPI contract is missing or stale.")
        print(f"{args.service} OpenAPI matches the source routes and annotations.")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(expected, encoding="utf-8")
    print(f"Generated {target.relative_to(CONTRACTS)}; OpenAPI validation passed.")


if __name__ == "__main__":
    main()
