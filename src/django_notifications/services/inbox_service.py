# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Reading side of notifications for the admin API: list, count, detail, mark read."""

from django.db.models import QuerySet
from django.utils import timezone

from django_notifications.models import Channel, Notification


def get_channel(channel_idx: str) -> Channel:
    return Channel.objects.get(idx=channel_idx)


def list_notifications(channel: Channel, *, unread: bool = False, role: str | None = None) -> QuerySet[Notification]:
    """Newest first."""
    qs = Notification.objects.filter(channel=channel)
    if unread:
        qs = qs.filter(read_at__isnull=True)
    if role:
        qs = qs.filter(recipient_role=role)
    return qs.order_by("-created_at", "-pk")


def unread_count(channel: Channel) -> int:
    return Notification.objects.filter(channel=channel, read_at__isnull=True).count()


def get_notification(channel: Channel, pk: int) -> Notification:
    return Notification.objects.prefetch_related("deliveries").get(channel=channel, pk=pk)


def mark_read(notification: Notification) -> Notification:
    """Idempotent — an already read notification keeps its original `read_at`."""
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at", "modified_at"])
    return notification


def mark_all_read(channel: Channel, *, role: str | None = None) -> int:
    """Mark every unread notification of the channel (optionally one role) read; returns how many."""
    qs = list_notifications(channel, unread=True, role=role).order_by()
    now = timezone.now()
    return qs.update(read_at=now, modified_at=now)
