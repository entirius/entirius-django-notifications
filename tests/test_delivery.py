# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
import logging
import smtplib

import pytest
from django.core import mail
from django_email.domain import EmailDomain

from django_notifications.enums import DeliveryKind, DeliveryStatus
from django_notifications.models import Delivery, DeliveryChannelConfig
from django_notifications.services import delivery_service
from django_notifications.tasks.deliver import deliver
from tests.conftest import WEBHOOK_URL


@pytest.fixture
def pending(escalation_setup, raise_high):
    """A pending delivery of the given kind for a fresh high notification."""

    def _pending(kind: str = DeliveryKind.EMAIL) -> Delivery:
        return Delivery.objects.create(notification=raise_high(), kind=kind, status=DeliveryStatus.PENDING)

    return _pending


@pytest.fixture
def flaky_smtp(monkeypatch):
    """`EmailDomain.send_email` raises the queued errors first, then sends for real (locmem)."""
    errors: list[Exception] = []
    real_send = EmailDomain.send_email

    def send_email(self, **kwargs):
        if errors:
            raise errors.pop(0)
        return real_send(self, **kwargs)

    monkeypatch.setattr(EmailDomain, "send_email", send_email)
    return errors


def _reload(delivery: Delivery) -> Delivery:
    delivery.refresh_from_db()
    return delivery


@pytest.mark.usefixtures("eager_celery")
def test_N02_redelivered_task_sends_once(pending):
    delivery = pending()
    deliver.delay(delivery.pk)
    deliver.delay(delivery.pk)  # the requeue of an acks_late task
    assert len(mail.outbox) == 1
    assert (_reload(delivery).status, delivery.attempts) == (DeliveryStatus.SENT, 1)


def test_delivery_claimed_by_another_worker_is_not_sent(pending):
    delivery = pending()
    Delivery.objects.filter(pk=delivery.pk).update(status=DeliveryStatus.SENDING)
    assert delivery_service.deliver(delivery.pk).status == DeliveryStatus.SENDING
    assert mail.outbox == []


@pytest.mark.parametrize("kind", [DeliveryKind.EMAIL, DeliveryKind.GOOGLE_CHAT])
def test_live_sends_skipped_outside_production(pending, settings, caplog, kind):
    settings.NOTIFICATIONS_ALLOW_LIVE_SENDS = False
    DeliveryChannelConfig.objects.filter(kind=DeliveryKind.GOOGLE_CHAT).update(config={"webhook_url": WEBHOOK_URL})
    delivery = pending(kind)
    with caplog.at_level(logging.WARNING, logger="django_notifications"):
        delivery_service.deliver(delivery.pk)
    assert (_reload(delivery).status, delivery.last_error) == (
        DeliveryStatus.SKIPPED,
        "live sends disabled outside production",
    )
    assert mail.outbox == []
    assert "live sends disabled" in caplog.text
    assert "SECRET" not in caplog.text


def test_live_sends_allowed_in_production(pending, settings):
    settings.NOTIFICATIONS_ALLOW_LIVE_SENDS = False
    settings.ENVIRONMENT = "production"
    delivery = pending()
    assert delivery_service.deliver(delivery.pk).status == DeliveryStatus.SENT
    assert len(mail.outbox) == 1


@pytest.mark.usefixtures("eager_celery")
def test_email_transient_smtp_error_retries(pending, flaky_smtp):
    flaky_smtp.append(smtplib.SMTPServerDisconnected("hiccup"))
    delivery = pending()
    deliver.delay(delivery.pk)
    assert (_reload(delivery).status, delivery.attempts, delivery.last_error) == (DeliveryStatus.SENT, 2, "")
    assert len(mail.outbox) == 1


@pytest.mark.usefixtures("eager_celery")
def test_email_smtp_error_after_retries_is_failed(pending, flaky_smtp):
    flaky_smtp.extend(ConnectionRefusedError("down") for _ in range(4))
    delivery = pending()
    assert deliver.delay(delivery.pk).get() == DeliveryStatus.FAILED  # the final try records, never raises
    assert (_reload(delivery).status, delivery.attempts) == (DeliveryStatus.FAILED, 4)
    assert delivery.last_error == "ConnectionRefusedError (status=None)"


def test_email_backend_setup_failure_has_readable_error(pending, monkeypatch):
    def broken_init(self, **kwargs):
        raise AttributeError("'Settings' object has no attribute 'EMAIL_SMTP_CONFIGURATION_CHANNELS'")

    monkeypatch.setattr(EmailDomain, "__init__", broken_init)
    delivery = pending()
    delivery_service.deliver(delivery.pk)
    assert (_reload(delivery).status, delivery.last_error) == (
        DeliveryStatus.FAILED,
        "email backend setup failed: AttributeError",
    )
