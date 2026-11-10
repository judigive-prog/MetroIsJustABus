from django.urls import path

from inbox.api.views import InboxListView, InboxMarkAllReadView, InboxMarkReadView

urlpatterns = [
    path("inbox", InboxListView.as_view(), name="inbox-list"),
    path("inbox/read-all", InboxMarkAllReadView.as_view(), name="inbox-read-all"),
    path("inbox/<uuid:pk>/read", InboxMarkReadView.as_view(), name="inbox-mark-read"),
]
