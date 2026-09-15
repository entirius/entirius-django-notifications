# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
import pytest
from celery import current_app
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from django_notifications.enums import DeliveryKind
from django_notifications.services.notify_service import notify
from tests.factories import ChannelFactory, DeliveryChannelConfigFactory, EscalationRuleFactory

CHANNEL_IDX = "default-europe"
WEBHOOK_URL = "https://chat.googleapis.com/v1/spaces/AAA/messages?key=SECRETKEY&token=SECRETTOKEN"


@pytest.fixture
def channel(db):
    return ChannelFactory()


@pytest.fixture
def escalation_setup(channel):
    """The emporium fixture shape: email + chat configs, high → email at 1 min, high → chat at 2 min."""
    DeliveryChannelConfigFactory(channel=channel)
    chat = DeliveryChannelConfigFactory(channel=channel, kind=DeliveryKind.GOOGLE_CHAT, config={"webhook_url": ""})
    EscalationRuleFactory(channel=channel, after_minutes=1, to_kind=DeliveryKind.EMAIL)
    EscalationRuleFactory(channel=channel, after_minutes=2, to_kind=DeliveryKind.GOOGLE_CHAT)
    return chat


@pytest.fixture
def raise_high(channel):
    def _raise(subject_ref: str = "lead:42", title: str = "Lead waits", role: str = "sales"):
        return notify(
            channel_idx=CHANNEL_IDX, recipient_role=role, severity="high", subject_ref=subject_ref, title=title
        )

    return _raise


@pytest.fixture
def eager_celery():
    previous = current_app.conf.task_always_eager
    current_app.conf.task_always_eager = True
    yield
    current_app.conf.task_always_eager = previous


def _client_for(**flags) -> APIClient:
    user = get_user_model().objects.create_user(username=f"u{len(flags)}{sorted(flags)}", **flags)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.fixture
def admin_api(db) -> APIClient:
    return _client_for(is_staff=True)


@pytest.fixture
def customer_api(db) -> APIClient:
    return _client_for()


def api_url(path: str) -> str:
    return f"/api/notifications/v2/admin/{CHANNEL_IDX}/{path}"
