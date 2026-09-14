# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
from celery import shared_task

from django_notifications.settings import QUEUE_DEFAULT


@shared_task(name="django_notifications.escalate", queue=QUEUE_DEFAULT, acks_late=True)
def escalate() -> int:
    """Beat entry (host `CELERY_BEAT_SCHEDULE`): `{"task": "django_notifications.escalate", "schedule": 60.0}`."""
    # Lazy: escalation_service imports the deliver task — a top-level import here would be circular.
    from django_notifications.services.escalation_service import run_escalation

    return run_escalation()
