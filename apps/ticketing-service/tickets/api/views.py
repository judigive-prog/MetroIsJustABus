import uuid

from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.pagination import LimitCursorPagination
from common.permissions import IsPassenger
from common.schema import ErrorResponseSerializer
from tickets import selectors
from tickets.api.serializers import TicketResponseSerializer
from tickets.exceptions import TicketNotFound


class TicketPagination(LimitCursorPagination):
    ordering = ("-created_at", "-id")


@extend_schema(
    summary="List passenger tickets (FR-034)",
    responses={
        200: TicketResponseSerializer(many=True),
        401: ErrorResponseSerializer,
        403: ErrorResponseSerializer,
    },
)
class TicketListView(ListAPIView):  # type: ignore[type-arg]  # DRF views are not generic at runtime
    permission_classes = [IsPassenger]
    serializer_class = TicketResponseSerializer
    pagination_class = TicketPagination

    def get_queryset(self):  # type: ignore[no-untyped-def]  # signature fixed by DRF
        return selectors.list_passenger_tickets(self.request.user.id)


class TicketDetailView(APIView):
    permission_classes = [IsPassenger]

    @extend_schema(
        summary="Retrieve passenger ticket and validation history (FR-034)",
        responses={
            200: TicketResponseSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def get(self, request: Request, ticket_id: uuid.UUID) -> Response:
        ticket = selectors.get_passenger_ticket(ticket_id, request.user.id)
        if ticket is None:
            raise TicketNotFound()
        serializer = TicketResponseSerializer(ticket)
        return Response(serializer.data)
