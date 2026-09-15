---
title: Gotchas
description: The one list of rules that bite — read before touching notify, escalation, delivery or the admin.
---

Install-time traps (the queue, the beat entry, OAS 3.1, the live-send flag) live in `install.md`, not here.
Each item below: the rule, then where it is enforced.

## notify and dedup

- **`notify()` is the only writer of `Notification`.** Callers never `Notification.objects.create` — they would skip
  dedup, the channel lock and the in-app row.
- **Dedup counts only unread rows inside the window, measured from the first occurrence** (`_recent_unread`). A
  stream of repeats longer than the window yields one notification per window, not one forever.
- **The channel row lock is what makes a first occurrence unique** — there is no unique constraint on `dedup_key`.
  Removing `select_for_update` brings back duplicate rows under concurrent callers.
- **Settings are snapshotted at import** (`settings.py`), and `dedup_window_s` defaults to that snapshot in the
  function signature: `override_settings(NOTIFICATIONS_DEDUP_WINDOW_S=…)` does nothing; pass `dedup_window_s`.
  `NOTIFICATIONS_ALLOW_LIVE_SENDS` is the exception, read at send time.

## Escalation

- **Each step once, per `(notification, kind)`** — the `Delivery` unique constraint plus `get_or_create`, not the
  rule, is what keeps a repeated or concurrent escalation run from sending twice.
- **Rules match one severity exactly.** A `critical` notification does not ride a `high` ladder — give it rules.
- **Reading stops the ladder, nothing restarts it.** Marking unread again is not an API operation.
- **`escalation_service` imports the `deliver` task; `tasks/escalate.py` imports the service lazily** — a top-level
  import there is circular.

## Delivery

- **The claim is the idempotency key.** `pending` → `sending` in one UPDATE; everything after it assumes the row is
  owned. A new code path that sends must claim first.
- **`sending` is never re-sent automatically** — at-most-once by design; `operations.md` § Re-running a step.
- **Retries have two owners.** Celery retries SMTP/socket errors (django_email has no retry loop) and the service
  puts the row back to `pending` before re-raising; the chat client retries 5xx itself and raises `GoogleChatError`,
  which Celery does not retry. Adding `GoogleChatError` to `RETRYABLE_ERRORS` multiplies posts.
- **The live gate sits after the target and package checks** — reordering it would hide a missing config behind
  `live sends disabled`.
- **`EmailDomain` needs `set_logger(ProcessLogger(...))` before `send_email`** — without it any send error surfaces
  as `AttributeError`.
- **Email is plain text: no `extra_headers`** — django_email switches `content_subtype` to html when they are given.
- **Soft imports are cached per process** (`functools.cache`): installing `django_email` or the chat package needs
  a worker restart before steps stop being `skipped`.

## Secrets and the admin

- **The webhook URL is a secret.** `_error_text` keeps only class + status; log lines name the kind, never the
  target; `DeliveryResponse` has no config field. `test_webhook_url_never_logged_or_stored` guards it.
- **The admin never renders `config`.** The change form shows `masked_config` and a write-only `webhook_url`
  (blank keeps the stored value). Email recipients are therefore not editable in the admin — fixtures or shell.
- **`Notification` is read-only in the admin** — no add, no change; mark read through the API.

## Module boundaries and runtime

- **Consumers import `notify` lazily** and treat the module as optional (communicator does) — never add an import of
  a consumer here.
- **Test endpoints are registered at URL import** (`is_development()` in `api/admin/urls.py`) and guarded again in
  the view — both halves are needed; a cached URLconf would otherwise outlive a settings change.
- **Postgres only** — the suite has no sqlite path.
