from rest_framework import serializers


class ErrorDetailSerializer(serializers.Serializer):  # type: ignore[type-arg]  # DRF serializers are not generic at runtime
    code = serializers.CharField()
    message = serializers.CharField()
    correlationId = serializers.CharField()


class ErrorResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]  # see above
    error = ErrorDetailSerializer()
