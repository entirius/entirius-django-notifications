# Changelog

## 0.1.0 (unreleased)

- Scaffold from the Entirius module template.
- `notify()` with dedup by subject, in-app delivery, escalation rules to email (django_email) and Google Chat
  (entirius-py-googlechat), `deliver` / `escalate` Celery tasks.
- Admin API v2: list, unread count, detail, mark read, read all; development-only test endpoints.
- Django admin for channels, delivery configs (masked), escalation rules and notifications.
