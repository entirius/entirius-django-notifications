# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.db import models
from django_utils.models.base_model import BaseModel

from django_notifications.enums import ESCALATION_KIND_CHOICES, Severity


class EscalationRule(BaseModel):
    """An unread notification of `severity` older than `after_minutes` is delivered to `to_kind`."""

    channel = models.ForeignKey(
        "django_notifications.Channel", on_delete=models.CASCADE, related_name="escalation_rules"
    )
    severity = models.CharField(max_length=16, choices=Severity.choices)
    after_minutes = models.PositiveIntegerField()
    to_kind = models.CharField(max_length=16, choices=ESCALATION_KIND_CHOICES)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["channel", "severity", "to_kind"], name="notif_rule_channel_sev_kind_uniq")
        ]

    def __str__(self) -> str:
        return f"{self.severity} +{self.after_minutes}min -> {self.to_kind}"
