from django.db import DatabaseError, connection
from django.http import HttpRequest, JsonResponse


def live(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


def ready(request: HttpRequest) -> JsonResponse:
    """Ready only when the database answers (conventions.md, Containers)."""
    try:
        connection.ensure_connection()
    except DatabaseError:
        return JsonResponse({"status": "unavailable", "dependency": "database"}, status=503)
    return JsonResponse({"status": "ok"})
