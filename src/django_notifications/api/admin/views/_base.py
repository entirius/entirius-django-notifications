# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Shared wiring of the admin views — auth declared explicitly, never inherited from service defaults."""

from typing import TypeVar

from django_utils.api.v2_errors import raise_pydantic_as_drf
from pydantic import BaseModel, ValidationError
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from django_notifications.models import Channel
from django_notifications.services import inbox_service

SchemaT = TypeVar("SchemaT", bound=BaseModel)

ERROR_RESPONSES = {400: None, 401: None, 403: None, 404: None}


class AdminView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    @staticmethod
    def channel(channel_idx: str) -> Channel:
        try:
            return inbox_service.get_channel(channel_idx)
        except Channel.DoesNotExist:
            raise NotFound("Channel not found.") from None


def parse(schema: type[SchemaT], data: object) -> SchemaT:
    """Validate request data; a Pydantic error becomes the v2 400 shape."""
    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        raise_pydantic_as_drf(exc)
