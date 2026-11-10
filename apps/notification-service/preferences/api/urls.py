from django.urls import path

from preferences.api.views import PreferenceDetailView, PreferencesView

urlpatterns = [
    path("preferences", PreferencesView.as_view(), name="preferences-list-update"),
    path("preferences/<str:channel>", PreferenceDetailView.as_view(), name="preferences-detail"),
]
