from django.urls import path

from network.api.views import LineListView, StopListView

urlpatterns = [
    path("lines", LineListView.as_view(), name="line-list"),
    path("stops", StopListView.as_view(), name="stop-list"),
]
