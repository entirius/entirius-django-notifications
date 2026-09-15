# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.db import models
from django_utils.models.base_model import BaseModel

from django_notifications.enums import DeliveryKind, DeliveryStatus


class Delivery(BaseModel):
    """One delivery step of a notification. The unique (notification, kind) makes every step happen once."""

    notification = models.ForeignKey(
        "django_notifications.Notification", on_delete=models.CASCADE, related_name="deliveries"
    )
    kind = models.CharField(max_length=16, choices=DeliveryKind.choices)
    status = models.CharField(max_length=16, choices=DeliveryStatus.choices, default=DeliveryStatus.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True, default="")
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["notification", "kind"], name="notif_delivery_notification_kind_uniq")
        ]
        verbose_name_plural = "deliveries"

    def __str__(self) -> str:
        return f"{self.notification_id}:{self.kind}:{self.status}"
