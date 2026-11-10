from common.errors import DomainError


class InvalidChannel(DomainError):
    code = "INVALID_CHANNEL"
    http_status = 400
    message = "Notification channel must be IN_APP or EMAIL (ADR A-06)."


class InvalidChangeType(DomainError):
    code = "INVALID_CHANGE_TYPE"
    http_status = 400
    message = "Change type must be one of DISRUPTION, DELAY, SCHEDULE_CHANGE."
