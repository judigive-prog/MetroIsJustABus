from django.http import HttpRequest, JsonResponse
from django.urls import include, path


def health(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("health/live", health),
    path("health/ready", health),
    path("api/payment-sim/v1/", include("payments.api.urls")),
]
