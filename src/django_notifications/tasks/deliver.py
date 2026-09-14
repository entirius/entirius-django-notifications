# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
from celery import shared_task

from django_notifications.services import delivery_service
from django_notifications.settings import QUEUE_DEFAULT


# Celery retries transient SMTP/socket errors (django_email has no retry loop); the chat client retries on its own
# and raises GoogleChatError, which is not retried here. Before each retry the service puts the row back to
# `pending`, so the re-run claims it again; the final try records `failed`.
@shared_task(
    bind=True,
    name="django_notifications.deliver",
    queue=QUEUE_DEFAULT,
    acks_late=True,
    autoretry_for=delivery_service.RETRYABLE_ERRORS,
    retry_backoff=True,
    max_retries=3,
)
def deliver(self, delivery_id: int) -> str:
    final_try = self.request.retries >= self.max_retries
    return delivery_service.deliver(delivery_id, final_try=final_try).status
