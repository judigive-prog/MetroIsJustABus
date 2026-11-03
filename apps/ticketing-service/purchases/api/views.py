import copy
import uuid

from django.conf import settings
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from metro_common.correlation import get_correlation_id
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsPassenger
from common.schema import ErrorResponseSerializer
from purchases import selectors, services
from purchases.api.serializers import PurchaseCreateRequestSerializer, PurchaseResponseSerializer
from purchases.clients import get_payment_client
from purchases.exceptions import IdempotencyKeyRequired, PurchaseNotFound

IDEMPOTENCY_HEADER = "Idempotency-Key"


def _idempotency_key(request: Request) -> uuid.UUID:
    raw = request.headers.get(IDEMPOTENCY_HEADER, "")
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise IdempotencyKeyRequired() from exc


def _response(outcome: services.PurchaseOutcome) -> Response:
    body = copy.deepcopy(outcome.body)
    if "error" in body:
        body["error"]["correlationId"] = get_correlation_id()  # stored bodies never carry one
    headers: dict[str, str] = {}
    if outcome.http_status == 202:
        headers["Location"] = f"/api/ticketing/v1/purchases/{outcome.purchase_id}"
        headers["Retry-After"] = str(settings.PURCHASE_RETRY_AFTER_SECONDS)
    return Response(body, status=outcome.http_status, headers=headers)


class PurchaseCreateView(APIView):
    permission_classes = [IsPassenger]

    @extend_schema(
        summary="Buy one ticket (FR-032, FR-033)",
        parameters=[OpenApiParameter(IDEMPOTENCY_HEADER, OpenApiTypes.UUID, OpenApiParameter.HEADER, required=True)],
        request=PurchaseCreateRequestSerializer,
        responses={
            201: PurchaseResponseSerializer,
            202: PurchaseResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
            409: ErrorResponseSerializer,
            422: ErrorResponseSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        key = _idempotency_key(request)
        serializer = PurchaseCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        outcome = services.create_purchase(
            services.PurchaseRequest(
                passenger_id=request.user.id,
                idempotency_key=key,
                ticket_type_id=data["ticketTypeId"],
                expected_price_cents=data["expectedPriceCents"],
                payment_method_token=data["paymentMethodToken"],
            ),
            payment_client=get_payment_client(),
            correlation_id=get_correlation_id() or "",
        )
        return _response(outcome)


class PurchaseDetailView(APIView):
    permission_classes = [IsPassenger]

    @extend_schema(
        summary="Status of one of my purchases (FR-036)",
        responses={200: PurchaseResponseSerializer, 401: ErrorResponseSerializer, 404: ErrorResponseSerializer},
    )
    def get(self, request: Request, purchase_id: uuid.UUID) -> Response:
        purchase = selectors.find_purchase_for_passenger(purchase_id, request.user.id)
        if purchase is None:
            raise PurchaseNotFound()
        return Response(selectors.purchase_body(purchase))
