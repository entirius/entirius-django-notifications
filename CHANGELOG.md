# Changelog

## 0.1.0 (unreleased)

First release. The notification layer of the leads platform: every module asks a human for attention through one
call, and nothing important waits unseen.

- **`notify()`** — the single entry point (`services/notify_service.py`): an unread in-app notification per
  channel and recipient role, with its `in_app` delivery written at once (N-01). An unread repeat of the same
  `subject_ref` + `title` inside `NOTIFICATIONS_DEDUP_WINDOW_S` (60 s) increments `count` instead of creating a row
  (N-04); concurrent callers are serialised on the channel row.
- **Escalation** — `EscalationRule(severity, after_minutes, to_kind)` per channel; the beat task
  `django_notifications.escalate` creates one `Delivery` per due step, email then Google Chat, each exactly once
  per notification (N-02). Reading a notification stops the ladder. Lost enqueues are re-enqueued after
  `NOTIFICATIONS_DELIVERY_STALE_MINUTES` (30).
- **Delivery** — atomic claim (`pending` → `sending`), so a redelivered task never sends twice. Email through
  `django_email` on the channel's SMTP connection (Celery retries transient SMTP/socket errors, 3×); Google Chat
  through `entirius-py-googlechat` (the client retries 5xx, then `failed`, in-app untouched — N-03). A missing
  config, blank webhook URL (N-05) or absent package ends `skipped` with a warning, never an exception.
- **Live-send gate** — email and chat leave only when `ENVIRONMENT == "production"` or
  `NOTIFICATIONS_ALLOW_LIVE_SENDS` is true; otherwise `skipped`.
- **Admin API v2** under `api/notifications/v2/admin/<channel_idx>/` (JWT, staff): list, unread count, detail with
  deliveries, mark read, read all; development-only `test/notify/` and `test/run-escalation/` for BDD.
- **Django admin** for channels, delivery configs (config masked, webhook URL write-only), escalation rules and
  read-only notifications. The webhook URL never reaches a log, `last_error` or the API.
- Docs: `docs/` (`api.md`, `concept.md`, `install.md`, `operations.md`, `testing.md`, `gotchas.md`,
  `openapi.yaml`, `erd-config.yaml`); `AGENTS.md` with the covered edge-case IDs N-01…N-05.
- **Fix (item 8): removed the dead `NOTIFICATIONS_ESCALATION_INTERVAL_S` setting.** It was never read —
  the beat schedule (`CELERY_BEAT_SCHEDULE`) is host-owned and its `schedule` value was hardcoded in
  `docs/install.md`, not sourced from this setting. Removed from `settings.py` and the settings table.
