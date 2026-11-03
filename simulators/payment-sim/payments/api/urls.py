from django.urls import path

from payments.api.views import PaymentCreateView, PaymentDetailView

urlpatterns = [
    path("payments", PaymentCreateView.as_view(), name="payment-create"),
    path("payments/<uuid:key>", PaymentDetailView.as_view(), name="payment-detail"),
]
