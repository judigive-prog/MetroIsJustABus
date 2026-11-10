from rest_framework.pagination import CursorPagination


class LimitCursorPagination(CursorPagination):
    """`limit` and `cursor` (default 50, max 200), conventions.md API."""

    page_size = 50
    max_page_size = 200
    page_size_query_param = "limit"
    ordering = ("created_at", "id")
