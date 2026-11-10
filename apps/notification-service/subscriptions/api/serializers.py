from rest_framework import serializers

from subscriptions.models import EntityType, Subscription


class SubscriptionCreateRequestSerializer(serializers.Serializer):  # type: ignore[type-arg]
    entityType = serializers.ChoiceField(choices=EntityType.choices)
    entityId = serializers.CharField(max_length=128, min_length=1)


class SubscriptionUpdateRequestSerializer(serializers.Serializer):  # type: ignore[type-arg]
    active = serializers.BooleanField()


class SubscriptionResponseSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    entityType = serializers.CharField(source="entity_type")
    entityId = serializers.CharField(source="entity_id")
    createdAt = serializers.DateTimeField(source="created_at")
    updatedAt = serializers.DateTimeField(source="updated_at")

    class Meta:
        model = Subscription
        fields = ("id", "entityType", "entityId", "active", "createdAt", "updatedAt")


class SubscriptionListResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    items = SubscriptionResponseSerializer(many=True)
