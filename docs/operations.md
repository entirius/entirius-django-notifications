---
title: Operations
description: Day 2 — Celery tasks, reading delivery states, stuck and failed steps, the live gate per environment, secrets.
---

Install-time facts — prerequisites, the settings table, wiring, bootstrap order — are in `install.md`.
The module has no management commands; the Django admin and the delivery rows are the operator's tools.

## Celery tasks

Both on `NOTIFICATIONS_QUEUE_DEFAULT` (`notifications_default`), `acks_late=True`.

| Task | Trigger | Does |
|---|---|---|
| `django_notifications.escalate` | beat, every 60 s | `run_escalation()`: creates due deliveries, enqueues `deliver` after commit, re-enqueues stale `pending` rows; returns how many were created |
| `django_notifications.deliver(delivery_id)` | enqueued by escalation | claims and sends one step; autoretries `SMTPException` / `OSError` with backoff, 3 retries; returns the final status |

The worker has no autoreload — restart it after a change to `tasks/` or `services/`.

## Reading a delivery

Django admin → Notifications → a notification: the read-only deliveries inline. Over the API:
`GET notifications/<id>/`.

| `status` | Means | Action |
|---|---|---|
| `pending` | created, not yet claimed | worker down or queue not consumed; the next escalation run after 30 min re-enqueues it |
| `sending` | claimed, the send did not finish | the worker died mid-send — **not re-sent automatically**; see below |
| `sent` | the backend accepted it | — |
| `skipped` | nothing to send to, package absent, or the live gate closed — `last_error` names which | fix the config or the environment; a skipped step never re-runs |
| `failed` | the backend refused after retries — `last_error` is class + status | fix the target; the step never re-runs |

`attempts` counts claims, a skip included (a skipped step shows 1).

## Re-running a step

Every step fires once per notification by design. To force a retry after fixing the target, in a shell:

```python
Delivery.objects.filter(pk=<id>, status__in=["sending", "failed", "skipped"]).update(status="pending")
deliver.delay(<id>)          # from django_notifications.tasks import deliver
```

Only do this for `sending` once you know the previous attempt did not reach the recipient.

## Live gate per environment

| Environment | Email / chat |
|---|---|
| `production` | sent |
| anything else, `NOTIFICATIONS_ALLOW_LIVE_SENDS = False` (default) | `skipped` — `live sends disabled outside production` |
| anything else, `NOTIFICATIONS_ALLOW_LIVE_SENDS = True` | sent — only where every sink is a sandbox |

The gate is checked after the target and package checks, so a missing config still reads as a missing config.
In-app notifications are unaffected in every environment.

## Secrets

- The Google Chat webhook URL carries `key` and `token`. It is never logged, never in `last_error`, never
  returned by the API; the admin shows `config` masked (`webhook_url: set`). Rotate a leaked URL in Google Chat and
  paste the new one into the write-only field.
- Error texts are reduced to the exception class and status on purpose — backend messages may embed hosts or URLs.

## Monitoring recipients

A channel that must page somebody needs, per severity it cares about: an active email config with recipients, an
active google_chat config with a webhook URL, and an `EscalationRule` for each `to_kind`. Check it by raising one
notification (`test/notify/` in development, `notify()` in a shell elsewhere), leaving it unread and watching both
steps turn `sent`.
