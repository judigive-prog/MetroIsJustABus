import uuid

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsPassenger
from common.schema import ErrorResponseSerializer
from inbox import selectors, services
from inbox.api.serializers import (
    InboxListResponseSerializer,
    InboxNotificationResponseSerializer,
    MarkAllReadResponseSerializer,
)


class InboxListView(APIView):
    permission_classes = [IsPassenger]

    @extend_schema(
        summary="Get passenger notification history / inbox (FR-067)",
        parameters=[
            OpenApiParameter(
                name="unread_only",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter to unread notifications only",
            )
        ],
        responses={
            200: InboxListResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
    def get(self, request: Request) -> Response:
        unread_param = request.query_params.get("unread_only", "")
        unread_only = unread_param.lower() in ("true", "1")

        notifications = selectors.list_passenger_notifications(
            passenger_id=request.user.id,
            unread_only=unread_only,
        )
        unread_count = selectors.count_unread_notifications(passenger_id=request.user.id)

        return Response(
            {
                "items": InboxNotificationResponseSerializer(notifications, many=True).data,
                "unreadCount": unread_count,
            }
        )


class InboxMarkReadView(APIView):
    permission_classes = [IsPassenger]

    @extend_schema(
        summary="Mark notification as read (FR-067)",
        responses={
            200: InboxNotificationResponseSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def post(self, request: Request, pk: uuid.UUID) -> Response:
        notif = services.mark_as_read(passenger_id=request.user.id, notification_id=pk)
        return Response(InboxNotificationResponseSerializer(notif).data)

    patch = post


class InboxMarkAllReadView(APIView):
    permission_classes = [IsPassenger]

    @extend_schema(
        summary="Mark all notifications as read (FR-067)",
        responses={
            200: MarkAllReadResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        count = services.mark_all_as_read(passenger_id=request.user.id)
        return Response({"markedCount": count})
