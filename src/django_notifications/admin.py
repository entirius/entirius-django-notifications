# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
from django import forms
from django.contrib import admin

from django_notifications.models import Channel, Delivery, DeliveryChannelConfig, EscalationRule, Notification


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ("idx", "label", "default_language")
    search_fields = ("idx", "label")
    filter_horizontal = ("languages",)


class DeliveryChannelConfigForm(forms.ModelForm):
    """`config` never reaches the form: the webhook URL is write-only, blank keeps the stored one."""

    webhook_url = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="Google Chat only. Leave blank to keep the stored URL.",
    )

    class Meta:
        model = DeliveryChannelConfig
        fields = ("channel", "kind", "is_active")

    def save(self, commit: bool = True) -> DeliveryChannelConfig:
        webhook_url = self.cleaned_data.get("webhook_url", "").strip()
        if webhook_url:
            config = self.instance.config if isinstance(self.instance.config, dict) else {}
            self.instance.config = {**config, "webhook_url": webhook_url}
        return super().save(commit=commit)


@admin.register(DeliveryChannelConfig)
class DeliveryChannelConfigAdmin(admin.ModelAdmin):
    form = DeliveryChannelConfigForm
    list_display = ("channel", "kind", "masked_config", "is_active")
    list_filter = ("kind", "is_active")
    fields = ("channel", "kind", "is_active", "webhook_url", "masked_config")
    readonly_fields = ("masked_config",)

    @admin.display(description="config")
    def masked_config(self, obj: DeliveryChannelConfig) -> str:
        """Key names and whether they are set — the webhook URL is a secret."""
        config = obj.config if isinstance(obj.config, dict) else {}
        return ", ".join(f"{key}: {'set' if value else 'empty'}" for key, value in config.items()) or "-"


@admin.register(EscalationRule)
class EscalationRuleAdmin(admin.ModelAdmin):
    list_display = ("channel", "severity", "after_minutes", "to_kind")
    list_filter = ("channel", "severity", "to_kind")


class DeliveryInline(admin.TabularInline):
    model = Delivery
    extra = 0
    can_delete = False
    fields = ("kind", "status", "attempts", "last_error", "sent_at")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "channel", "severity", "recipient_role", "count", "read_at", "created_at")
    list_filter = ("channel", "severity", "recipient_role")
    search_fields = ("title", "subject_ref")
    inlines = [DeliveryInline]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False
