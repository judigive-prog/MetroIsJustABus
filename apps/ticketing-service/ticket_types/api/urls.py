from django.urls import path

from ticket_types.api.views import TicketTypeListView

urlpatterns = [
    path("ticket-types", TicketTypeListView.as_view(), name="ticket-type-list"),
]
