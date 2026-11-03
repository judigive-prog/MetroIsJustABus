from common.errors import DomainError


class IdempotencyKeyRequired(DomainError):
    code = "IDEMPOTENCY_KEY_REQUIRED"
    http_status = 400
    message = "The request needs an Idempotency-Key header containing a UUID."


class IdempotencyKeyReused(DomainError):
    code = "IDEMPOTENCY_KEY_REUSED"
    http_status = 409
    message = "This request key was already used for a different purchase."


class TicketTypeNotFound(DomainError):
    code = "TICKET_TYPE_NOT_FOUND"
    http_status = 404
    message = "This ticket type does not exist."


class TicketTypeNotAvailable(DomainError):
    code = "TICKET_TYPE_NOT_AVAILABLE"
    http_status = 422
    message = "This ticket type can no longer be bought."


class PriceChanged(DomainError):
    code = "PRICE_CHANGED"
    http_status = 422
    message = "The price of this ticket has changed. Please check it and try again."


class PurchaseNotFound(DomainError):
    code = "PURCHASE_NOT_FOUND"
    http_status = 404
    message = "This purchase was not found."


PAYMENT_DECLINED_CODE = "PAYMENT_DECLINED"
PAYMENT_DECLINED_MESSAGE = "The payment was declined. No ticket was issued."
