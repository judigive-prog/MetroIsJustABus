import uuid

from django.db.models import QuerySet

from inbox.models import InboxNotification


def list_passenger_notifications(passenger_id: uuid.UUID, unread_only: bool = False) -> QuerySet[InboxNotification]:
    qs = InboxNotification.objects.filter(passenger_id=passenger_id)
    if unread_only:
        qs = qs.filter(read_at__isnull=True)
    return qs.order_by("-created_at")


def get_passenger_notification(passenger_id: uuid.UUID, notification_id: uuid.UUID) -> InboxNotification | None:
    return InboxNotification.objects.filter(id=notification_id, passenger_id=passenger_id).first()


def count_unread_notifications(passenger_id: uuid.UUID) -> int:
    return InboxNotification.objects.filter(passenger_id=passenger_id, read_at__isnull=True).count()
