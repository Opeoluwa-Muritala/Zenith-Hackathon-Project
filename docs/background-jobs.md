# Background jobs

Run the scheduler independently from the API with `python -m app.scheduler.worker`.
APScheduler triggers account sync, stale marking, pending-unlink retry, asset reminders,
obligation reminders, overspending alerts, and retention cleanup. Each scheduled minute is
claimed through a unique PostgreSQL `job_runs` row, so duplicate workers do not execute the
same occurrence. Provider retries remain bounded and scheduled sync records calls per user.

Push uses FCM when `FCM_CREDENTIALS_JSON` is configured. Missing or invalid credentials
disable push with one process warning; sync, stale marking, unlink retry, and cleanup remain
active. Delivery logs suppress duplicate device/event sends, retry failures, and invalidate
tokens rejected as unregistered. Webhook processing still uses FastAPI `BackgroundTasks` and
depends on provider redelivery after a process crash.
