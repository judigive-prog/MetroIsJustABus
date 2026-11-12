from rest_framework import serializers


class ErrorDetailSerializer(serializers.Serializer):  # type: ignore[type-arg]
    code = serializers.CharField()
    message = serializers.CharField()
    correlationId = serializers.CharField()


class ErrorResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    error = ErrorDetailSerializer()
