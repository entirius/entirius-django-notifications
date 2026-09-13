# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Response schemas of the notifications admin API v2. Delivery configs (webhook URLs) are never exposed."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: str = Field(description="in_app, email or google_chat.", examples=["email"])
    status: str = Field(description="pending, sent, failed or skipped.", examples=["sent"])
    attempts: int = Field(description="Send attempts made.", examples=[1])
    last_error: str = Field(description="Error class and status of the last failure.", examples=[""])
    sent_at: datetime | None = Field(description="When the step was sent.", examples=["2026-09-13T12:03:00Z"])


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Notification id.", examples=[7])
    recipient_role: str = Field(description="Who should act.", examples=["sales"])
    severity: str = Field(description="low, medium, high or critical.", examples=["high"])
    subject_ref: str = Field(description="What it is about.", examples=["lead:42"])
    title: str = Field(description="One-line headline.", examples=["Lead waits for reply"])
    body: str = Field(description="Plain-text details.", examples=["No reply for 2 days."])
    count: int = Field(description="How many times it was raised inside the dedup window.", examples=[1])
    read_at: datetime | None = Field(description="When it was read; null when unread.", examples=[None])
    created_at: datetime = Field(description="When it was first raised.", examples=["2026-09-13T12:00:00Z"])


class NotificationDetailResponse(NotificationResponse):
    deliveries: list[DeliveryResponse] = Field(description="Delivery steps so far.", examples=[[]])


class NotificationListResponse(BaseModel):
    count: int = Field(description="Total matching notifications.", examples=[1])
    next: str | None = Field(description="Next page URL.", examples=[None])
    previous: str | None = Field(description="Previous page URL.", examples=[None])
    results: list[NotificationResponse] = Field(description="Newest first.", examples=[[]])


class UnreadCountResponse(BaseModel):
    unread: int = Field(description="Unread notifications in the channel.", examples=[3])


class UpdatedResponse(BaseModel):
    updated: int = Field(description="Notifications marked read.", examples=[3])


class EscalationRunResponse(BaseModel):
    created: int = Field(description="Deliveries created by this run.", examples=[2])
