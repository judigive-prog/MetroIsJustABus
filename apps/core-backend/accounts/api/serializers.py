from rest_framework import serializers

from accounts.models import RoleAssignment, User

# DRF serializers are not generic at runtime, hence the type-arg ignores below.


class RegisterRequestSerializer(serializers.Serializer):  # type: ignore[type-arg]
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(min_length=8, max_length=128, write_only=True, trim_whitespace=False)
    fullName = serializers.CharField(max_length=200)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")

    def validate_fullName(self, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise serializers.ValidationError("Full name must not be blank.")
        return stripped

    def validate_password(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Password must not be blank.")
        return value


class PassengerAccountResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    id = serializers.UUIDField()
    email = serializers.EmailField()
    fullName = serializers.CharField()
    contactEmail = serializers.EmailField()
    phone = serializers.CharField()
    role = serializers.ChoiceField(choices=RoleAssignment.Role.choices)
    status = serializers.ChoiceField(choices=User.Status.choices)
    createdAt = serializers.DateTimeField()
