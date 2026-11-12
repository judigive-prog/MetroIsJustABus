from rest_framework import serializers


class TicketTypeResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]  # DRF serializers are not generic at runtime
    id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    priceCents = serializers.IntegerField(source="price_cents")
    currency = serializers.CharField()
