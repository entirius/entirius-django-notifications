# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.db import models


class Severity(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    CRITICAL = "critical", "Critical"


class DeliveryKind(models.TextChoices):
    IN_APP = "in_app", "In-app"
    EMAIL = "email", "Email"
    GOOGLE_CHAT = "google_chat", "Google Chat"


# Escalation never targets in-app — in-app is the immediate step of every notification.
ESCALATION_KIND_CHOICES = [(kind.value, kind.label) for kind in (DeliveryKind.EMAIL, DeliveryKind.GOOGLE_CHAT)]


class DeliveryStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SENDING = "sending", "Sending"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"
