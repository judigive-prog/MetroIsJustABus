"""Simulated payment behaviour per reserved token (purchase design §5.2, N-11).

`sim_lose_response` (record the approval, then drop the connection) is not implemented:
Django cannot close the socket without answering. It returns 501 and records nothing.
"""

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction

from payments.models import Payment

APPROVING_TOKENS = {"sim_approve", "sim_slow"}


@dataclass(frozen=True)
class SimResponse:
    http_status: int
    body: dict[str, Any]


def fingerprint(amount_cents: int, currency: str, token: str) -> str:
    canonical = json.dumps(
        {"amountCents": amount_cents, "currency": currency, "paymentMethodToken": token},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _body(payment: Payment) -> dict[str, Any]:
    body: dict[str, Any] = {"paymentId": str(payment.id), "status": payment.status}
    if payment.reason:
        body["reason"] = payment.reason
    return body


def process_payment(*, key: uuid.UUID, amount_cents: int, currency: str, token: str) -> SimResponse:
    fp = fingerprint(amount_cents, currency, token)
    try:
        response, slow = _process(key=key, fp=fp, amount_cents=amount_cents, currency=currency, token=token)
    except IntegrityError:
        # A concurrent first call with the same key won; treat this one as a repeat.
        response, slow = _process(key=key, fp=fp, amount_cents=amount_cents, currency=currency, token=token)
    if slow:
        time.sleep(settings.SIM_SLOW_SECONDS)  # longer than the caller's read timeout, on purpose
    return response


def _process(
    *, key: uuid.UUID, fp: str, amount_cents: int, currency: str, token: str
) -> tuple[SimResponse, bool]:
    with transaction.atomic():
        payment = Payment.objects.select_for_update().filter(idempotency_key=key).first()
        if payment is not None:
            if payment.request_fingerprint != fp:
                return SimResponse(409, {"error": {"code": "IDEMPOTENCY_KEY_REUSED"}}), False
            payment.request_count += 1
            if payment.status == Payment.Status.ERRORED:
                payment.status = Payment.Status.APPROVED
                payment.charge_count = 1
            payment.save(update_fields=["request_count", "status", "charge_count", "updated_at"])
            return SimResponse(200, _body(payment)), False

        if token == "sim_lose_response":
            return SimResponse(501, {"error": {"code": "NOT_IMPLEMENTED"}}), False

        if token == "sim_error":
            Payment.objects.create(
                idempotency_key=key,
                request_fingerprint=fp,
                amount_cents=amount_cents,
                currency=currency,
                status=Payment.Status.ERRORED,
            )
            return SimResponse(500, {"error": {"code": "SIMULATED_ERROR"}}), False

        approved = token in APPROVING_TOKENS
        reason = None
        if not approved:
            reason = "DECLINED" if token == "sim_decline" else "INVALID_PAYMENT_METHOD"
        payment = Payment.objects.create(
            idempotency_key=key,
            request_fingerprint=fp,
            amount_cents=amount_cents,
            currency=currency,
            status=Payment.Status.APPROVED if approved else Payment.Status.DECLINED,
            reason=reason,
            charge_count=1 if approved else 0,
        )
        return SimResponse(200, _body(payment)), token == "sim_slow"


def inspect_payment(key: uuid.UUID) -> dict[str, Any] | None:
    """For tests: was exactly one charge made for this key?"""
    payment = Payment.objects.filter(idempotency_key=key).first()
    if payment is None:
        return None
    return {
        "status": payment.status,
        "paymentId": str(payment.id),
        "chargeCount": payment.charge_count,
        "requestCount": payment.request_count,
    }
