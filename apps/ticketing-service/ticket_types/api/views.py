from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from common.pagination import LimitCursorPagination
from ticket_types import selectors
from ticket_types.api.serializers import TicketTypeResponseSerializer


@extend_schema(summary="List ticket types that can be bought (FR-031)")
class TicketTypeListView(ListAPIView):  # type: ignore[type-arg]  # DRF views are not generic at runtime
    permission_classes = [AllowAny]  # public on purpose (N-01)
    authentication_classes = []
    serializer_class = TicketTypeResponseSerializer
    pagination_class = LimitCursorPagination

    def get_queryset(self):  # type: ignore[no-untyped-def]  # signature fixed by DRF
        return selectors.active_ticket_types()
