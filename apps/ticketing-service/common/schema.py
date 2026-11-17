from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.openapi import AutoSchema
from rest_framework import serializers


class JWTAuthenticationSchema(OpenApiAuthenticationExtension):
    """Describe the existing authentication class; do not change token checks."""

    target_class = "common.auth.JWTAuthentication"
    name = "bearerAuth"

    def get_security_definition(self, auto_schema: AutoSchema) -> dict[str, str]:
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}


class ErrorDetailSerializer(serializers.Serializer):  # type: ignore[type-arg]  # DRF serializers are not generic at runtime
    code = serializers.CharField()
    message = serializers.CharField()
    correlationId = serializers.CharField()


class ErrorResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]  # see above
    error = ErrorDetailSerializer()
