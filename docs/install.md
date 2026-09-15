---
title: Install
description: What a host needs before the first notification — prerequisites, extras, the settings table, URLs, the beat entry, bootstrap order.
---

Read this once, top to bottom, before `migrate`. Day-2 commands and failure handling: `operations.md`.

## Prerequisites

| Requirement | Why | Verify |
|---|---|---|
| `django_regional` and `django_notifications` in `INSTALLED_APPS` | `Channel.default_language` / `languages` point at `django_regional.Language` | `manage.py check` |
| PostgreSQL | `select_for_update` serialises `notify()`; the suite has no sqlite path | `manage.py migrate` |
| `rest_framework_simplejwt` | the admin views authenticate with `JWTAuthentication` explicitly | a 401 without a token |
| A Celery worker consuming **`notifications_default`** | `deliver` and `escalate` run there; without it every escalation stays `pending` | `celery -A main worker -Q …,notifications_default` |
| Celery beat with the escalation entry (below) | nothing escalates without it; `notify()` enqueues nothing | a `pending` → `sent` row after `after_minutes` + 1 min |
| `SPECTACULAR_SETTINGS["OAS_VERSION"] = "3.1.0"` | Pydantic documents examples as JSON Schema 2020-12 | `manage.py spectacular --validate` |
| *Optional:* extra `email` + `django_email` in `INSTALLED_APPS` + `EMAIL_SMTP_CONFIGURATION_CHANNELS[<channel_idx>]` | the email step; without the package the step is `skipped` | a `sent` email delivery |
| *Optional:* extra `googlechat` | the Google Chat step; without the package the step is `skipped` | a `sent` google_chat delivery |

```shell
pip install "entirius-django-notifications[email,googlechat]"
```

## Wiring

```python
INSTALLED_APPS += ["django_regional", "django_notifications"]  # + "django_email" for the email step
urlpatterns.append(path("", include("django_notifications.urls")))  # api/notifications/v2/admin/<channel_idx>/
CELERY_BEAT_SCHEDULE["notifications-escalate"] = {"task": "django_notifications.escalate", "schedule": 60.0}
```

## Settings

The only settings table. Every value except `NOTIFICATIONS_ALLOW_LIVE_SENDS` is read **once, at import** of
`django_notifications.settings` — set them in the host settings file, not with `override_settings`.

| Setting | Default | Meaning |
|---|---|---|
| `NOTIFICATIONS_DEDUP_WINDOW_S` | `60` | an unread repeat of `subject_ref` + `title` inside this window is counted, not duplicated |
| `NOTIFICATIONS_QUEUE_DEFAULT` | `notifications_default` | the queue of `deliver` and `escalate` |
| `NOTIFICATIONS_DELIVERY_STALE_MINUTES` | `30` | a `pending` delivery untouched this long is re-enqueued by the next escalation run |
| `NOTIFICATIONS_ALLOW_LIVE_SENDS` | `False` | read at send time: email and chat send outside `ENVIRONMENT == "production"` only when true |
| `ENVIRONMENT` (host) | — | `production` opens the live gate; `development` registers the test endpoints |

**Set `NOTIFICATIONS_ALLOW_LIVE_SENDS` only on a stack whose every sink is a sandbox** (a mail catcher, blank or
test webhooks). A staging database restored from production carries real recipients and real webhook URLs.

## Bootstrap order

```
manage.py migrate                         # five tables
# admin or fixtures, per sales channel:
#   Channel(idx)                          # must match the idx other modules pass to notify()
#   DeliveryChannelConfig(kind=email, config={"recipients": [...]})
#   DeliveryChannelConfig(kind=google_chat, config={"webhook_url": "..."})
#   EscalationRule(severity, after_minutes, to_kind)
# start the worker (notifications_default) and beat
```

The Django admin sets the webhook URL as a write-only field; it does not edit `config` otherwise, so email
recipients come from fixtures or a shell (`gotchas.md`).

A fixture example — the zeno seed: `fixtures/django_notifications.cfg.yaml` in `entirius-test-package-emporium`.
