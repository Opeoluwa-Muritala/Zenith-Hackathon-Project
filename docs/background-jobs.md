# Background jobs

No scheduler or worker is implemented. Account sync, reminders, push notifications, pending-unlink retries, and cleanup jobs are planned gaps. Account unlink and consent revoke now persist `pending_unlink` before attempting Mono unlink, but nothing automatically retries failed attempts. Webhook processing still uses FastAPI `BackgroundTasks`, which is not durable.
