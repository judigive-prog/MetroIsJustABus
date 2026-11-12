from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

from common import health

urlpatterns = [
    path("health/live", health.live),
    path("health/ready", health.ready),
    path("api/notifications/v1/", include("subscriptions.api.urls")),
    path("api/notifications/v1/", include("preferences.api.urls")),
    path("api/notifications/v1/schema", SpectacularAPIView.as_view(), name="schema"),
]
