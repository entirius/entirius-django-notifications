# AGENTS.md

entirius-django-notifications — "a human must look at this": in-app notifications for the CMS bar, escalated to
email and Google Chat when nobody reads them. App label `django_notifications`, table prefix `django_notifications_`.

## Quick Reference

- Python ≥ 3.11, Django ≥ 4.2, PostgreSQL, Celery, `uv`, ruff, hatchling, MPL-2.0.
- Extras: `email` (`entirius-django-email`), `googlechat` (`entirius-py-googlechat`) — soft; absent → step `skipped`.
- Read first: `docs/install.md` (host) · `docs/api.md` (caller) · `docs/concept.md` (why) ·
  `docs/gotchas.md` (before editing). This file is the map; it explains nothing twice.

## Commands

| Command | Meaning |
|---|---|
| `make install` | `uv sync --all-extras` |
| `make test` | pytest — Postgres only, see Testing |
| `make check` / `fix` | ruff lint + format (+ canonical `.gitleaks.toml` guard) |
| in zeno: `make module-test MODULE=entirius-django-notifications` | the same suite inside the service container |

## Conventions

- English only; MPL-2.0 header on every `.py` (`insert-license`); no Claude attribution trailers in commits or PRs.
- Layered: `models/` · `services/` · `schemas/` · `api/admin/` · `tasks/`. No logic in models or views.
- Never rename the package, the app label or the table prefix; never edit a released migration.
- Git flow: `develop` + `master`, PRs. Do not commit by default — the operator decides.

## Map

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

## Where things live

| Question | Answer |
|---|---|
| A setting's name, default, meaning | `settings.py`; the table in `docs/install.md` |
| Host wiring: apps, URLs, beat entry, queue | `docs/install.md` |
| Request / response shape, auth, errors | `docs/api.md`; `schemas/`; `docs/openapi.yaml` (static export) |
| Dedup, the ladder, retries, the live gate — why | `docs/concept.md` |
| Delivery states, re-running a step, secrets | `docs/operations.md` |
| Which test file covers what | `docs/testing.md` |
| What changed and why | `CHANGELOG.md` |

## Testing

- Postgres only (`tests/settings.py`): `DATABASE_URL` wins (zeno container), else
  `postgres:postgres@localhost:5432/test_notifications`. Migrations run in tests.
- The `test` extra pulls in both soft dependencies and `respx`: `uv sync --extra test` suffices.
- `tests/settings.py` sets `ENVIRONMENT = "development"` and `NOTIFICATIONS_ALLOW_LIVE_SENDS = True` — every sink is
  locmem or monkeypatched; the live gate has its own tests.

## Testing end-to-end

- Edge cases covered (the leads-platform edge-case IDs; each ID returns in the test name):

  | ID | Unit (`tests/`) | BDD / e2e (emporium) |
  |---|---|---|
  | N-01 in-app, unread count, mark read | `test_notify_service`, `test_admin_api` | `features/notifications/notifications.feature`; `e2e/cms/test_leads_funnel.py::test_N01_high_notification_in_bar` |
  | N-02 escalation email then chat, each once | `test_escalation`, `test_delivery` | `features/notifications/notifications.feature` |
  | N-03 Google Chat 5xx → failed, in-app untouched | `test_escalation` | — |
  | N-04 dedup by subject with a counter | `test_notify_service` | — |
  | N-05 chat config without URL → skipped | `test_escalation` | seeded blank webhook, asserted in N-02 BDD |

- BDD: `make mail && make seed && make bdd TAGS=@notifications` — not one-shot (the Background marks all read and
  purges the mailbox). Data: emporium `fixtures/django_notifications.cfg.yaml`. Needs the worker on
  `notifications_default` and `NOTIFICATIONS_ALLOW_LIVE_SENDS = True` (zeno `docker/settings_local.py`).
- The funnel (`@leads-oneshot`, `make e2e-funnel`) exercises notifications through communicator and leads: two
  `high` notifications on a reply, then an escalation mail.
- Guides: portal `guides/leads-end-to-end-testing.md` (modes A/B/C), emporium `docs/e2e-leads-funnel.md`.
- Restart the worker after task changes — Celery has no autoreload.

## Gotchas

`docs/gotchas.md` — the only list. Read it before touching notify, escalation, delivery or the admin.
