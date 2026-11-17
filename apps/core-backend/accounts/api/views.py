from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts import selectors, services
from accounts.api.serializers import PassengerAccountResponseSerializer, RegisterRequestSerializer
from accounts.models import RoleAssignment
from common.schema import ErrorResponseSerializer


class RegisterView(APIView):
    """Public passenger registration endpoint (FR-020)."""

    permission_classes = [AllowAny]  # public on purpose: visitors register before signing in (FR-020)
    authentication_classes = []

    @extend_schema(
        summary="Create a passenger account (FR-020)",
        request=RegisterRequestSerializer,
        responses={
            201: PassengerAccountResponseSerializer,
            400: ErrorResponseSerializer,
            409: ErrorResponseSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        serializer = RegisterRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = services.create_user_credentials(
            email=data["email"],
            raw_password=data["password"],
            full_name=data["fullName"],
            phone=data["phone"],
            role=RoleAssignment.Role.PASSENGER,
        )
        return Response(selectors.account_body(user, role=RoleAssignment.Role.PASSENGER), status=201)
