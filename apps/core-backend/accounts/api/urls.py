from django.urls import path

from accounts.api.views import JWKSView, LoginView, LogoutView, RegisterView, SessionView

urlpatterns = [
    path("auth/register", RegisterView.as_view(), name="auth-register"),
    path("auth/login", LoginView.as_view(), name="auth-login"),
    path("auth/logout", LogoutView.as_view(), name="auth-logout"),
    path("auth/session", SessionView.as_view(), name="auth-session"),
    path("auth/jwks", JWKSView.as_view(), name="auth-jwks"),
]
