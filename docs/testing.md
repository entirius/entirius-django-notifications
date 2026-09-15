---
title: Test suite map
description: Which test file covers what, and which edge-case IDs.
---

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
