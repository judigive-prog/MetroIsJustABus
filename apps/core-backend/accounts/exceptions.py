from common.errors import DomainError


class InvalidPasswordError(DomainError):
    code = "INVALID_PASSWORD"
    http_status = 400
    message = "A non-empty password is required."


class DuplicateAccountError(DomainError):
    code = "ACCOUNT_ALREADY_EXISTS"
    http_status = 409
    message = "An account with this email already exists."
