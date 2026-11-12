from common.errors import DomainError


class SubscriptionAlreadyExists(DomainError):
    code = "SUBSCRIPTION_ALREADY_EXISTS"
    http_status = 409
    message = "You already have an active subscription for this entity."


class SubscriptionNotFound(DomainError):
    code = "SUBSCRIPTION_NOT_FOUND"
    http_status = 404
    message = "This subscription was not found."


class InvalidEntityType(DomainError):
    code = "INVALID_ENTITY_TYPE"
    http_status = 400
    message = "Entity type must be one of LINE, STOP, TRIP."
