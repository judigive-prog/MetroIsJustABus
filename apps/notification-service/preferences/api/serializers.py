from rest_framework import serializers

from preferences.models import ChangeType, NotificationChannel, NotificationPreference


class PreferenceItemSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    channel = serializers.ChoiceField(choices=NotificationChannel.choices)
    enabled = serializers.BooleanField()
    enabledChangeTypes = serializers.ListField(  # type: ignore[var-annotated]
        child=serializers.ChoiceField(choices=ChangeType.choices),
        source="enabled_change_types",
    )

    class Meta:
        model = NotificationPreference
        fields = ("channel", "enabled", "enabledChangeTypes")


class PreferencesResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    preferences = PreferenceItemSerializer(many=True)


class PreferenceUpdateRequestSerializer(serializers.Serializer):  # type: ignore[type-arg]
    enabled = serializers.BooleanField()
    enabledChangeTypes = serializers.ListField(  # type: ignore[var-annotated]
        child=serializers.ChoiceField(choices=ChangeType.choices),
        default=list,
    )


class PreferencesBulkUpdateRequestSerializer(serializers.Serializer):  # type: ignore[type-arg]
    preferences = serializers.ListField(child=serializers.DictField())  # type: ignore[var-annotated]
