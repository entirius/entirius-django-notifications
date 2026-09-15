# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Request schemas of the notifications admin API v2."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from django_notifications.enums import Severity


class NotificationListQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")

    unread: bool = Field(default=False, description="Only unread notifications when true.", examples=[True])
    role: str | None = Field(default=None, max_length=64, description="Only this recipient role.", examples=["sales"])


class ReadAllRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str | None = Field(
        default=None, max_length=64, description="Mark only this recipient role's notifications.", examples=["sales"]
    )


class DevNotifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient_role: str = Field(min_length=1, max_length=64, description="Who should act.", examples=["sales"])
    severity: Severity = Field(description="Drives the escalation rules.", examples=["high"])
    subject_ref: str = Field(
        min_length=1, max_length=200, description="What it is about — dedup subject.", examples=["lead:42"]
    )
    title: str = Field(
        min_length=1, max_length=200, description="One-line headline.", examples=["Lead waits for reply"]
    )
    body: str = Field(default="", description="Plain-text details.", examples=["No reply for 2 days."])


class DevRunEscalationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    now: datetime | None = Field(
        default=None, description="Clock to escalate against; server time when null.", examples=["2026-09-13T12:00:00Z"]
    )
