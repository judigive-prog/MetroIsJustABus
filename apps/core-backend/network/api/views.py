from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from common.pagination import LimitCursorPagination
from network import selectors
from network.api.serializers import LineResponseSerializer, StopResponseSerializer
from network.models import Line, Stop


@extend_schema(summary="List all active lines (FR-001)")
class LineListView(ListAPIView):  # type: ignore[type-arg]  # DRF views are not generic at runtime
    permission_classes = [AllowAny]  # public on purpose: any visitor can list lines (FR-001, FR-024)
    authentication_classes = []
    serializer_class = LineResponseSerializer
    pagination_class = LimitCursorPagination

    def get_queryset(self) -> QuerySet[Line]:
        return selectors.active_lines()


@extend_schema(summary="List all active stops (FR-001)")
class StopListView(ListAPIView):  # type: ignore[type-arg]  # DRF views are not generic at runtime
    permission_classes = [AllowAny]  # public on purpose: any visitor can list stops (FR-001, FR-024)
    authentication_classes = []
    serializer_class = StopResponseSerializer
    pagination_class = LimitCursorPagination

    def get_queryset(self) -> QuerySet[Stop]:
        return selectors.active_stops()
