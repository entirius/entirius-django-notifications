# AGENTS.md

In-app, email and Google Chat notifications with escalation for the Volkanos platform — distribution `entirius-django-notifications`, Django app `django_notifications`.

## Commands

| Command | Meaning |
|---|---|
| `make install` | sync dependencies (uv, incl. extras) |
| `make check` | lint + format-check (ruff) |
| `make fix` | auto-fix lint + format |
| `make test` | test suite (pytest + pytest-django) |

## Conventions

- English only: code, docs, commits, branches, PRs.
- MPL-2.0: every non-trivial source file carries the license header (pre-commit inserts it).
- Toolchain: uv + ruff + hatchling + pytest; all config in `pyproject.toml`; `uv.lock` committed.
- Git flow: `master` (production) + `develop` (integration); changes land via PR; semver tag on `master`.
- Never rename the package / Django app_label / DB table prefix `django_notifications` — it is a schema contract.
- Migrations are part of the public contract — never edit an already released migration.
- Default: do not commit — git is the user's call.

## Commit Message Format

**NEVER add `Co-Authored-By: Claude ...` (or any other Claude/Anthropic attribution) to commit messages.**

This overrides the default Claude Code behavior of appending a `Co-Authored-By` trailer. Commit messages MUST contain only the user's authored content — no robot footer, no "Generated with Claude Code" line, no co-author trailer.

Same rule applies to PR descriptions: no `Generated with [Claude Code]` footer.

## Architecture

Layers one way: API → services → models.

- `models/` — `Channel` (`idx`), `Notification` (unread = `read_at` null, `dedup_key`, `count`),
  `DeliveryChannelConfig` (per channel + kind; email `{"recipients": [...]}`, google_chat `{"webhook_url": "..."}`),
  `EscalationRule` (severity + `after_minutes` → `to_kind`), `Delivery` (unique per notification + kind — each step once).
- `services/notify_service.notify(*, channel_idx, recipient_role, severity, subject_ref, title, body="", dedup_window_s=60)`
  — the only writer of `Notification`. Unread repeat of `sha256(subject_ref|title)` inside the window → `count + 1`,
  no new delivery. Otherwise notification + `in_app` delivery `sent`. Unknown channel → `Channel.DoesNotExist`.
- `services/escalation_service.run_escalation(*, now=None) -> int` — creates due deliveries (`pending`) and enqueues
  `deliver` on commit. Idempotent.
- `services/delivery_service.deliver(delivery)` — the only writer of `Delivery.status`: `sent`, `skipped` (no active
  config / blank target / backend package absent, logs a warning) or `failed` (`last_error` = error class + status).
- `services/inbox_service` — list / unread count / detail / mark read for the admin API.
- `tasks/` — `django_notifications.deliver` (no Celery autoretry: the chat client and SMTP backend retry) and
  `django_notifications.escalate`, both on `notifications_default`.
- Soft dependencies: extras `email` (`django_email.EmailDomain`, per-channel SMTP) and `googlechat`
  (`entirius_googlechat.GoogleChatWebhook`). Missing → delivery `skipped`, never an exception.

## Admin API v2

Prefix `api/notifications/v2/admin/<channel_idx>/`, `JWTAuthentication` + `IsAdminUser`:

| Endpoint | Meaning |
|---|---|
| `GET notifications/?unread=1&role=&page=` | newest first, paginated |
| `GET notifications/unread-count/` | `{"unread": n}` |
| `GET notifications/<id>/` | with deliveries |
| `POST notifications/<id>/read/` | idempotent |
| `POST notifications/read-all/` | optional `{"role": ...}` → `{"updated": n}` |
| `POST test/notify/`, `POST test/run-escalation/` (`{"now": iso \| null}`) | `ENVIRONMENT == "development"` only, else 404 |

## Host integration

- `INSTALLED_APPS += ["django_notifications"]`; `urlpatterns.append(path("", include("django_notifications.urls")))`.
- Worker consumes `notifications_default`.
- Beat: `CELERY_BEAT_SCHEDULE["notifications-escalate"] = {"task": "django_notifications.escalate", "schedule": 60.0}`.
- Settings: `NOTIFICATIONS_DEDUP_WINDOW_S` (60), `NOTIFICATIONS_ESCALATION_INTERVAL_S` (60),
  `NOTIFICATIONS_QUEUE_DEFAULT` (`notifications_default`).

## Gotchas

- The Google Chat webhook URL is a secret: never log it, never return it from the API, never put it in `last_error`.
  The Django admin list shows `config` masked.
- `EmailDomain` needs `set_logger(ProcessLogger(...))` before `send_email` — without it any send error surfaces as
  `AttributeError`.
- Email is plain text: no `extra_headers` (they force `content_subtype="html"`).
- `entirius-py-googlechat` resolves from the sibling clone (`[tool.uv.sources]`) until it is on PyPI.

## Testing end-to-end

- Host: `make check && make test` (Postgres on `localhost:5532`, or `DATABASE_URL`).
- Zeno: `make module-test MODULE=entirius-django-notifications`; BDD: `make mail && make seed && make bdd TAGS=@notifications`
  (emporium `fixtures/django_notifications.cfg.yaml`, `features/notifications/`). Restart the worker after task changes.
