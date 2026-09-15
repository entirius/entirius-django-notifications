# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Admin API v2 — the in-app inbox of a channel: list, unread count, detail, mark read."""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response

from django_notifications.api.admin.views._base import ERROR_RESPONSES, AdminView, parse
from django_notifications.models import Notification
from django_notifications.schemas.requests import NotificationListQuery, ReadAllRequest
from django_notifications.schemas.responses import (
    DeliveryResponse,
    NotificationDetailResponse,
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
    UpdatedResponse,
)
from django_notifications.services import inbox_service

_TAGS = ["Notifications"]


class NotificationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class NotificationListView(AdminView):
    @extend_schema(
        tags=_TAGS,
        operation_id="notifications_list",
        summary="List notifications of the channel",
        description="Newest first, paginated (`page`, `page_size` ≤ 100).",
        parameters=[
            OpenApiParameter("unread", bool, description="Only unread when 1/true."),
            OpenApiParameter("role", str, description="Only this recipient role."),
            OpenApiParameter("page", int, description="Page number."),
        ],
        responses={200: NotificationListResponse, **ERROR_RESPONSES},
    )
    def get(self, request: Request, channel_idx: str) -> Response:
        query = parse(NotificationListQuery, request.query_params.dict())
        qs = inbox_service.list_notifications(self.channel(channel_idx), unread=query.unread, role=query.role)
        paginator = NotificationPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        payload = NotificationListResponse(
            count=paginator.page.paginator.count,
            next=paginator.get_next_link(),
            previous=paginator.get_previous_link(),
            results=[NotificationResponse.model_validate(item) for item in page],
        )
        return Response(payload.model_dump(mode="json"))


class UnreadCountView(AdminView):
    @extend_schema(
        tags=_TAGS,
        summary="Count unread notifications of the channel",
        responses={200: UnreadCountResponse, **ERROR_RESPONSES},
    )
    def get(self, request: Request, channel_idx: str) -> Response:
        unread = inbox_service.unread_count(self.channel(channel_idx))
        return Response(UnreadCountResponse(unread=unread).model_dump())


class _NotificationObjectView(AdminView):
    def notification(self, channel_idx: str, pk: int) -> Notification:
        try:
            return inbox_service.get_notification(self.channel(channel_idx), pk)
        except Notification.DoesNotExist:
            raise NotFound("Notification not found.") from None


class NotificationDetailView(_NotificationObjectView):
    @extend_schema(
        tags=_TAGS,
        summary="Get one notification with its deliveries",
        responses={200: NotificationDetailResponse, **ERROR_RESPONSES},
    )
    def get(self, request: Request, channel_idx: str, pk: int) -> Response:
        notification = self.notification(channel_idx, pk)
        payload = NotificationDetailResponse(
            **NotificationResponse.model_validate(notification).model_dump(),
            deliveries=[DeliveryResponse.model_validate(delivery) for delivery in notification.deliveries.all()],
        )
        return Response(payload.model_dump(mode="json"))


class MarkReadView(_NotificationObjectView):
    @extend_schema(
        tags=_TAGS,
        summary="Mark one notification read",
        description="Idempotent — a read notification keeps its first `read_at`.",
        request=None,
        responses={200: NotificationResponse, **ERROR_RESPONSES},
    )
    def post(self, request: Request, channel_idx: str, pk: int) -> Response:
        notification = inbox_service.mark_read(self.notification(channel_idx, pk))
        return Response(NotificationResponse.model_validate(notification).model_dump(mode="json"))


class ReadAllView(AdminView):
    @extend_schema(
        tags=_TAGS,
        summary="Mark every unread notification of the channel read",
        request=ReadAllRequest,
        responses={200: UpdatedResponse, **ERROR_RESPONSES},
    )
    def post(self, request: Request, channel_idx: str) -> Response:
        body = parse(ReadAllRequest, request.data or {})
        updated = inbox_service.mark_all_read(self.channel(channel_idx), role=body.role)
        return Response(UpdatedResponse(updated=updated).model_dump())
