from django.urls import path

from subscriptions.api.views import SubscriptionDetailView, SubscriptionsView

urlpatterns = [
    path("subscriptions", SubscriptionsView.as_view(), name="subscriptions-list-create"),
    path("subscriptions/<uuid:pk>", SubscriptionDetailView.as_view(), name="subscriptions-detail"),
]
