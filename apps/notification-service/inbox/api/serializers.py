from rest_framework import serializers

from inbox.models import InboxNotification


class InboxNotificationResponseSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    eventId = serializers.UUIDField(source="event_id")
    changeType = serializers.CharField(source="change_type")
    entityType = serializers.CharField(source="entity_type")
    entityId = serializers.CharField(source="entity_id")
    read = serializers.SerializerMethodField()
    readAt = serializers.DateTimeField(source="read_at")
    createdAt = serializers.DateTimeField(source="created_at")

    class Meta:
        model = InboxNotification
        fields = (
            "id",
            "eventId",
            "title",
            "body",
            "changeType",
            "entityType",
            "entityId",
            "read",
            "readAt",
            "createdAt",
        )

    def get_read(self, obj: InboxNotification) -> bool:
        return obj.read_at is not None


class InboxListResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    items = InboxNotificationResponseSerializer(many=True)
    unreadCount = serializers.IntegerField()


class MarkAllReadResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    markedCount = serializers.IntegerField()
