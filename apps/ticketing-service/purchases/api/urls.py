from django.urls import path

from purchases.api.views import PurchaseCreateView, PurchaseDetailView

urlpatterns = [
    path("purchases", PurchaseCreateView.as_view(), name="purchase-create"),
    path("purchases/<uuid:purchase_id>", PurchaseDetailView.as_view(), name="purchase-detail"),
]
