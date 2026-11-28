from common.errors import DomainError


class InvalidPasswordError(DomainError):
    code = "INVALID_PASSWORD"
    http_status = 400
    message = "A non-empty password is required."


class InvalidAccountDataError(DomainError):
    code = "INVALID_ACCOUNT_DATA"
    http_status = 400
    message = "Valid email and non-empty full name are required."


class InvalidCredentialsError(DomainError):
    code = "INVALID_CREDENTIALS"
    http_status = 401
    message = "Invalid email or password."


class DuplicateAccountError(DomainError):
    code = "ACCOUNT_ALREADY_EXISTS"
    http_status = 409
    message = "An account with this email already exists."
