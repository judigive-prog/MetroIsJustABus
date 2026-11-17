"""Schema-only descriptions of existing payment responses and authentication."""

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.openapi import AutoSchema
from rest_framework import serializers


class ServiceTokenSchema(OpenApiAuthenticationExtension):
    target_class = "payments.api.auth.ServiceTokenAuthentication"
    name = "serviceBearer"

    def get_security_definition(self, auto_schema: AutoSchema) -> dict[str, str]:
        return {
            "type": "http",
            "scheme": "bearer",
            "description": "Existing shared service token; not a passenger JWT. Credential issuance remains pending.",
        }


class PaymentResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]  # DRF is not generic at runtime
    paymentId = serializers.UUIDField()
    status = serializers.ChoiceField(choices=["APPROVED", "DECLINED"])
    reason = serializers.CharField(required=False)


class PaymentInspectionSerializer(serializers.Serializer):  # type: ignore[type-arg]  # DRF is not generic at runtime
    paymentId = serializers.UUIDField()
    status = serializers.ChoiceField(choices=["APPROVED", "DECLINED", "ERRORED"])
    chargeCount = serializers.IntegerField(min_value=0)
    requestCount = serializers.IntegerField(min_value=0)


class PaymentErrorDetailSerializer(serializers.Serializer):  # type: ignore[type-arg]  # DRF is not generic at runtime
    code = serializers.CharField()


class PaymentErrorSerializer(serializers.Serializer):  # type: ignore[type-arg]  # DRF is not generic at runtime
    error = PaymentErrorDetailSerializer()


class FrameworkErrorSerializer(serializers.Serializer):  # type: ignore[type-arg]  # DRF is not generic at runtime
    detail = serializers.CharField()
