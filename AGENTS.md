# AGENTS.md

entirius-django-notifications (Django app `django_notifications`) — notifications module of Entirius: "a human
must look at this" — in-app notifications for the CMS bar, escalated to email and Google Chat when nobody reads
them. Table prefix `django_notifications_`.

## Commands

| Command | Meaning |
|---|---|
| `make install` | `uv sync --all-extras` |
| `make test` | pytest — PostgreSQL only: `DATABASE_URL`, else the default in `tests/settings.py` (`docs/testing.md`) |
| `make check` / `fix` | ruff lint + format (+ canonical `.gitleaks.toml` guard) |

## Conventions

- English only; MPL-2.0 header on every `.py` (`insert-license`); no Claude attribution trailers in commits or PRs.
- Layered: `models/` · `services/` · `schemas/` · `api/admin/` · `tasks/`. No logic in models or views.
- Never rename the package, the app label or the table prefix; never edit a released migration.
- Access: areas live on the AppConfig (`access_areas`, `access_route_rules`), every admin view carries
  `access_area`; a new admin route without one fails `tests/test_access_ownership.py`.
- Git flow: `develop` + `master`, PRs. Do not commit by default — the operator decides.

## Architecture

Read first: `docs/install.md` (host) · `docs/api.md` (caller) · `docs/concept.md` (why) ·
`docs/gotchas.md` (before editing). Extras `email` and `googlechat` are soft: absent → the step is `skipped`.

```
src/django_notifications/
├── apps.py  enums.py (Severity, DeliveryKind, DeliveryStatus)  settings.py (read at import)  admin.py
├── models/        channel  notification  delivery  delivery_channel_config  escalation_rule
├── schemas/       requests.py  responses.py (no delivery config ever)
├── api/admin/     views/notification_views.py  views/test_views.py (development only)  views/_base.py  urls.py
├── urls.py        api/notifications/v2/admin/<channel_idx>/ → api.admin.urls
├── services/      notify_service (notify — the only writer of Notification)  inbox_service (read side)
│                  escalation_service (run_escalation)  delivery_service (deliver — the only writer of status)
└── tasks/         deliver.py  escalate.py (beat)          queue `notifications_default`
```

Flow: a module calls `notify()` → `Notification` + `in_app` delivery `sent` (or `count + 1` on an unread repeat)
→ beat `escalate` → `run_escalation` creates a `pending` `Delivery` per due `EscalationRule` → `deliver` claims it
→ email (`django_email`) / Google Chat → `sent` · `skipped` · `failed`.

| Topic | Where |
|---|---|
| A setting's name, default, meaning | `settings.py`; the table in `docs/install.md` |
| Host wiring: apps, URLs, beat entry, queue | `docs/install.md` |
| Request / response shape, auth, errors | `docs/api.md`; `schemas/`; `docs/openapi.yaml` (static export) |
| Dedup, the ladder, retries, the live gate — why | `docs/concept.md` |
| Delivery states, re-running a step, secrets | `docs/operations.md` |
| Which test file covers what; BDD and e2e in the entirius-zeno harness | `docs/testing.md` |
| What changed and why | `CHANGELOG.md` |

## Gotchas

- `docs/gotchas.md` is the only list. Read it before touching notify, escalation, delivery or the admin.
