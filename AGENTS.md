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
- `services/escalation_service.run_escalation(*, now=None, channel=None) -> int` — creates due deliveries (`pending`)
  and enqueues `deliver` on commit; `channel` limits the run to one channel. Also re-enqueues `pending` rows untouched
  for `NOTIFICATIONS_DELIVERY_STALE_MINUTES` (lost enqueue). Idempotent.
- `services/delivery_service.deliver(delivery_id, *, final_try=True)` — the only writer of `Delivery.status`. Starts
  with an atomic claim (`pending` → `sending`, `attempts + 1` in one UPDATE; a lost claim sends nothing, so a
  redelivered task never sends twice), then ends `sent`, `skipped` (no active config / blank target / backend package
  absent / live sends disabled, logs a warning) or `failed` (`last_error` = error class + status, or
  `email backend setup failed: <class>`). `attempts` counts claims, a skip included.
- `services/inbox_service` — list / unread count / detail / mark read for the admin API.
- `tasks/` — `django_notifications.deliver` and `django_notifications.escalate`, both on `notifications_default`.
  `deliver` autoretries `SMTPException`/`OSError` (backoff, 3 retries — `django_email` has no retry loop): the service
  puts the row back to `pending` before re-raising, the retry claims it again, the final try records `failed`.
  The chat client retries on its own (`GoogleChatError` is not retried by Celery).
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
  `NOTIFICATIONS_QUEUE_DEFAULT` (`notifications_default`), `NOTIFICATIONS_DELIVERY_STALE_MINUTES` (30),
  `NOTIFICATIONS_ALLOW_LIVE_SENDS` (False).
- Live gate: email and chat send only when `ENVIRONMENT == "production"` or `NOTIFICATIONS_ALLOW_LIVE_SENDS` is true;
  otherwise the delivery is `skipped` (`live sends disabled outside production`). Set the flag only on a stack whose
  every sink is a sandbox (zeno: GreenMail, blank webhook) — a restored production dump would post for real.

## Gotchas

- The Google Chat webhook URL is a secret: never log it, never return it from the API, never put it in `last_error`.
  The Django admin never renders `config`: the list and change form show it masked, the webhook URL is a write-only
  password field (blank keeps the stored URL). `config` is not editable in the admin (email recipients included).
- A delivery stuck in `sending` (worker killed mid-send) is not re-sent automatically — at-most-once by design.
- `EmailDomain` needs `set_logger(ProcessLogger(...))` before `send_email` — without it any send error surfaces as
  `AttributeError`.
- Email is plain text: no `extra_headers` (they force `content_subtype="html"`).

## Known gaps

- `entirius-py-googlechat` resolves from the sibling clone (`[tool.uv.sources]`) until it is on PyPI — GitHub CI
  (`uv sync --frozen --all-extras`) and any standalone install stay red until FIX-03b swaps it for `>=0.1.0a1`.

## Testing end-to-end

- Host: `make check && make test` (`DATABASE_URL`, else `postgres:postgres@localhost:5432/test_notifications`).
- The `test` extra pulls in both soft dependencies (`email`, `googlechat`) and `respx`: `uv sync --extra test` suffices.
- Zeno: `make module-test MODULE=entirius-django-notifications`; BDD: `make mail && make seed && make bdd TAGS=@notifications`
  (emporium `fixtures/django_notifications.cfg.yaml`, `features/notifications/`). Restart the worker after task changes.
