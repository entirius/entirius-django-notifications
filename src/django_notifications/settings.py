# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Module settings — host overrides via Django settings of the same name."""

from django.conf import settings

QUEUE_DEFAULT = getattr(settings, "NOTIFICATIONS_QUEUE_DEFAULT", "notifications_default")

# An unread notification with the same subject_ref + title inside this window is counted, not duplicated.
NOTIFICATIONS_DEDUP_WINDOW_S = getattr(settings, "NOTIFICATIONS_DEDUP_WINDOW_S", 60)

# How often the host's beat should run `django_notifications.escalate` (documented in AGENTS.md).
NOTIFICATIONS_ESCALATION_INTERVAL_S = getattr(settings, "NOTIFICATIONS_ESCALATION_INTERVAL_S", 60)
