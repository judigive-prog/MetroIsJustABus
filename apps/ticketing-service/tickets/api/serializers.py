from rest_framework import serializers


class TicketTypeSummarySerializer(serializers.Serializer):  # type: ignore[type-arg]
    id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)


class ValidationHistoryItemSerializer(serializers.Serializer):  # type: ignore[type-arg]
    id = serializers.UUIDField()
    result = serializers.ChoiceField(choices=["ACCEPTED", "REJECTED"])
    reason = serializers.CharField(allow_null=True, required=False)
    decidedAt = serializers.DateTimeField(source="decided_at")
    stopId = serializers.UUIDField(source="stop_id", allow_null=True, required=False)
    validatorId = serializers.UUIDField(source="validator_id", allow_null=True, required=False)
    deviceTime = serializers.DateTimeField(source="device_time", allow_null=True, required=False)


class TicketStateChangeSerializer(serializers.Serializer):  # type: ignore[type-arg]
    id = serializers.UUIDField()
    fromStatus = serializers.CharField(source="from_status", allow_null=True, required=False)
    toStatus = serializers.CharField(source="to_status")
    reason = serializers.CharField()
    occurredAt = serializers.DateTimeField(source="created_at")


class TicketResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    id = serializers.UUIDField()
    ticketType = TicketTypeSummarySerializer(source="ticket_type")
    status = serializers.ChoiceField(choices=["ISSUED", "ACTIVE", "USED_UP", "EXPIRED", "CANCELLED"])
    terms = serializers.JSONField(source="terms_snapshot")
    priceCents = serializers.IntegerField(source="price_cents")
    currency = serializers.CharField()
    remainingJourneys = serializers.IntegerField(source="remaining_journeys", allow_null=True)
    activatedAt = serializers.DateTimeField(source="activated_at", allow_null=True)
    validUntil = serializers.DateTimeField(source="valid_until", allow_null=True)
    issuedAt = serializers.DateTimeField(source="issued_at")
    createdAt = serializers.DateTimeField(source="created_at")
    validationHistory = ValidationHistoryItemSerializer(source="validation_attempts", many=True)
    stateChanges = TicketStateChangeSerializer(source="state_changes", many=True, required=False)
