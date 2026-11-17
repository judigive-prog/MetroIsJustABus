from django.urls import path

from accounts.api.views import RegisterView

urlpatterns = [
    path("auth/register", RegisterView.as_view(), name="auth-register"),
]
