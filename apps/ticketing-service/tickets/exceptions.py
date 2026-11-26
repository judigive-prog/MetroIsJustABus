from common.errors import DomainError


class TicketNotFound(DomainError):
    code = "TICKET_NOT_FOUND"
    http_status = 404
    message = "This ticket was not found."
