# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from django_notifications.api.admin.views import test_views
from django_notifications.models import Notification
from tests.conftest import api_url


def test_N01_unread_count_and_read_endpoints(admin_api, raise_high):
    notification = raise_high(title="Lead waits for reply")

    assert admin_api.get(api_url("notifications/unread-count/")).json() == {"unread": 1}
    listing = admin_api.get(api_url("notifications/"), {"unread": "1"}).json()
    assert [item["title"] for item in listing["results"]] == ["Lead waits for reply"]

    first = admin_api.post(api_url(f"notifications/{notification.pk}/read/")).json()
    again = admin_api.post(api_url(f"notifications/{notification.pk}/read/")).json()
    assert first["read_at"] is not None
    assert again["read_at"] == first["read_at"]
    assert admin_api.get(api_url("notifications/unread-count/")).json() == {"unread": 0}


def test_detail_includes_deliveries(admin_api, raise_high):
    notification = raise_high()
    body = admin_api.get(api_url(f"notifications/{notification.pk}/")).json()
    assert [(d["kind"], d["status"]) for d in body["deliveries"]] == [("in_app", "sent")]


def test_list_newest_first_and_paginated(admin_api, raise_high):
    for n in range(3):
        raise_high(subject_ref=f"lead:{n}")
    body = admin_api.get(api_url("notifications/"), {"page_size": 2}).json()
    assert body["count"] == 3
    assert [item["subject_ref"] for item in body["results"]] == ["lead:2", "lead:1"]
    assert body["next"] is not None


def test_list_unread_query_count(admin_api, raise_high):
    for n in range(5):
        raise_high(subject_ref=f"lead:{n}")
    with CaptureQueriesContext(connection) as queries:
        response = admin_api.get(api_url("notifications/"), {"unread": "1"})
    assert response.status_code == 200
    assert len(queries) <= 4


def test_read_all_filters_by_role(admin_api, raise_high):
    raise_high(subject_ref="a", role="sales")
    raise_high(subject_ref="b", role="support")

    assert admin_api.post(api_url("notifications/read-all/"), {"role": "sales"}, format="json").json() == {"updated": 1}
    assert Notification.objects.get(recipient_role="support").read_at is None
    assert admin_api.post(api_url("notifications/read-all/"), {}, format="json").json() == {"updated": 1}


def test_api_requires_admin_jwt(client, customer_api, channel):
    assert client.get(api_url("notifications/")).status_code == 401
    assert customer_api.get(api_url("notifications/")).status_code == 403


def test_unknown_channel_or_notification_is_404(admin_api, channel):
    assert admin_api.get("/api/notifications/v2/admin/nope/notifications/unread-count/").status_code == 404
    assert admin_api.get(api_url("notifications/999999/")).status_code == 404


def test_other_channel_notification_is_404(admin_api, raise_high):
    from tests.factories import ChannelFactory

    ChannelFactory(idx="other")
    notification = raise_high()
    assert admin_api.get(f"/api/notifications/v2/admin/other/notifications/{notification.pk}/").status_code == 404


def test_test_notify_endpoint_creates_notification(admin_api, channel):
    body = {"recipient_role": "sales", "severity": "high", "subject_ref": "lead:1", "title": "T", "body": ""}
    response = admin_api.post(api_url("test/notify/"), body, format="json")
    assert response.status_code == 201
    assert Notification.objects.get().title == "T"


def test_test_notify_rejects_bad_severity(admin_api, channel):
    body = {"recipient_role": "sales", "severity": "urgent", "subject_ref": "lead:1", "title": "T"}
    assert admin_api.post(api_url("test/notify/"), body, format="json").status_code == 400


def test_test_run_escalation_endpoint(admin_api, channel):
    response = admin_api.post(api_url("test/run-escalation/"), {"now": None}, format="json")
    assert response.json() == {"created": 0}


def test_test_run_escalation_endpoint_acts_on_its_channel_only(admin_api, channel, monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(test_views, "run_escalation", lambda **kwargs: calls.append(kwargs) or 0)
    admin_api.post(api_url("test/run-escalation/"), {"now": None}, format="json")
    assert calls == [{"now": None, "channel": channel}]


@pytest.mark.parametrize("path", ["test/notify/", "test/run-escalation/"])
def test_test_endpoints_404_outside_development(admin_api, channel, settings, path):
    settings.ENVIRONMENT = "production"
    assert admin_api.post(api_url(path), {}, format="json").status_code == 404
