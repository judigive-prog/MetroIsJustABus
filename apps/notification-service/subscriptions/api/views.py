import uuid

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsPassenger
from common.schema import ErrorResponseSerializer
from subscriptions import selectors, services
from subscriptions.api.serializers import (
    SubscriptionCreateRequestSerializer,
    SubscriptionListResponseSerializer,
    SubscriptionResponseSerializer,
    SubscriptionUpdateRequestSerializer,
)


class SubscriptionsView(APIView):
    permission_classes = [IsPassenger]

    @extend_schema(
        summary="Subscribe to a line, stop, or scheduled trip (FR-060)",
        request=SubscriptionCreateRequestSerializer,
        responses={
            201: SubscriptionResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            409: ErrorResponseSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        serializer = SubscriptionCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        subscription = services.create_subscription(
            passenger_id=request.user.id,
            entity_type=serializer.validated_data["entityType"],
            entity_id=serializer.validated_data["entityId"],
        )
        return Response(SubscriptionResponseSerializer(subscription).data, status=201)

    @extend_schema(
        summary="List passenger subscriptions (FR-061)",
        parameters=[
            OpenApiParameter(
                name="active",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by active status (true/false)",
            )
        ],
        responses={
            200: SubscriptionListResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
    def get(self, request: Request) -> Response:
        active_param = request.query_params.get("active")
        active_filter: bool | None = None
        if active_param is not None:
            active_filter = active_param.lower() in ("true", "1")
        subscriptions = selectors.list_subscriptions(passenger_id=request.user.id, active=active_filter)
        return Response({"items": SubscriptionResponseSerializer(subscriptions, many=True).data})


class SubscriptionDetailView(APIView):
    permission_classes = [IsPassenger]

    @extend_schema(
        summary="Update subscription status (FR-061)",
        request=SubscriptionUpdateRequestSerializer,
        responses={
            200: SubscriptionResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def patch(self, request: Request, pk: uuid.UUID) -> Response:
        serializer = SubscriptionUpdateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        subscription = services.update_subscription_status(
            subscription_id=pk,
            passenger_id=request.user.id,
            active=serializer.validated_data["active"],
        )
        return Response(SubscriptionResponseSerializer(subscription).data)

    @extend_schema(
        summary="Cancel a subscription (FR-061)",
        responses={
            204: None,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def delete(self, request: Request, pk: uuid.UUID) -> Response:
        services.cancel_subscription(subscription_id=pk, passenger_id=request.user.id)
        return Response(status=204)
