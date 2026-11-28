from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts import selectors, services
from accounts.api.serializers import (
    JWKSResponseSerializer,
    LoginRequestSerializer,
    LoginResponseSerializer,
    PassengerAccountResponseSerializer,
    RegisterRequestSerializer,
    SessionResponseSerializer,
)
from accounts.models import RoleAssignment
from accounts.tokens import jwks_body
from common.clock import default_clock, to_iso
from common.permissions import IsAuthenticatedRole
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


class LoginView(APIView):
    """Public sign-in endpoint issuing a revocable RS256 access token (FR-021)."""

    permission_classes = [AllowAny]  # public on purpose: callers sign in before holding a token (FR-021)
    authentication_classes = []

    @extend_schema(
        summary="Sign in and start a session (FR-021)",
        request=LoginRequestSerializer,
        responses={
            200: LoginResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        serializer = LoginRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        outcome = services.authenticate_user(email=data["email"], raw_password=data["password"])
        return Response(
            {
                "accessToken": outcome.access_token,
                "tokenType": "Bearer",
                "expiresIn": outcome.expires_in,
                "sessionId": str(outcome.session.id),
                "issuedAt": to_iso(outcome.session.issued_at),
                "expiresAt": to_iso(outcome.session.expires_at),
                "user": selectors.account_body(outcome.user, role=outcome.session.role),
            },
            status=200,
        )


class LogoutView(APIView):
    """Revoke the caller's active authentication session (FR-021)."""

    permission_classes = [IsAuthenticatedRole]

    @extend_schema(
        summary="End the current session (FR-021)",
        request=None,
        responses={
            204: None,
            401: ErrorResponseSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        session_id = getattr(request.user, "session_id", None)
        if session_id is None:
            raise AuthenticationFailed()
        services.end_session(session_id=session_id, user_id=request.user.id)
        return Response(status=204)


class SessionView(APIView):
    """Return the caller's active authenticated session details (FR-021)."""

    permission_classes = [IsAuthenticatedRole]

    @extend_schema(
        summary="Inspect the current authenticated session (FR-021)",
        responses={
            200: SessionResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
    def get(self, request: Request) -> Response:
        session_id = getattr(request.user, "session_id", None)
        if session_id is None:
            raise AuthenticationFailed()
        session = selectors.find_active_session(
            session_id=session_id,
            user_id=request.user.id,
            now=default_clock.now(),
        )
        if session is None:
            raise AuthenticationFailed()
        return Response(selectors.session_body(session))


class JWKSView(APIView):
    """Public JWK Set for verifying RS256 tokens issued by core-backend."""

    permission_classes = [AllowAny]  # public on purpose: verification keys are not secret
    authentication_classes = []

    @extend_schema(
        summary="Public RS256 verification keys (JWKS)",
        responses={200: JWKSResponseSerializer},
    )
    def get(self, request: Request) -> Response:
        return Response(jwks_body())
