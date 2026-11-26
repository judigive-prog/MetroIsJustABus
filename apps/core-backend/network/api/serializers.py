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


class OrderedStopResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    position = serializers.IntegerField()
    stopId = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()


class RoutePatternResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    id = serializers.UUIDField()
    directionLabel = serializers.CharField()
    revision = serializers.IntegerField()
    stops = OrderedStopResponseSerializer(many=True)


class LineOrderedStopsResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    lineId = serializers.UUIDField()
    lineCode = serializers.CharField()
    lineName = serializers.CharField()
    patterns = RoutePatternResponseSerializer(many=True)
