---
title: Concept
description: What a notification is, dedup, the delivery ladder (in-app, email, Google Chat), escalation rules and the live-send gate.
---

django-notifications answers one question for every other module: "a human must look at this — make sure
somebody does." A module calls `notify()`; the notification shows up in the CMS bar at once, and when nobody reads
it in time it climbs a ladder of louder channels — email, then Google Chat — each step exactly once.

## The model

| Model | Holds | Written by |
|---|---|---|
| `Channel` | `idx` (validated), label, languages — the sales channel the notification belongs to | the operator (admin, fixtures) |
| `Notification` | `recipient_role`, `severity`, `subject_ref`, `title`, `body`, `dedup_key`, `count`, `read_at` | `notify_service.notify` only |
| `Delivery` | one step per `(notification, kind)` — `status`, `attempts`, `last_error`, `sent_at` | `notify()` (in-app), `escalation_service` (creates), `delivery_service` (status) |
| `DeliveryChannelConfig` | per `(channel, kind)`: email `{"recipients": [...]}`, google_chat `{"webhook_url": "..."}`, `is_active` | the operator |
| `EscalationRule` | per `(channel, severity, to_kind)`: `after_minutes` | the operator |

Unread means `read_at IS NULL`. Nothing is ever deleted by the module.

## notify()

```python
notify(*, channel_idx, recipient_role, severity, subject_ref, title, body="", dedup_window_s=60) -> Notification
```

- `severity` ∈ `low` · `medium` · `high` · `critical` — an unknown value raises `ValueError`; an unknown channel
  raises `Channel.DoesNotExist`. The caller decides what to do with either.
- Inside one transaction the channel row is locked (`select_for_update`), which serialises concurrent calls: a first
  occurrence cannot be inserted twice by two workers.
- **Dedup (N-04).** `dedup_key = sha256(subject_ref|title)`. An **unread** notification with that key created
  within the last `dedup_window_s` seconds gets `count + 1` and is returned; no new row, no new delivery. A read one,
  a different title, or one older than the window starts a new notification. The window is measured from the
  first occurrence's `created_at`, not slid by each repeat.
- A new notification gets its `in_app` delivery written `sent` immediately — in-app is not a send, it is the row
  the CMS bar reads (N-01).

`notify()` enqueues nothing. Email and chat are reached only through escalation.

## Escalation

`run_escalation(now=None, channel=None)` — the beat task `django_notifications.escalate` calls it every minute.

For every `EscalationRule` it selects notifications of **exactly** that severity, unread, created at least
`after_minutes` before `now`, that have no delivery of `to_kind` yet — creates a `pending` `Delivery` and enqueues
`deliver` after commit. The unique `(notification, kind)` constraint plus `get_or_create` make a repeated or
concurrent run create nothing twice (N-02). Reading the notification stops every step that has not fired yet.

A typical ladder, as seeded in zeno: `high` → email after 1 min, `high` → Google Chat after 2 min. Rules are
independent — the chat step does not wait for the email step to succeed.

The same run re-enqueues `pending` deliveries untouched for `NOTIFICATIONS_DELIVERY_STALE_MINUTES` (30): an enqueue
lost between commit and broker gets a second chance instead of waiting forever.

## Delivery

`delivery_service.deliver(delivery_id, final_try=True)` is the only writer of `Delivery.status` after creation.

1. **Claim.** One `UPDATE … WHERE status='pending'` sets `sending` and `attempts + 1`. A worker that loses the claim
   (a redelivered `acks_late` task, a concurrent re-enqueue) sends nothing — at most once per claim.
2. **Target.** The active `DeliveryChannelConfig` for the kind. No config, no recipients or a blank webhook URL →
   `skipped` with a warning (N-05).
3. **Backend.** `email` → `django_email.EmailDomain(channel_idx)` (the channel's SMTP connection), plain text, the
   title as subject. `google_chat` → `entirius_googlechat.GoogleChatWebhook(url).send_text("[severity] title\nbody")`.
   A package that is not installed → `skipped`, never an `ImportError`.
4. **Live gate.** Before a real send: `ENVIRONMENT == "production"`, or `NOTIFICATIONS_ALLOW_LIVE_SENDS = True`.
   Otherwise `skipped` with `live sends disabled outside production`.
5. **Outcome.** `sent` with `sent_at`; or `failed` with `last_error` = error class + status.

| Failure | Who retries | End state |
|---|---|---|
| `SMTPException` / `OSError` | Celery autoretry, backoff, 3 retries; the row goes back to `pending` before each | `sent`, or `failed` on the final try |
| Google Chat 5xx / transport error | the chat client: 3 attempts, 1 s and 2 s apart | `failed` (`GoogleChatError (status=…)`, N-03) |
| Google Chat 4xx | nobody | `failed` |
| `EmailDomain` construction | nobody | `failed` (`email backend setup failed: <class>`) |
| anything else | nobody | `failed` |

A failed step never touches the in-app row or `read_at`: the notification stays unread in the bar.

## What it deliberately does not do

- No per-user inbox, no web push, no digest — the CMS bar is per channel and role.
- No automatic re-send of a row stuck in `sending` (a worker killed mid-send): at-most-once beats a double page.
- No escalation back to in-app, and no severity inheritance (`critical` does not match a `high` rule).
