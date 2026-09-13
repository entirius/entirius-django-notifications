# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Development-only endpoints that let BDD raise a notification and drive the escalation clock.

Registered only when `settings.ENVIRONMENT == "development"` (kept out of other schemas); the view guard
answers 404 as well, so a host that mounts the URLs anyway still exposes nothing.
"""

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response

from django_notifications.api.admin.views._base import ERROR_RESPONSES, AdminView, parse
from django_notifications.schemas.requests import DevNotifyRequest, DevRunEscalationRequest
from django_notifications.schemas.responses import EscalationRunResponse, NotificationResponse
from django_notifications.services.escalation_service import run_escalation
from django_notifications.services.notify_service import notify

_TAGS = ["Notifications (development)"]


def is_development() -> bool:
    return getattr(settings, "ENVIRONMENT", "") == "development"


class _DevelopmentView(AdminView):
    def initial(self, request: Request, *args, **kwargs) -> None:
        if not is_development():
            raise NotFound()
        super().initial(request, *args, **kwargs)


class DevNotifyView(_DevelopmentView):
    @extend_schema(
        tags=_TAGS,
        summary="Raise a notification (development only)",
        request=DevNotifyRequest,
        responses={201: NotificationResponse, **ERROR_RESPONSES},
    )
    def post(self, request: Request, channel_idx: str) -> Response:
        body = parse(DevNotifyRequest, request.data)
        channel = self.channel(channel_idx)
        notification = notify(channel_idx=channel.idx, **body.model_dump(mode="json"))
        return Response(NotificationResponse.model_validate(notification).model_dump(mode="json"), status=201)


class DevRunEscalationView(_DevelopmentView):
    @extend_schema(
        tags=_TAGS,
        summary="Run the escalation now, optionally against a shifted clock (development only)",
        request=DevRunEscalationRequest,
        responses={200: EscalationRunResponse, **ERROR_RESPONSES},
    )
    def post(self, request: Request, channel_idx: str) -> Response:
        body = parse(DevRunEscalationRequest, request.data or {})
        self.channel(channel_idx)
        created = run_escalation(now=body.now)
        return Response(EscalationRunResponse(created=created).model_dump())
