# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Admin API URL routing — manual `path()` per Volkanos convention."""

from django.urls import path

from django_notifications.api.admin.views.notification_views import (
    MarkReadView,
    NotificationDetailView,
    NotificationListView,
    ReadAllView,
    UnreadCountView,
)
from django_notifications.api.admin.views.test_views import DevNotifyView, DevRunEscalationView, is_development

urlpatterns = [
    path("notifications/", NotificationListView.as_view(), name="admin-notifications-list"),
    path("notifications/unread-count/", UnreadCountView.as_view(), name="admin-notifications-unread-count"),
    path("notifications/read-all/", ReadAllView.as_view(), name="admin-notifications-read-all"),
    path("notifications/<int:pk>/", NotificationDetailView.as_view(), name="admin-notifications-detail"),
    path("notifications/<int:pk>/read/", MarkReadView.as_view(), name="admin-notifications-read"),
]

if is_development():
    urlpatterns += [
        path("test/notify/", DevNotifyView.as_view(), name="admin-notifications-test-notify"),
        path("test/run-escalation/", DevRunEscalationView.as_view(), name="admin-notifications-test-run-escalation"),
    ]
