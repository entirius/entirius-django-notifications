# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
import factory

from django_notifications.enums import DeliveryKind, Severity
from django_notifications.models import Channel, DeliveryChannelConfig, EscalationRule


class ChannelFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Channel
        django_get_or_create = ("idx",)

    idx = "default-europe"
    label = "Default Europe"


class DeliveryChannelConfigFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DeliveryChannelConfig

    channel = factory.SubFactory(ChannelFactory)
    kind = DeliveryKind.EMAIL
    config = factory.LazyFunction(lambda: {"recipients": ["sandbox@greenmail.test"]})


class EscalationRuleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EscalationRule

    channel = factory.SubFactory(ChannelFactory)
    severity = Severity.HIGH
    after_minutes = 1
    to_kind = DeliveryKind.EMAIL
