from django.urls import path
from drf_spectacular.views import SpectacularAPIView

from common import health

urlpatterns = [
    path("health/live", health.live),
    path("health/ready", health.ready),
    path("api/notifications/v1/schema", SpectacularAPIView.as_view(), name="schema"),
]
