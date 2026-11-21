from django.urls import path

from tickets.api.views import TicketDetailView, TicketListView

urlpatterns = [
    path("tickets", TicketListView.as_view(), name="ticket-list"),
    path("tickets/<uuid:ticket_id>", TicketDetailView.as_view(), name="ticket-detail"),
]
