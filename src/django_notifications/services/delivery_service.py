# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Sends one escalation delivery. The only writer of `Delivery.status` after creation.

django_email and entirius-py-googlechat are soft dependencies: when absent the delivery is skipped.
The Google Chat webhook URL is a secret — it never reaches a log line or `last_error`.
"""

import functools
import logging
import smtplib
from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.db.models import F
from django.utils import timezone

from django_notifications.enums import DeliveryKind, DeliveryStatus
from django_notifications.models import Delivery, DeliveryChannelConfig, Notification

logger = logging.getLogger(__name__)

# Transient transport errors (SMTP hiccups, refused connections): the task retries these.
RETRYABLE_ERRORS = (smtplib.SMTPException, OSError)
LIVE_SENDS_DISABLED = "live sends disabled outside production"


class DeliverySkipped(Exception):
    """Nothing to send to (no active config, blank target, backend package absent, or live sends disabled)."""


class DeliveryFailed(Exception):
    """A send failed before reaching the backend; the message is safe to store in `last_error`."""


def deliver(delivery_id: int, *, final_try: bool = True) -> Delivery:
    """Claim a pending delivery and send it once; ends `sent`, `skipped` (with a warning) or `failed`.

    The claim (`pending` → `sending`, `attempts + 1`) is one UPDATE, so a redelivered or concurrent task that
    loses it sends nothing. A retryable error before the final try puts the row back to `pending` and re-raises
    for the task's autoretry.
    """
    claimed = Delivery.objects.filter(pk=delivery_id, status=DeliveryStatus.PENDING).update(
        status=DeliveryStatus.SENDING, attempts=F("attempts") + 1, modified_at=timezone.now()
    )
    delivery = Delivery.objects.select_related("notification__channel").get(pk=delivery_id)
    if claimed:
        _send(delivery, final_try)
    return delivery


def _send(delivery: Delivery, final_try: bool) -> None:
    notification = delivery.notification
    try:
        _SENDERS[delivery.kind](notification, _active_config(notification, delivery.kind))
    except DeliverySkipped as exc:
        logger.warning("Notification %s: %s delivery skipped: %s", notification.pk, delivery.kind, exc)
        return _finish(delivery, DeliveryStatus.SKIPPED, str(exc))
    except RETRYABLE_ERRORS as exc:
        if not final_try:
            _finish(delivery, DeliveryStatus.PENDING, _error_text(exc))
            raise
        return _fail(delivery, _error_text(exc))
    except DeliveryFailed as exc:
        return _fail(delivery, str(exc))
    except Exception as exc:  # noqa: BLE001 — any send failure ends the delivery, never the caller
        return _fail(delivery, _error_text(exc))
    _finish(delivery, DeliveryStatus.SENT)


def _active_config(notification: Notification, kind: str) -> dict:
    config = DeliveryChannelConfig.objects.filter(channel_id=notification.channel_id, kind=kind, is_active=True).first()
    return config.config if config and isinstance(config.config, dict) else {}


def _fail(delivery: Delivery, error: str) -> None:
    logger.warning("Notification %s: %s delivery failed: %s", delivery.notification_id, delivery.kind, error)
    _finish(delivery, DeliveryStatus.FAILED, error)


def _finish(delivery: Delivery, status: str, error: str = "") -> None:
    """Writes the outcome; `attempts` was already counted by the claim."""
    delivery.status = status
    delivery.last_error = error
    delivery.sent_at = timezone.now() if status == DeliveryStatus.SENT else None
    delivery.save(update_fields=["status", "last_error", "sent_at", "modified_at"])


def _error_text(exc: Exception) -> str:
    """Error class + status only — exception messages may embed hosts or the webhook URL."""
    status = getattr(exc, "status_code", None) or getattr(exc, "smtp_code", None)
    return f"{type(exc).__name__} (status={status})"


def _require_live_sends() -> None:
    """Real sinks only in production, or where the host vouches every sink is a sandbox."""
    if getattr(settings, "ENVIRONMENT", "") == "production":
        return
    if not getattr(settings, "NOTIFICATIONS_ALLOW_LIVE_SENDS", False):
        raise DeliverySkipped(LIVE_SENDS_DISABLED)


def _send_email(notification: Notification, config: dict) -> None:
    recipients = config.get("recipients") or []
    if not recipients:
        raise DeliverySkipped("no active email config with recipients")
    build_email_domain = _email_domain_factory()
    if build_email_domain is None:
        raise DeliverySkipped("django_email is not installed")
    _require_live_sends()
    subject = " ".join(notification.title.splitlines())
    build_email_domain(notification.channel.idx).send_email(
        subject=subject, message=notification.body, recipient_list=list(recipients)
    )


def _send_google_chat(notification: Notification, config: dict) -> None:
    url = str(config.get("webhook_url") or "").strip()
    if not url:
        raise DeliverySkipped("no active google_chat config with a webhook_url")
    webhook = _google_chat_class()
    if webhook is None:
        raise DeliverySkipped("entirius-py-googlechat is not installed")
    _require_live_sends()
    webhook(url).send_text(f"[{notification.severity}] {notification.title}\n{notification.body}")


_SENDERS = {DeliveryKind.EMAIL: _send_email, DeliveryKind.GOOGLE_CHAT: _send_google_chat}


@functools.cache
def _email_domain_factory() -> Callable[[str], Any] | None:
    """`channel_idx -> EmailDomain` (per-channel SMTP from `EMAIL_SMTP_CONFIGURATION_CHANNELS`), or None."""
    try:
        from django_email.domain import EmailDomain
        from process_logger import ProcessLogger
    except (ImportError, RuntimeError):
        # RuntimeError: django_email importable but not in INSTALLED_APPS.
        logger.warning("django_email not installed — email deliveries are skipped for this process lifetime")
        return None

    def build(channel_idx: str) -> EmailDomain:
        try:
            domain = EmailDomain(channel_idx=channel_idx)
        except Exception as exc:  # noqa: BLE001 — a misconfigured backend ends the delivery readably
            raise DeliveryFailed(f"email backend setup failed: {type(exc).__name__}") from None
        domain.set_logger(ProcessLogger(process_name="notification_delivery", module="django_notifications"))
        return domain

    return build


@functools.cache
def _google_chat_class() -> type | None:
    try:
        from entirius_googlechat import GoogleChatWebhook
    except ImportError:
        logger.warning("entirius-py-googlechat not installed — chat deliveries are skipped for this process lifetime")
        return None
    return GoogleChatWebhook
