"""Client for payment-sim (task T-07). Maps every response to exactly one of three outcomes (N-06)."""

import uuid
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from typing import Protocol

import httpx
import structlog
from django.conf import settings

from common.http import ServiceHttpClient

logger = structlog.get_logger(__name__)

# Route proposed in the purchase design (§5.2). Still open: OQ-03.
PAYMENTS_PATH = "/api/payment-sim/v1/payments"


class PaymentOutcome(StrEnum):
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    UNCERTAIN = "UNCERTAIN"


@dataclass(frozen=True)
class PaymentResult:
    outcome: PaymentOutcome
    payment_id: str | None = None
    reason: str | None = None


class PaymentClient(Protocol):
    def pay(
        self, *, idempotency_key: uuid.UUID, amount_cents: int, currency: str, payment_method_token: str
    ) -> PaymentResult: ...


class HttpPaymentClient:
    def __init__(self, http: ServiceHttpClient) -> None:
        self._http = http

    def pay(
        self, *, idempotency_key: uuid.UUID, amount_cents: int, currency: str, payment_method_token: str
    ) -> PaymentResult:
        try:
            response = self._http.post_json(
                PAYMENTS_PATH,
                json={"amountCents": amount_cents, "currency": currency, "paymentMethodToken": payment_method_token},
                headers={"Idempotency-Key": str(idempotency_key)},
            )
        except httpx.HTTPError as exc:
            # Timeout or lost connection: the payment may or may not have happened.
            logger.warning("payment_outcome_uncertain", purchase_id=str(idempotency_key), cause=type(exc).__name__)
            return PaymentResult(PaymentOutcome.UNCERTAIN)

        if response.status_code != 200:
            event = "payment_idempotency_conflict" if response.status_code == 409 else "payment_outcome_uncertain"
            logger.warning(event, purchase_id=str(idempotency_key), http_status=response.status_code)
            return PaymentResult(PaymentOutcome.UNCERTAIN)

        try:
            data = response.json()
            status = data["status"]
            payment_id = data.get("paymentId")
            reason = data.get("reason")
        except (ValueError, KeyError, TypeError, AttributeError):
            logger.warning("payment_outcome_uncertain", purchase_id=str(idempotency_key), cause="malformed_body")
            return PaymentResult(PaymentOutcome.UNCERTAIN)

        if status == "APPROVED" and isinstance(payment_id, str) and payment_id:
            return PaymentResult(PaymentOutcome.APPROVED, payment_id=payment_id)
        if status == "DECLINED":
            return PaymentResult(PaymentOutcome.DECLINED, reason=reason if isinstance(reason, str) else None)
        logger.warning("payment_outcome_uncertain", purchase_id=str(idempotency_key), cause="unexpected_status")
        return PaymentResult(PaymentOutcome.UNCERTAIN)


@cache
def get_payment_client() -> PaymentClient:
    return HttpPaymentClient(ServiceHttpClient(settings.PAYMENT_SIM_URL, settings.PAYMENT_SIM_TOKEN))
