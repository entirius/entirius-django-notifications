# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
import logging
from datetime import timedelta

import httpx
import pytest
from django.core import mail
from django.utils import timezone

from django_notifications.enums import DeliveryKind, DeliveryStatus
from django_notifications.models import Delivery, DeliveryChannelConfig, Notification
from django_notifications.services.escalation_service import run_escalation
from tests.conftest import WEBHOOK_URL
from tests.factories import ChannelFactory, EscalationRuleFactory


def _escalate(django_capture_on_commit_callbacks, now) -> int:
    with django_capture_on_commit_callbacks(execute=True):
        return run_escalation(now=now)


def _statuses(notification) -> dict[str, str]:
    return dict(Delivery.objects.filter(notification=notification).values_list("kind", "status"))


@pytest.fixture
def chat_calls(monkeypatch):
    """Stand-in for respx (absent from the service venv): every webhook POST answers 503, no real sleeps."""
    calls: list[dict] = []

    def fake_post(url, *, json, timeout):
        calls.append(json)
        return httpx.Response(503, request=httpx.Request("POST", url))

    monkeypatch.setattr("entirius_googlechat.webhook.httpx.post", fake_post)
    monkeypatch.setattr("entirius_googlechat.webhook.time.sleep", lambda _s: None)
    return calls


@pytest.mark.usefixtures("eager_celery")
def test_N02_escalation_email_then_chat_each_once(escalation_setup, raise_high, django_capture_on_commit_callbacks):
    notification = raise_high(title="Lead waits for reply")
    start = notification.created_at

    assert _escalate(django_capture_on_commit_callbacks, start + timedelta(minutes=1)) == 1
    assert _statuses(notification) == {DeliveryKind.IN_APP: "sent", DeliveryKind.EMAIL: "sent"}
    assert [m.subject for m in mail.outbox] == ["Lead waits for reply"]
    assert mail.outbox[0].to == ["sandbox@greenmail.test"]

    assert _escalate(django_capture_on_commit_callbacks, start + timedelta(minutes=2)) == 1
    assert _statuses(notification)[DeliveryKind.GOOGLE_CHAT] == DeliveryStatus.SKIPPED

    assert _escalate(django_capture_on_commit_callbacks, start + timedelta(minutes=10)) == 0
    assert len(mail.outbox) == 1


@pytest.mark.usefixtures("eager_celery")
def test_N02_read_notification_never_escalates(escalation_setup, raise_high, django_capture_on_commit_callbacks):
    notification = raise_high()
    notification.read_at = timezone.now()
    notification.save()
    assert _escalate(django_capture_on_commit_callbacks, timezone.now() + timedelta(hours=1)) == 0


def test_N02_not_due_before_rule_minutes(escalation_setup, raise_high):
    notification = raise_high()
    assert run_escalation(now=notification.created_at + timedelta(seconds=59)) == 0


@pytest.mark.usefixtures("eager_celery")
def test_N03_chat_5xx_delivery_failed_in_app_unaffected(
    escalation_setup, raise_high, chat_calls, django_capture_on_commit_callbacks
):
    DeliveryChannelConfig.objects.filter(pk=escalation_setup.pk).update(config={"webhook_url": WEBHOOK_URL})
    notification = raise_high()

    _escalate(django_capture_on_commit_callbacks, notification.created_at + timedelta(minutes=2))

    chat = Delivery.objects.get(notification=notification, kind=DeliveryKind.GOOGLE_CHAT)
    assert len(chat_calls) == 3
    assert (chat.status, chat.attempts) == (DeliveryStatus.FAILED, 1)
    assert chat.last_error == "GoogleChatError (status=503)"
    assert _statuses(notification)[DeliveryKind.IN_APP] == DeliveryStatus.SENT
    notification.refresh_from_db()
    assert notification.read_at is None


@pytest.mark.usefixtures("eager_celery")
def test_N05_missing_webhook_url_skipped_with_warning(
    escalation_setup, raise_high, caplog, django_capture_on_commit_callbacks
):
    notification = raise_high()
    with caplog.at_level(logging.WARNING, logger="django_notifications"):
        _escalate(django_capture_on_commit_callbacks, notification.created_at + timedelta(minutes=2))
    chat = Delivery.objects.get(notification=notification, kind=DeliveryKind.GOOGLE_CHAT)
    assert (chat.status, chat.attempts) == (DeliveryStatus.SKIPPED, 1)  # the claim counts; a skip keeps it
    assert "google_chat delivery skipped" in caplog.text


@pytest.mark.usefixtures("eager_celery")
def test_webhook_url_never_logged_or_stored(
    escalation_setup, raise_high, chat_calls, caplog, django_capture_on_commit_callbacks
):
    DeliveryChannelConfig.objects.filter(pk=escalation_setup.pk).update(config={"webhook_url": WEBHOOK_URL})
    notification = raise_high()
    with caplog.at_level(logging.DEBUG):
        _escalate(django_capture_on_commit_callbacks, notification.created_at + timedelta(minutes=2))
    stored = Delivery.objects.get(notification=notification, kind=DeliveryKind.GOOGLE_CHAT).last_error
    assert "SECRET" not in caplog.text + stored


@pytest.mark.usefixtures("eager_celery")
def test_email_without_config_is_skipped(channel, raise_high, django_capture_on_commit_callbacks):
    EscalationRuleFactory(channel=channel, after_minutes=0)
    notification = raise_high()
    _escalate(django_capture_on_commit_callbacks, notification.created_at)
    assert _statuses(notification)[DeliveryKind.EMAIL] == DeliveryStatus.SKIPPED
    assert mail.outbox == []


@pytest.fixture
def other_channel_notification(db):
    other = ChannelFactory(idx="other-europe", label="Other Europe")
    EscalationRuleFactory(channel=other, after_minutes=1)
    return Notification.objects.create(
        channel=other, recipient_role="sales", severity="high", subject_ref="lead:7", title="Other waits"
    )


def test_run_escalation_scoped_to_channel(escalation_setup, raise_high, other_channel_notification):
    notification = raise_high()
    later = notification.created_at + timedelta(minutes=5)
    assert run_escalation(now=later, channel=notification.channel) == 2
    assert not Delivery.objects.filter(notification=other_channel_notification).exists()
    assert run_escalation(now=later) == 1


def test_stale_pending_delivery_requeued(escalation_setup, raise_high, django_capture_on_commit_callbacks, monkeypatch):
    enqueued: list[int] = []
    monkeypatch.setattr("django_notifications.services.escalation_service.deliver.delay", enqueued.append)
    stale = Delivery.objects.create(notification=raise_high(), kind=DeliveryKind.EMAIL)
    sent = Delivery.objects.create(notification=raise_high(title="Other"), kind=DeliveryKind.EMAIL, status="sent")
    with django_capture_on_commit_callbacks(execute=True):
        run_escalation(now=stale.modified_at + timedelta(minutes=29))
    assert stale.pk not in enqueued
    with django_capture_on_commit_callbacks(execute=True):
        run_escalation(now=stale.modified_at + timedelta(minutes=30))
    assert enqueued.count(stale.pk) == 1
    assert sent.pk not in enqueued
