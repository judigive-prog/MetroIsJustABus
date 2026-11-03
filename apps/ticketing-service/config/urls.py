from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

from common import health

urlpatterns = [
    path("health/live", health.live),
    path("health/ready", health.ready),
    path("api/ticketing/v1/", include("ticket_types.api.urls")),
    path("api/ticketing/v1/", include("purchases.api.urls")),
    path("api/ticketing/v1/schema", SpectacularAPIView.as_view(), name="schema"),
]
