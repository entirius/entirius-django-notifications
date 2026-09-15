# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.db import models
from django_utils.models.base_model import BaseModel

from django_notifications.enums import Severity


class Notification(BaseModel):
    """Something a human must look at. Written only by `services.notify_service.notify`."""

    channel = models.ForeignKey("django_notifications.Channel", on_delete=models.CASCADE, related_name="notifications")
    recipient_role = models.CharField(max_length=64, db_index=True)
    severity = models.CharField(max_length=16, choices=Severity.choices)
    subject_ref = models.CharField(max_length=200, db_index=True)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True, default="")
    dedup_key = models.CharField(max_length=64, db_index=True)
    count = models.PositiveIntegerField(default=1)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["channel", "read_at"], name="notif_channel_read_idx")]

    def __str__(self) -> str:
        return f"[{self.severity}] {self.title}"
