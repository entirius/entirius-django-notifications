# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
from celery import shared_task

from django_notifications.models import Delivery
from django_notifications.services import delivery_service
from django_notifications.settings import QUEUE_DEFAULT


# No autoretry: retries live in entirius-py-googlechat and the SMTP backend, so a delivery ends failed
# deterministically after them instead of being re-sent by Celery.
@shared_task(name="django_notifications.deliver", queue=QUEUE_DEFAULT, acks_late=True, autoretry_for=())
def deliver(delivery_id: int) -> str:
    delivery = Delivery.objects.select_related("notification__channel").get(pk=delivery_id)
    return delivery_service.deliver(delivery).status
