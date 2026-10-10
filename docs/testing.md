---
title: Test suite map
description: Which test file covers what, and which edge-case IDs.
---

Postgres only (`tests/settings.py`): `DATABASE_URL`, else
`postgresql://postgres:postgres@localhost:5432/test_notifications`. Migrations run in tests. The `test` extra
pulls in both soft dependencies and `respx`: `uv sync --extra test` suffices. `tests/settings.py` sets
`ENVIRONMENT = "development"` and `NOTIFICATIONS_ALLOW_LIVE_SENDS = True` — every sink is locmem or
monkeypatched; the live gate has its own tests.

- `test_notify_service.py` — in-app delivery written `sent` (N-01), dedup: 50 calls → one row with `count` 50, a new
  row after the window, a read row not counted, a different title is new (N-04); unknown channel / severity raise.
- `test_escalation.py` — email then chat, each once, nothing after (N-02); a read notification never escalates; not
  due before `after_minutes`; chat 5xx → three client attempts, `failed`, in-app untouched (N-03); blank webhook →
  `skipped` with a warning (N-05); the webhook URL never in logs or `last_error`; email without config skipped; a
  run scoped to one channel; a stale `pending` delivery re-enqueued.
- `test_delivery.py` — a redelivered task sends once and a lost claim sends nothing (N-02); the live gate closed
  outside production for both kinds, open in production; transient SMTP errors retried, `failed` after the last
  retry; a broken email backend gives a readable `last_error`.
- `test_admin_api.py` — unread count, list, mark read idempotent (N-01); detail with deliveries; order and
  pagination; list query count; read-all by role; 401/403 without a staff JWT; 404 for an unknown or foreign
  notification; test endpoints (notify, bad severity, run-escalation scoped to its channel, 404 outside development).
- `test_admin.py` — the webhook URL is write-only in the admin change form; blank keeps it, a value replaces it.
- `test_openapi.py` — `spectacular --validate --fail-on-warn`.

Fixtures: `tests/conftest.py` (channel `default-europe`, `raise_high`, JWT clients, `eager_celery`),
`tests/factories.py`. Mail goes to the locmem backend; the chat client's `httpx.post` and `time.sleep` are
monkeypatched — no network.

## Edge-case coverage and end-to-end layers

The leads-platform edge-case IDs; each ID returns in the test name.

| ID | Unit (`tests/`) | BDD / e2e (emporium) |
|---|---|---|
| N-01 in-app, unread count, mark read | `test_notify_service`, `test_admin_api` | `features/notifications/notifications.feature`; `e2e/cms/test_leads_funnel.py::test_N01_high_notification_in_bar` |
| N-02 escalation email then chat, each once | `test_escalation`, `test_delivery` | `features/notifications/notifications.feature` |
| N-03 Google Chat 5xx → failed, in-app untouched | `test_escalation` | — |
| N-04 dedup by subject with a counter | `test_notify_service` | — |
| N-05 chat config without URL → skipped | `test_escalation` | seeded blank webhook, asserted in N-02 BDD |

In the entirius-zeno harness: `make mail && make seed && make bdd TAGS=@notifications` runs the BDD layer — not
one-shot (the Background marks all read and purges the mailbox). Data: emporium
`fixtures/django_notifications.cfg.yaml`. It needs the worker on `notifications_default` and
`NOTIFICATIONS_ALLOW_LIVE_SENDS = True` in the harness settings. `make module-test
MODULE=entirius-django-notifications` runs the module suite inside the service container.

The funnel (`@leads-oneshot`, `make e2e-funnel` in the harness) exercises notifications through communicator and
leads: two `high` notifications on a reply, then an escalation mail. Guides: the Entirius documentation at
https://docs.entirius.com/ and emporium `docs/e2e-leads-funnel.md`.

Restart the worker after task changes — Celery has no autoreload.
