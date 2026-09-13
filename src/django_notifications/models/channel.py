# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.db import models
from django_utils.models.base_model import BaseModel
from idx_normalizator import validate_idx


class Channel(BaseModel):
    idx = models.CharField(max_length=128, unique=True)
    label = models.CharField(max_length=128)
    default_language = models.ForeignKey(
        "django_regional.Language",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="notification_default_channels",
    )
    languages = models.ManyToManyField("django_regional.Language", blank=True, related_name="notification_channels")

    def __str__(self) -> str:
        return f"{self.label} [{self.idx}]"

    def save(self, *args, **kwargs) -> None:
        validate_idx(str(self.idx))
        super().save(*args, **kwargs)
