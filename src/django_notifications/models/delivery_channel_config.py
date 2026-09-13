# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.db import models
from django_utils.models.base_model import BaseModel

from django_notifications.enums import DeliveryKind


class DeliveryChannelConfig(BaseModel):
    """Per-channel delivery target. `config`: email `{"recipients": [...]}`, google_chat `{"webhook_url": "..."}`.

    The webhook URL carries `key` + `token` — never log it or return it from the API.
    """

    channel = models.ForeignKey(
        "django_notifications.Channel", on_delete=models.CASCADE, related_name="delivery_configs"
    )
    kind = models.CharField(max_length=16, choices=DeliveryKind.choices)
    config = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["channel", "kind"], name="notif_config_channel_kind_uniq")]

    def __str__(self) -> str:
        return f"{self.channel_id}:{self.kind}"
