from django.urls import path

from network.api.views import LineListView, LineOrderedStopsView, StopListView

urlpatterns = [
    path("lines", LineListView.as_view(), name="line-list"),
    path("lines/<uuid:line_id>/stops", LineOrderedStopsView.as_view(), name="line-stop-list"),
    path("stops", StopListView.as_view(), name="stop-list"),
]
