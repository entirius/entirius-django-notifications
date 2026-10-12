# entirius-django-notifications

A Django module for staff notifications in Entirius, the open-source modular ecommerce platform.
It shows in-app notifications in the CMS and escalates them to email and Google Chat when nobody reads them.

[![PyPI](https://img.shields.io/pypi/v/entirius-django-notifications.svg)](https://pypi.org/project/entirius-django-notifications/)
[![Python](https://img.shields.io/pypi/pyversions/entirius-django-notifications.svg)](https://pypi.org/project/entirius-django-notifications/)
[![License: MPL-2.0](https://img.shields.io/badge/license-MPL--2.0-blue.svg)](https://github.com/entirius/entirius-django-notifications/blob/develop/LICENSE)

## What it does

- Creates in-app notifications with a severity and a subject reference through one function, `notify()`.
- Counts repeats of an unread notification inside a dedup window instead of creating new rows.
- Escalates unread notifications along per-channel rules to email and Google Chat, each step once.
- Keeps real sends behind a gate outside production (`NOTIFICATIONS_ALLOW_LIVE_SENDS`).
- Exposes an admin API (JWT, Pydantic schemas, OpenAPI) for the CMS notification bar.

## Installation

```shell
uv add entirius-django-notifications
pip install entirius-django-notifications
```

Optional extras: `entirius-django-notifications[email]` (the email step, through `entirius-django-email`),
`entirius-django-notifications[googlechat]` (the Google Chat step, through `entirius-py-googlechat`).
Without an extra its step is recorded as `skipped`. The email step also needs `django_email` in `INSTALLED_APPS`.

```python
INSTALLED_APPS = [
    # ...
    "django_utils",
    "django_regional",
    "django_notifications",
]

# main/urls.py
urlpatterns.append(path("", include("django_notifications.urls")))
```

The module needs a Celery worker consuming the `notifications_default` queue and the escalation beat entry.
Settings (`NOTIFICATIONS_DEDUP_WINDOW_S`, `NOTIFICATIONS_DELIVERY_STALE_MINUTES`,
`NOTIFICATIONS_QUEUE_DEFAULT`, `NOTIFICATIONS_ALLOW_LIVE_SENDS`) and the bootstrap order: `docs/install.md` —
https://github.com/entirius/entirius-django-notifications/blob/develop/docs/install.md

## Quick start

```python
from django_notifications.services.notify_service import notify

notify(
    channel_idx="my-channel",
    recipient_role="sales",
    severity="high",  # a value of django_notifications.enums.Severity
    subject_ref="leads.Company:42",
    title="A reply needs an answer",
)
```

The notification appears in the CMS bar at once; escalation follows the rules of the channel.

## Requirements

- Python 3.11 or newer, Django 4.2 or newer.
- PostgreSQL.
- A Celery worker consuming the `notifications_default` queue, and Celery beat.
- Entirius packages pulled in: `entirius-django-utils`, `entirius-django-regional`,
  `entirius-py-idx-normalizator`.

## Documentation

- Module docs: https://github.com/entirius/entirius-django-notifications/tree/develop/docs
- Entirius documentation: https://docs.entirius.com/
- Changelog: https://github.com/entirius/entirius-django-notifications/blob/develop/CHANGELOG.md

## Part of Entirius

This module runs inside the Entirius backend service (Volkanos); other modules call `notify()` when a person must act.

- Backend service: https://github.com/entirius/entirius-service-volkanos
- Docker harness: https://github.com/entirius/entirius-zeno
- Sibling modules: https://github.com/entirius/entirius-django-communicator, https://github.com/entirius/entirius-django-leads,
  https://github.com/entirius/entirius-django-email

## Development

```shell
make install     # sync dependencies (uv, incl. extras)
make check       # lint + format check (ruff)
make test        # test suite (pytest; PostgreSQL through DATABASE_URL)
```

Development and agent instructions: https://github.com/entirius/entirius-django-notifications/blob/develop/AGENTS.md

## License

Mozilla Public License 2.0 (MPL-2.0) — see https://github.com/entirius/entirius-django-notifications/blob/develop/LICENSE.
