# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Module settings — host overrides via Django settings of the same name."""

from django.conf import settings

QUEUE_DEFAULT = getattr(settings, "NOTIFICATIONS_QUEUE_DEFAULT", "notifications_default")

# An unread notification with the same subject_ref + title inside this window is counted, not duplicated.
NOTIFICATIONS_DEDUP_WINDOW_S = getattr(settings, "NOTIFICATIONS_DEDUP_WINDOW_S", 60)

# A `pending` delivery untouched this long lost its enqueue — the escalation run enqueues it again.
NOTIFICATIONS_DELIVERY_STALE_MINUTES = getattr(settings, "NOTIFICATIONS_DELIVERY_STALE_MINUTES", 30)

# `NOTIFICATIONS_ALLOW_LIVE_SENDS` (default False) is read at send time by `delivery_service`: outside
# `ENVIRONMENT == "production"` email and chat deliveries are skipped unless it is true.
