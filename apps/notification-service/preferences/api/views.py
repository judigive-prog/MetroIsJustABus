from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsPassenger
from common.schema import ErrorResponseSerializer
from preferences import selectors, services
from preferences.api.serializers import (
    PreferenceItemSerializer,
    PreferencesBulkUpdateRequestSerializer,
    PreferencesResponseSerializer,
    PreferenceUpdateRequestSerializer,
)


class PreferencesView(APIView):
    permission_classes = [IsPassenger]

    @extend_schema(
        summary="Get passenger notification preferences (FR-062, A-06)",
        responses={
            200: PreferencesResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
    def get(self, request: Request) -> Response:
        prefs = selectors.get_preferences_for_passenger(passenger_id=request.user.id)
        return Response({"preferences": PreferenceItemSerializer(prefs, many=True).data})

    @extend_schema(
        summary="Set bulk notification preferences (FR-062, A-06)",
        request=PreferencesBulkUpdateRequestSerializer,
        responses={
            200: PreferencesResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
    def put(self, request: Request) -> Response:
        serializer = PreferencesBulkUpdateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        prefs = services.set_bulk_preferences(
            passenger_id=request.user.id,
            items=serializer.validated_data["preferences"],
        )
        return Response({"preferences": PreferenceItemSerializer(prefs, many=True).data})


class PreferenceDetailView(APIView):
    permission_classes = [IsPassenger]

    @extend_schema(
        summary="Set single channel preference (FR-062, A-06)",
        request=PreferenceUpdateRequestSerializer,
        responses={
            200: PreferenceItemSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
    def put(self, request: Request, channel: str) -> Response:
        serializer = PreferenceUpdateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        pref = services.set_preference(
            passenger_id=request.user.id,
            channel=channel.upper(),
            enabled=serializer.validated_data["enabled"],
            enabled_change_types=serializer.validated_data["enabledChangeTypes"],
        )
        return Response(PreferenceItemSerializer(pref).data)

    patch = put
