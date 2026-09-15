---
title: Admin API
description: The in-app inbox of a channel — list, unread count, detail, mark read, read all; auth, errors, the development-only endpoints.
---

Five endpoints under `/api/notifications/v2/admin/<channel_idx>/` (the host mounts `django_notifications.urls`),
plus two development-only ones. The API only **reads** notifications and marks them read — raising one is a
Python call (`notify()`, `concept.md`), never an HTTP request in production.

Views are thin (`api/admin/views/notification_views.py`): parse into a Pydantic schema, call
`services.inbox_service`, serialise. No ORM in the view layer. The static spec is `docs/openapi.yaml`.

## Auth

| | |
|---|---|
| Authentication | `JWTAuthentication` — declared on the view, never inherited from the host defaults |
| Permission | `IsAdminUser` (staff) |
| Throttle | none of its own; the host's defaults apply |

`recipient_role` is a label for filtering, not an authorisation boundary: every staff user of the host sees every
role of every channel.

## Endpoints

| Method | Path | Body / query | Response |
|---|---|---|---|
| GET | `notifications/` | `unread` (1/true), `role`, `page`, `page_size` (≤ 100, default 20) | `NotificationListResponse` — `count`, `next`, `previous`, `results`, newest first |
| GET | `notifications/unread-count/` | — | `{"unread": n}` — the whole channel, every role |
| GET | `notifications/<id>/` | — | `NotificationDetailResponse` — a notification plus its `deliveries` |
| POST | `notifications/<id>/read/` | — | `NotificationResponse`; idempotent — a read notification keeps its first `read_at` |
| POST | `notifications/read-all/` | `{"role": str \| null}` (optional) | `{"updated": n}` — unread rows marked in this call |

A notification of another channel answers 404, exactly like a missing one.

## Response

```json
{
  "id": 7,
  "recipient_role": "sales",
  "severity": "high",
  "subject_ref": "lead:42",
  "title": "Lead waits for reply",
  "body": "No reply for 2 days.",
  "count": 1,
  "read_at": null,
  "created_at": "2026-09-13T12:00:00Z",
  "deliveries": [
    {"kind": "in_app", "status": "sent", "attempts": 0, "last_error": "", "sent_at": "2026-09-13T12:00:00Z"},
    {"kind": "email", "status": "sent", "attempts": 1, "last_error": "", "sent_at": "2026-09-13T12:03:00Z"}
  ]
}
```

| Key | Meaning |
|---|---|
| `count` | how many times the same `subject_ref` + `title` was raised while unread inside the dedup window (N-04) |
| `read_at` | null = unread; unread is what escalates |
| `deliveries` | detail only. `in_app` is written `sent` by `notify()` itself (`attempts` 0); `email` / `google_chat` rows appear only when an escalation rule fired |
| `status` | `pending` · `sending` (claimed by a worker) · `sent` · `failed` · `skipped` |
| `last_error` | error class and status only (`GoogleChatError (status=503)`), or the skip reason — never a URL or a recipient |

Delivery targets (`DeliveryChannelConfig.config`, the Google Chat webhook URL) are never serialised.

## Development-only endpoints

Registered only when `settings.ENVIRONMENT == "development"`; each view answers 404 in any other environment even
if the URLs are mounted. They exist so BDD can raise a notification and move the escalation clock. They are left
out of `docs/openapi.yaml`, which describes a non-development host.

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `test/notify/` | `recipient_role`, `severity`, `subject_ref`, `title`, `body` | 201 `NotificationResponse` (a dedup repeat returns the counted row) |
| POST | `test/run-escalation/` | `{"now": iso-8601 \| null}` | `{"created": n}` — deliveries created for this channel only |

## Errors

| Status | Cause |
|---|---|
| 400 | Pydantic validation (`raise_pydantic_as_drf`) — unknown key in a body (`extra="forbid"`), bad severity, over-long role |
| 401 | no / invalid JWT |
| 403 | authenticated but not staff |
| 404 | unknown `channel_idx`, unknown notification, a notification of another channel; test endpoints outside development |

## OpenAPI

Every view is `@extend_schema`-annotated (tag `Notifications`) and generates without warnings under
`OAS_VERSION = "3.1.0"` — `tests/test_openapi.py` runs `spectacular --validate --fail-on-warn`.
