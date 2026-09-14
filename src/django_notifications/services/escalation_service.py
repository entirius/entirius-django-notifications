# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Escalation: unread notifications older than a rule's minutes get one delivery per rule target."""

from datetime import datetime, timedelta
from functools import partial

from django.db import transaction
from django.utils import timezone

from django_notifications.enums import DeliveryStatus
from django_notifications.models import Channel, Delivery, EscalationRule, Notification
from django_notifications.settings import NOTIFICATIONS_DELIVERY_STALE_MINUTES
from django_notifications.tasks.deliver import deliver


def run_escalation(*, now: datetime | None = None, channel: Channel | None = None) -> int:
    """Create (and enqueue) every due delivery; returns how many were created. Safe to run repeatedly.

    `channel` limits the run to one channel. Stale `pending` deliveries (enqueue lost) are enqueued again.
    """
    now = now or timezone.now()
    rules = EscalationRule.objects.all()
    if channel is not None:
        rules = rules.filter(channel=channel)
    _requeue_stale(now, channel)
    return sum(_escalate_rule(rule, now) for rule in rules)


def _requeue_stale(now: datetime, channel: Channel | None) -> None:
    stale = Delivery.objects.filter(
        status=DeliveryStatus.PENDING, modified_at__lte=now - timedelta(minutes=NOTIFICATIONS_DELIVERY_STALE_MINUTES)
    )
    if channel is not None:
        stale = stale.filter(notification__channel=channel)
    for delivery_id in stale.values_list("pk", flat=True):
        transaction.on_commit(partial(deliver.delay, delivery_id))


def _escalate_rule(rule: EscalationRule, now: datetime) -> int:
    due = Notification.objects.filter(
        channel_id=rule.channel_id,
        severity=rule.severity,
        read_at__isnull=True,
        created_at__lte=now - timedelta(minutes=rule.after_minutes),
    ).exclude(deliveries__kind=rule.to_kind)
    created = 0
    for notification in due.iterator():
        delivery, is_new = Delivery.objects.get_or_create(
            notification=notification, kind=rule.to_kind, defaults={"status": DeliveryStatus.PENDING}
        )
        if is_new:
            transaction.on_commit(partial(deliver.delay, delivery.pk))
            created += 1
    return created
