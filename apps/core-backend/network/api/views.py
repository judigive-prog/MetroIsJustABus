import uuid

from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.pagination import LimitCursorPagination
from common.schema import ErrorResponseSerializer
from network import selectors
from network.api.serializers import (
    LineOrderedStopsResponseSerializer,
    LineResponseSerializer,
    StopResponseSerializer,
)
from network.models import Line, Stop


@extend_schema(summary="List all active lines (FR-001)")
class LineListView(ListAPIView):  # type: ignore[type-arg]  # DRF views are not generic at runtime
    permission_classes = [AllowAny]  # public on purpose: any visitor can list lines (FR-001, FR-024)
    authentication_classes = []
    serializer_class = LineResponseSerializer
    pagination_class = LimitCursorPagination

    def get_queryset(self) -> QuerySet[Line]:
        return selectors.active_lines()


class LineOrderedStopsView(APIView):
    """Public ordered stop sequence per direction for an active line (FR-002)."""

    permission_classes = [AllowAny]  # public on purpose: visitors inspect line stops (FR-002, FR-024)
    authentication_classes = []

    @extend_schema(
        summary="Show ordered stops of a line (FR-002)",
        responses={
            200: LineOrderedStopsResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def get(self, request: Request, line_id: uuid.UUID) -> Response:
        line = selectors.find_active_line(line_id)
        if line is None:
            raise NotFound("Line not found.")
        return Response(selectors.line_ordered_stops_body(line))


@extend_schema(summary="List all active stops (FR-001)")
class StopListView(ListAPIView):  # type: ignore[type-arg]  # DRF views are not generic at runtime
    permission_classes = [AllowAny]  # public on purpose: any visitor can list stops (FR-001, FR-024)
    authentication_classes = []
    serializer_class = StopResponseSerializer
    pagination_class = LimitCursorPagination

    def get_queryset(self) -> QuerySet[Stop]:
        return selectors.active_stops()
