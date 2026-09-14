# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
from datetime import timedelta

import pytest

from django_notifications.enums import DeliveryKind, DeliveryStatus
from django_notifications.models import Channel, Delivery, Notification
from django_notifications.services.notify_service import notify


def test_N01_notify_creates_unread_in_app_delivery(raise_high):
    notification = raise_high()
    assert notification.read_at is None
    assert notification.count == 1
    delivery = Delivery.objects.get(notification=notification)
    assert (delivery.kind, delivery.status) == (DeliveryKind.IN_APP, DeliveryStatus.SENT)
    assert delivery.sent_at is not None


def test_N04_same_subject_50_times_one_notification_count_50(raise_high):
    for _ in range(50):
        notification = raise_high()
    assert Notification.objects.count() == 1
    assert notification.count == 50
    assert Delivery.objects.count() == 1


def test_N04_new_notification_after_window(raise_high):
    first = raise_high()
    Notification.objects.filter(pk=first.pk).update(created_at=first.created_at - timedelta(seconds=61))
    second = raise_high()
    assert second.pk != first.pk
    assert Notification.objects.count() == 2


def test_N04_read_notification_is_not_counted(raise_high):
    first = raise_high()
    Notification.objects.filter(pk=first.pk).update(read_at=first.created_at)
    assert raise_high().pk != first.pk


def test_N04_different_title_is_a_new_notification(raise_high):
    assert raise_high(title="A").pk != raise_high(title="B").pk


def test_unknown_channel_raises(db):
    with pytest.raises(Channel.DoesNotExist):
        notify(channel_idx="nope", recipient_role="sales", severity="high", subject_ref="x", title="t")


def test_unknown_severity_raises(channel):
    with pytest.raises(ValueError):
        notify(channel_idx=channel.idx, recipient_role="sales", severity="urgent", subject_ref="x", title="t")
