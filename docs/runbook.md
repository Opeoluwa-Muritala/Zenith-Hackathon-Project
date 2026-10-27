# Runbook

| Symptom | Check | Current action/limitation |
|---|---|---|
| Mono webhook absent | Check `WEBHOOK_SECURE_KEY`, public URL, and webhook event tests. | No durable delivery monitor exists. |
| Account processing/delayed | Inspect provider link data_status and webhook_events processing_status. | Data calls need AVAILABLE/PARTIAL and retrieved_data. A completed receipt alone does not prove sync. Redeliver failed events or use manual sync for already ready accounts. |
| Sync failure | Check provider state and safely logged error_type. | Read requests retry bounded transport/429/5xx failures; Lookup and link initiation are attempted once. No automatic worker exists. |
| BVN lookup error | Confirm numeric validation, separate Lookup key and ten-minute session. | Failed starts retain cooldown. Restart expired sessions; review dashboard charges rather than repeatedly initiating lookups. |
| 429 response | Check OTP/account refresh throttle. | Retry after the endpoint’s throttle window. |
| Pending unlink | Check `provider_links.status = pending_unlink` and application logs. | Local account data has been purged; remote unlink is still pending. No automatic retry worker exists. |
| Wipe failure | No complete wipe endpoint exists. | Treat as a planned gap; do not claim deletion. |
| Demo OTP absent | Check demo settings, exact allowlisted identifier, password and worker count. | Request from the app and refresh the protected presenter page. Codes expire or disappear after verification/restart. Use one worker. |
| Neon connection/schema failure | Check deployment secrets without printing connection strings; inspect Alembic revision through an authorised operator query. | Offline tests do not verify Neon. Review migrations on disposable storage before any apply; never reset the populated demo database. |
