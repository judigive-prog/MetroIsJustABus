import uuid

from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from payments import services


class PaymentRequestSerializer(serializers.Serializer):  # type: ignore[type-arg]  # DRF serializers are not generic at runtime
    amountCents = serializers.IntegerField(min_value=0)
    currency = serializers.RegexField(regex=r"^[A-Z]{3}$")
    paymentMethodToken = serializers.CharField(max_length=64)


class PaymentCreateView(APIView):
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
    def get(self, request: Request, key: uuid.UUID) -> Response:
        body = services.inspect_payment(key)
        if body is None:
            return Response({"error": {"code": "NOT_FOUND"}}, status=404)
        return Response(body)
