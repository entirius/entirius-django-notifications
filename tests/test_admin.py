# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
import pytest

from django_notifications.enums import DeliveryKind
from tests.conftest import WEBHOOK_URL
from tests.factories import DeliveryChannelConfigFactory

NEW_URL = "https://chat.googleapis.com/v1/spaces/BBB/messages?key=NEWKEY&token=NEWTOKEN"


@pytest.fixture
def chat_config(channel):
    return DeliveryChannelConfigFactory(
        channel=channel, kind=DeliveryKind.GOOGLE_CHAT, config={"webhook_url": WEBHOOK_URL}
    )


@pytest.fixture
def change_url(admin_client, chat_config):
    return f"/admin/django_notifications/deliverychannelconfig/{chat_config.pk}/change/"


def _post(admin_client, change_url, chat_config, webhook_url: str):
    data = {"channel": chat_config.channel_id, "kind": chat_config.kind, "is_active": "on", "webhook_url": webhook_url}
    assert admin_client.post(change_url, data).status_code == 302
    chat_config.refresh_from_db()


def test_admin_change_form_hides_webhook_url(admin_client, change_url):
    body = admin_client.get(change_url).content.decode()
    assert "SECRET" not in body
    assert "webhook_url: set" in body


def test_admin_blank_webhook_url_keeps_stored_one(admin_client, change_url, chat_config):
    _post(admin_client, change_url, chat_config, "")
    assert chat_config.config == {"webhook_url": WEBHOOK_URL}


def test_admin_webhook_url_replaced_when_given(admin_client, change_url, chat_config):
    _post(admin_client, change_url, chat_config, NEW_URL)
    assert chat_config.config == {"webhook_url": NEW_URL}
    assert "NEWKEY" not in admin_client.get("/admin/admin/logentry/").content.decode()
