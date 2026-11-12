from common.errors import DomainError


class NotificationNotFound(DomainError):
    code = "NOTIFICATION_NOT_FOUND"
    http_status = 404
    message = "This notification was not found."
