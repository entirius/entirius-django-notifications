# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Escalation: unread notifications older than a rule's minutes get one delivery per rule target."""

from datetime import datetime, timedelta
from functools import partial

from django.db import transaction
from django.utils import timezone

from django_notifications.enums import DeliveryStatus
from django_notifications.models import Delivery, EscalationRule, Notification
from django_notifications.tasks.deliver import deliver


def run_escalation(*, now: datetime | None = None) -> int:
    """Create (and enqueue) every due delivery; returns how many were created. Safe to run repeatedly."""
    now = now or timezone.now()
    return sum(_escalate_rule(rule, now) for rule in EscalationRule.objects.all())


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
