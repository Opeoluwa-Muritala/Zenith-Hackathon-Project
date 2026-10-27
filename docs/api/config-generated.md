# Generated configuration reference

Do not edit; run `python backend/scripts/gen_config_docs.py`.

| Setting | Type | Default |
|---|---|---|
| `database_url` | `<class 'str'>` | `postgresql+asyncpg://localhost/cashlens` |
| `jwt_secret` | `<class 'str'>` | `` |
| `environment` | `<class 'str'>` | `development` |
| `redis_url` | `<class 'str'>` | `` |
| `cors_origins` | `<class 'str'>` | `http://localhost:3000` |
| `public_base_url` | `<class 'str'>` | `http://localhost:8000` |
| `api_docs_enabled` | `<class 'bool'>` | `False` |
| `otp_secret` | `<class 'str'>` | `` |
| `otp_sender` | `<class 'str'>` | `disabled` |
| `otp_dev_inbox_enabled` | `<class 'bool'>` | `False` |
| `demo_mode` | `<class 'bool'>` | `False` |
| `demo_otp_inbox_password` | `<class 'str'>` | `` |
| `demo_identifiers` | `<class 'str'>` | `` |
| `otp_http_url` | `<class 'str'>` | `` |
| `otp_http_key` | `<class 'str'>` | `` |
| `otp_sender_id` | `<class 'str'>` | `` |
| `otp_expiry_seconds` | `<class 'int'>` | `300` |
| `otp_max_attempts` | `<class 'int'>` | `5` |
| `otp_resend_cooldown_seconds` | `<class 'int'>` | `60` |
| `otp_lockout_threshold` | `<class 'int'>` | `5` |
| `otp_lockout_base_seconds` | `<class 'int'>` | `60` |
| `balance_stale_minutes` | `<class 'int'>` | `45` |
| `account_refresh_cooldown_seconds` | `<class 'int'>` | `3600` |
| `mono_refresh_monthly_limit` | `<class 'int'>` | `2` |
| `fx_provider_name` | `<class 'str'>` | `` |
| `fx_provider_url` | `<class 'str'>` | `` |
| `fx_provider_key` | `<class 'str'>` | `` |
| `fx_ttl_hours` | `<class 'int'>` | `6` |
| `access_minutes` | `<class 'int'>` | `15` |
| `refresh_days` | `<class 'int'>` | `30` |
| `jwt_issuer` | `<class 'str'>` | `cashlens-api` |
| `jwt_audience` | `<class 'str'>` | `cashlens-mobile` |
| `bvn_pepper` | `<class 'str'>` | `` |
| `aggregator_provider` | `<class 'str'>` | `mock` |
| `mono_base_url` | `<class 'str'>` | `https://api.withmono.com` |
| `mono_secret_key` | `<class 'str'>` | `` |
| `mono_lookup_secret_key` | `<class 'str'>` | `` |
| `mono_public_key` | `<class 'str'>` | `` |
| `webhook_secure_key` | `<class 'str'>` | `` |
| `mono_redirect_url` | `<class 'str'>` | `cashlens://mono/callback` |
| `mono_account_match_enabled` | `<class 'bool'>` | `False` |
| `ai_enabled_global` | `<class 'bool'>` | `False` |
| `ai_provider` | `<class 'str'>` | `groq` |
| `groq_key` | `<class 'str'>` | `` |
| `groq_base_url` | `<class 'str'>` | `https://api.groq.com/openai/v1` |
| `ai_explain_model` | `<class 'str'>` | `openai/gpt-oss-20b` |
| `ai_chat_model` | `<class 'str'>` | `openai/gpt-oss-120b` |
| `ai_max_tokens_explain` | `<class 'int'>` | `240` |
| `ai_max_tokens_chat` | `<class 'int'>` | `700` |
| `ai_daily_token_budget_per_user` | `<class 'int'>` | `12000` |
| `ai_global_daily_token_budget` | `<class 'int'>` | `250000` |
| `ai_request_timeout_s` | `<class 'float'>` | `20.0` |
| `ai_chat_requests_per_minute` | `<class 'int'>` | `10` |
| `assistant_retention_days` | `<class 'int'>` | `30` |
| `field_encryption_key` | `<class 'str'>` | `` |
| `field_encryption_key_id` | `<class 'str'>` | `primary` |
| `field_encryption_previous_keys` | `<class 'str'>` | `{}` |
