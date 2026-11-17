import uuid

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, PolymorphicProxySerializer, extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from payments import services
from payments.api.schema import (
    FrameworkErrorSerializer,
    PaymentErrorSerializer,
    PaymentInspectionSerializer,
    PaymentResponseSerializer,
)


class PaymentRequestSerializer(serializers.Serializer):  # type: ignore[type-arg]  # DRF serializers are not generic at runtime
    amountCents = serializers.IntegerField(min_value=0)
    currency = serializers.RegexField(regex=r"^[A-Z]{3}$")
    paymentMethodToken = serializers.CharField(max_length=64)


class PaymentCreateView(APIView):
    @extend_schema(
        summary="Create or replay a simulated payment",
        description="Existing simulator behaviour only; no real payment is processed.",
        parameters=[OpenApiParameter("Idempotency-Key", OpenApiTypes.UUID, OpenApiParameter.HEADER, required=True)],
        request=PaymentRequestSerializer,
        responses={
            200: PaymentResponseSerializer,
            400: PolymorphicProxySerializer(
                component_name="PaymentBadRequest",
                serializers=[PaymentErrorSerializer, FrameworkErrorSerializer],
                resource_type_field_name=None,
            ),
            401: FrameworkErrorSerializer,
            403: FrameworkErrorSerializer,
            405: FrameworkErrorSerializer,
            409: PaymentErrorSerializer,
            415: FrameworkErrorSerializer,
            500: PaymentErrorSerializer,
            501: PaymentErrorSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        try:
            key = uuid.UUID(request.headers.get("Idempotency-Key", ""))
        except ValueError:
            return Response({"error": {"code": "IDEMPOTENCY_KEY_REQUIRED"}}, status=400)
        serializer = PaymentRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": {"code": "VALIDATION_ERROR"}}, status=400)
        data = serializer.validated_data
        result = services.process_payment(
            key=key, amount_cents=data["amountCents"], currency=data["currency"], token=data["paymentMethodToken"]
        )
        return Response(result.body, status=result.http_status)


class PaymentDetailView(APIView):
    @extend_schema(
        summary="Inspect a simulated payment by its idempotency key",
        responses={
            200: PaymentInspectionSerializer,
            401: FrameworkErrorSerializer,
            403: FrameworkErrorSerializer,
            404: PaymentErrorSerializer,
            405: FrameworkErrorSerializer,
        },
    )
    def get(self, request: Request, key: uuid.UUID) -> Response:
        body = services.inspect_payment(key)
        if body is None:
            return Response({"error": {"code": "NOT_FOUND"}}, status=404)
        return Response(body)
