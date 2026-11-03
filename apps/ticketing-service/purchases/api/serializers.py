from rest_framework import serializers

# DRF serializers are not generic at runtime, hence the type-arg ignores below.


class PurchaseCreateRequestSerializer(serializers.Serializer):  # type: ignore[type-arg]
    ticketTypeId = serializers.UUIDField()
    expectedPriceCents = serializers.IntegerField(min_value=0)
    # Opaque simulated token (N-11). The allowed format is not specified anywhere yet; this regex is a placeholder.
    paymentMethodToken = serializers.RegexField(regex=r"^[A-Za-z0-9_]{1,64}$")


class PurchaseResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=["PENDING", "COMPLETED", "FAILED"])
    ticketTypeId = serializers.UUIDField()
    priceCents = serializers.IntegerField()
    currency = serializers.CharField()
    createdAt = serializers.DateTimeField()
    ticketId = serializers.UUIDField(required=False)
    completedAt = serializers.DateTimeField(required=False)
    failureCode = serializers.CharField(required=False)
