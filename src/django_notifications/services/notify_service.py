# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""`notify()` — the one entry point every module uses to ask a human for attention."""

import hashlib
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from django_notifications.enums import DeliveryKind, DeliveryStatus, Severity
from django_notifications.models import Channel, Delivery, Notification
from django_notifications.settings import NOTIFICATIONS_DEDUP_WINDOW_S


def notify(
    *,
    channel_idx: str,
    recipient_role: str,
    severity: str,
    subject_ref: str,
    title: str,
    body: str = "",
    dedup_window_s: int = NOTIFICATIONS_DEDUP_WINDOW_S,
) -> Notification:
    """Create an unread in-app notification, or count a repeat of an unread one inside the dedup window.

    Raises `Channel.DoesNotExist` for an unknown channel and `ValueError` for an unknown severity.
    """
    severity = Severity(severity).value
    channel = Channel.objects.get(idx=channel_idx)
    dedup_key = hashlib.sha256(f"{subject_ref}|{title}".encode()).hexdigest()[:64]
    with transaction.atomic():
        repeat = _recent_unread(channel, dedup_key, dedup_window_s)
        if repeat is not None:
            return _count_repeat(repeat)
        notification = Notification.objects.create(
            channel=channel,
            recipient_role=recipient_role,
            severity=severity,
            subject_ref=subject_ref,
            title=title,
            body=body,
            dedup_key=dedup_key,
        )
        Delivery.objects.create(
            notification=notification, kind=DeliveryKind.IN_APP, status=DeliveryStatus.SENT, sent_at=timezone.now()
        )
    return notification


def _recent_unread(channel: Channel, dedup_key: str, window_s: int) -> Notification | None:
    since = timezone.now() - timedelta(seconds=window_s)
    candidates = Notification.objects.select_for_update().filter(
        channel=channel, dedup_key=dedup_key, read_at__isnull=True, created_at__gte=since
    )
    return candidates.order_by("-created_at").first()


def _count_repeat(notification: Notification) -> Notification:
    Notification.objects.filter(pk=notification.pk).update(count=F("count") + 1, modified_at=timezone.now())
    notification.refresh_from_db()
    return notification
