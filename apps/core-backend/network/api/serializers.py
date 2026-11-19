from rest_framework import serializers

# DRF serializers are not generic at runtime, hence the type-arg ignores below.


class LineResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()


class StopResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()
