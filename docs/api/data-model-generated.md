# Generated data model reference

Do not edit; run `python backend/scripts/gen_data_model.py`.

## `accounts`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `user_id` | `CHAR(32)` | False | FK |  |
| `institution_id` | `CHAR(32)` | False | FK |  |
| `consent_id` | `CHAR(32)` | False | FK |  |
| `account_number_masked` | `VARCHAR(20)` | False |  |  |
| `type` | `VARCHAR(7)` | False |  |  |
| `currency` | `VARCHAR(3)` | False |  |  |
| `current_balance_minor` | `BIGINT` | False |  |  |
| `last_synced_at` | `DATETIME` | True |  |  |
| `sync_cursor_at` | `DATETIME` | True |  |  |
| `category` | `VARCHAR(19)` | False |  |  |
| `available_balance_minor` | `BIGINT` | True |  |  |
| `ledger_balance_minor` | `BIGINT` | True |  |  |
| `balance_synced_at` | `DATETIME` | True |  |  |
| `sync_status` | `VARCHAR(7)` | False |  |  |
| `sync_paused` | `BOOLEAN` | False |  |  |

## `ai_audit`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `user_id` | `CHAR(32)` | False | FK |  |
| `feature` | `VARCHAR(12)` | False |  |  |
| `model` | `VARCHAR(100)` | False |  |  |
| `prompt_version` | `VARCHAR(40)` | False |  |  |
| `input_tokens` | `INTEGER` | False |  |  |
| `output_tokens` | `INTEGER` | False |  |  |
| `latency_ms` | `INTEGER` | False |  |  |
| `verification_passed` | `BOOLEAN` | False |  |  |
| `fallback_used` | `BOOLEAN` | False |  |  |
| `tools_used` | `JSON` | False |  |  |
| `created_at` | `DATETIME` | False |  |  |

## `assistant_conversations`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `user_id` | `CHAR(32)` | False | FK |  |
| `created_at` | `DATETIME` | False |  |  |
| `expires_at` | `DATETIME` | False |  |  |

## `assistant_messages`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `conversation_id` | `CHAR(32)` | False | FK |  |
| `role` | `VARCHAR(20)` | False |  |  |
| `content_redacted` | `TEXT` | False |  |  |
| `tool_names` | `JSON` | False |  |  |
| `created_at` | `DATETIME` | False |  |  |

## `auth_lockouts`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `identifier_hash` | `VARCHAR(64)` | False | PK | Hash |
| `failed_attempts` | `INTEGER` | False |  |  |
| `locked_until` | `DATETIME` | True |  |  |
| `updated_at` | `DATETIME` | False |  |  |

## `bookkeeper_invites`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `owner_user_id` | `CHAR(32)` | False | FK |  |
| `email` | `VARCHAR(254)` | False |  |  |
| `token_hash` | `VARCHAR(64)` | False |  | Hash |
| `status` | `VARCHAR(20)` | False |  |  |
| `accepted_by_user_id` | `CHAR(32)` | True | FK |  |
| `created_at` | `DATETIME` | False |  |  |
| `expires_at` | `DATETIME` | False |  |  |
| `revoked_at` | `DATETIME` | True |  |  |

## `budgets`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `user_id` | `CHAR(32)` | False | FK |  |
| `monthly_limit_minor` | `BIGINT` | False |  |  |
| `effective_from` | `DATETIME` | False |  |  |

## `bvn_lookup_sessions`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `user_id` | `CHAR(32)` | False | FK |  |
| `mono_session_id` | `VARCHAR(100)` | False |  |  |
| `scope` | `VARCHAR(30)` | False |  |  |
| `expires_at` | `DATETIME` | False |  |  |
| `status` | `VARCHAR(20)` | False |  |  |
| `created_at` | `DATETIME` | False |  |  |

## `category_rules`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `user_id` | `CHAR(32)` | False | FK |  |
| `counterparty_key` | `VARCHAR(160)` | False |  |  |
| `category` | `VARCHAR(40)` | False |  |  |
| `created_at` | `DATETIME` | False |  |  |

## `classification_corrections`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `user_id` | `CHAR(32)` | False | FK |  |
| `counterparty_key` | `VARCHAR(160)` | False |  |  |
| `category` | `VARCHAR(40)` | False |  |  |
| `confirmed` | `BOOLEAN` | False |  |  |
| `created_at` | `DATETIME` | False |  |  |

## `consent_audit`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `consent_id` | `CHAR(32)` | False | FK |  |
| `event` | `VARCHAR(30)` | False |  |  |
| `actor` | `VARCHAR(80)` | False |  |  |
| `at` | `DATETIME` | False |  |  |

## `consents`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `user_id` | `CHAR(32)` | False | FK |  |
| `institution` | `VARCHAR(80)` | False |  |  |
| `scope` | `VARCHAR(100)` | False |  |  |
| `granted_at` | `DATETIME` | False |  |  |
| `expires_at` | `DATETIME` | False |  |  |
| `revoked_at` | `DATETIME` | True |  |  |

## `device_tokens`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `user_id` | `CHAR(32)` | False | FK |  |
| `token_encrypted` | `VARCHAR(512)` | False |  | Encrypted |
| `token_hash` | `VARCHAR(64)` | False |  | Hash |
| `platform` | `VARCHAR(20)` | False |  |  |
| `last_seen_at` | `DATETIME` | False |  |  |
| `is_valid` | `BOOLEAN` | False |  |  |
| `invalidated_at` | `DATETIME` | True |  |  |

## `discovered_accounts`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `user_id` | `CHAR(32)` | False | FK |  |
| `provider` | `VARCHAR(20)` | False |  |  |
| `account_name` | `VARCHAR(160)` | False |  |  |
| `account_designation` | `VARCHAR(40)` | False |  |  |
| `bank_code` | `VARCHAR(10)` | False |  |  |
| `nip_code` | `VARCHAR(10)` | True |  |  |
| `institution_name` | `VARCHAR(120)` | False |  |  |
| `account_type` | `VARCHAR(40)` | False |  |  |
| `account_number_encrypted` | `VARCHAR(512)` | False |  | Encrypted |
| `account_number_last4` | `VARCHAR(4)` | False |  |  |
| `account_number_hash` | `VARCHAR(64)` | False |  | Hash |
| `institution_id` | `VARCHAR(80)` | True |  |  |
| `institution_auth_method` | `VARCHAR(40)` | True |  |  |
| `link_ref` | `VARCHAR(80)` | True |  |  |
| `account_match_requested` | `BOOLEAN` | False |  |  |
| `status` | `VARCHAR(10)` | False |  |  |
| `discovered_at` | `DATETIME` | False |  |  |

## `fx_rates`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `base` | `VARCHAR(3)` | False |  |  |
| `quote` | `VARCHAR(3)` | False |  |  |
| `rate` | `BIGINT` | False |  |  |
| `source` | `VARCHAR(80)` | False |  |  |
| `fetched_at` | `DATETIME` | False |  |  |

## `insight_alerts`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `user_id` | `CHAR(32)` | False | FK |  |
| `insight_id` | `CHAR(32)` | False | FK |  |
| `kind` | `VARCHAR(30)` | False |  |  |
| `severity` | `VARCHAR(20)` | False |  |  |
| `what_changed` | `VARCHAR(200)` | False |  |  |
| `suggested_response` | `VARCHAR(200)` | False |  |  |
| `created_at` | `DATETIME` | False |  |  |
| `read_at` | `DATETIME` | True |  |  |

## `insight_profiles`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `user_id` | `CHAR(32)` | False | PK |  |
| `mode` | `VARCHAR(12)` | False |  |  |
| `updated_at` | `DATETIME` | False |  |  |

## `insights`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `user_id` | `CHAR(32)` | False | FK |  |
| `module` | `VARCHAR(20)` | False |  |  |
| `kind` | `VARCHAR(60)` | False |  |  |
| `severity` | `VARCHAR(20)` | False |  |  |
| `title` | `VARCHAR(160)` | False |  |  |
| `body` | `TEXT` | False |  |  |
| `template_title` | `VARCHAR(160)` | False |  |  |
| `template_body` | `TEXT` | False |  |  |
| `wording_source` | `VARCHAR(12)` | False |  |  |
| `prompt_version` | `VARCHAR(40)` | True |  |  |
| `wording_cache_key` | `VARCHAR(64)` | True |  |  |
| `payload_json` | `JSON` | False |  |  |
| `dedupe_key` | `VARCHAR(160)` | False |  |  |
| `created_at` | `DATETIME` | False |  |  |
| `dismissed_at` | `DATETIME` | True |  |  |

## `institutions`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `name` | `VARCHAR(80)` | False |  |  |
| `code` | `VARCHAR(20)` | False |  |  |
| `logo_url` | `VARCHAR(500)` | True |  |  |
| `savings_rate_bps` | `INTEGER` | False |  |  |

## `job_runs`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `job_name` | `VARCHAR(60)` | False |  |  |
| `scheduled_for` | `DATETIME` | False |  |  |
| `lock_owner` | `VARCHAR(64)` | False |  |  |
| `status` | `VARCHAR(20)` | False |  |  |
| `started_at` | `DATETIME` | False |  |  |
| `completed_at` | `DATETIME` | True |  |  |

## `manual_assets`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `user_id` | `CHAR(32)` | False | FK |  |
| `platform` | `VARCHAR(17)` | False |  |  |
| `category` | `VARCHAR(14)` | False |  |  |
| `currency` | `VARCHAR(3)` | False |  |  |
| `amount_minor` | `BIGINT` | False |  |  |
| `fx_rate_used` | `BIGINT` | True |  |  |
| `update_cadence` | `VARCHAR(8)` | False |  |  |
| `last_updated_at` | `DATETIME` | True |  |  |
| `next_reminder_at` | `DATETIME` | True |  |  |

## `merchants`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `canonical_name` | `VARCHAR(100)` | False |  |  |
| `category_default` | `VARCHAR(40)` | False |  |  |
| `is_subscription_like` | `BOOLEAN` | False |  |  |
| `legitimately_repeating` | `BOOLEAN` | False |  |  |

## `notification_logs`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `user_id` | `CHAR(32)` | False | FK |  |
| `device_id` | `CHAR(32)` | False | FK |  |
| `event_key` | `VARCHAR(160)` | False |  |  |
| `kind` | `VARCHAR(40)` | False |  |  |
| `status` | `VARCHAR(20)` | False |  |  |
| `attempts` | `INTEGER` | False |  |  |
| `last_attempt_at` | `DATETIME` | False |  |  |
| `sent_at` | `DATETIME` | True |  |  |

## `notification_preferences`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `user_id` | `CHAR(32)` | False | PK |  |
| `overspending_alerts` | `BOOLEAN` | False |  |  |
| `loan_repayment_reminders` | `BOOLEAN` | False |  |  |
| `investment_update_prompts` | `BOOLEAN` | False |  |  |

## `obligation_payments`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `obligation_id` | `CHAR(32)` | False | FK |  |
| `transaction_id` | `CHAR(32)` | True | FK |  |
| `paid_at` | `DATETIME` | False |  |  |
| `amount_minor` | `BIGINT` | False |  |  |

## `obligations`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `user_id` | `CHAR(32)` | False | FK |  |
| `account_id` | `CHAR(32)` | True | FK |  |
| `lender_name` | `VARCHAR(120)` | False |  |  |
| `kind` | `VARCHAR(20)` | False |  |  |
| `amount_minor` | `BIGINT` | False |  |  |
| `cadence_days` | `INTEGER` | False |  |  |
| `next_due_date` | `DATE` | False |  |  |
| `confidence_bps` | `INTEGER` | False |  |  |
| `status` | `VARCHAR(20)` | False |  |  |
| `source` | `VARCHAR(20)` | False |  |  |

## `otp_codes`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `identifier` | `VARCHAR(254)` | False |  |  |
| `code_hash` | `VARCHAR(64)` | False |  | Hash |
| `salt` | `VARCHAR(32)` | False |  |  |
| `expires_at` | `DATETIME` | False |  |  |
| `attempts` | `INTEGER` | False |  |  |
| `consumed_at` | `DATETIME` | True |  |  |
| `created_at` | `DATETIME` | False |  |  |

## `provider_call_logs`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `user_id` | `CHAR(32)` | False | FK |  |
| `provider` | `VARCHAR(20)` | False |  |  |
| `operation` | `VARCHAR(60)` | False |  |  |
| `account_id` | `CHAR(32)` | True | FK |  |
| `requested_at` | `DATETIME` | False |  |  |
| `outcome` | `VARCHAR(20)` | False |  |  |

## `provider_links`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `user_id` | `CHAR(32)` | False | FK |  |
| `consent_id` | `CHAR(32)` | False | FK |  |
| `provider` | `VARCHAR(20)` | False |  |  |
| `provider_account_id_encrypted` | `VARCHAR(512)` | True |  | Encrypted |
| `provider_account_id_hash` | `VARCHAR(64)` | True |  | Hash |
| `status` | `VARCHAR(20)` | False |  |  |
| `data_status` | `VARCHAR(30)` | True |  |  |
| `created_at` | `DATETIME` | False |  |  |
| `last_webhook_at` | `DATETIME` | True |  |  |

## `recurring_series`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `user_id` | `CHAR(32)` | False | FK |  |
| `account_id` | `CHAR(32)` | True | FK |  |
| `merchant_id` | `CHAR(32)` | False | FK |  |
| `cadence_days` | `INTEGER` | False |  |  |
| `typical_amount_minor` | `BIGINT` | False |  |  |
| `last_amount_minor` | `BIGINT` | False |  |  |
| `previous_amount_minor` | `BIGINT` | True |  |  |
| `cycles` | `INTEGER` | False |  |  |
| `first_seen_at` | `DATETIME` | False |  |  |
| `last_seen_at` | `DATETIME` | False |  |  |
| `next_expected_at` | `DATETIME` | False |  |  |
| `status` | `VARCHAR(9)` | False |  |  |
| `direction` | `VARCHAR(6)` | False |  |  |

## `refresh_tokens`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `user_id` | `CHAR(32)` | False | FK |  |
| `token_hash` | `VARCHAR(64)` | False |  | Hash |
| `expires_at` | `DATETIME` | False |  |  |
| `used_at` | `DATETIME` | True |  |  |
| `family_id` | `CHAR(32)` | False |  |  |
| `revoked_at` | `DATETIME` | True |  |  |

## `report_share_links`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `user_id` | `CHAR(32)` | False | FK |  |
| `month` | `DATE` | False |  |  |
| `token_hash` | `VARCHAR(64)` | False |  | Hash |
| `created_at` | `DATETIME` | False |  |  |
| `expires_at` | `DATETIME` | False |  |  |
| `revoked_at` | `DATETIME` | True |  |  |

## `reviewed_global_rules`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `narration_hash` | `VARCHAR(64)` | False |  | Hash |
| `category` | `VARCHAR(40)` | False |  |  |
| `reviewed_at` | `DATETIME` | False |  |  |

## `security_audit_events`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `user_id` | `CHAR(32)` | True | FK |  |
| `event` | `VARCHAR(50)` | False |  |  |
| `subject_hash` | `VARCHAR(64)` | True |  | Hash |
| `occurred_at` | `DATETIME` | False |  |  |

## `transaction_use_labels`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `transaction_id` | `CHAR(32)` | False | PK |  |
| `user_id` | `CHAR(32)` | False | FK |  |
| `suggested_label` | `VARCHAR(12)` | False |  |  |
| `confidence_bps` | `INTEGER` | False |  |  |
| `confirmed_label` | `VARCHAR(12)` | True |  |  |
| `updated_at` | `DATETIME` | False |  |  |

## `transactions`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `account_id` | `CHAR(32)` | False | FK |  |
| `posted_at` | `DATETIME` | False |  |  |
| `amount_minor` | `BIGINT` | False |  |  |
| `direction` | `VARCHAR(6)` | False |  |  |
| `narration_raw` | `TEXT` | False |  |  |
| `narration_clean` | `VARCHAR(200)` | False |  |  |
| `merchant_id` | `CHAR(32)` | True | FK |  |
| `category` | `VARCHAR(40)` | False |  |  |
| `channel` | `VARCHAR(5)` | False |  |  |
| `balance_after_minor` | `BIGINT` | True |  |  |
| `dedupe_hash` | `VARCHAR(64)` | False |  | Hash |
| `decoded_merchant` | `VARCHAR(100)` | True |  |  |
| `category_source` | `VARCHAR(9)` | False |  |  |
| `source` | `VARCHAR(20)` | False |  |  |
| `parse_confidence_bps` | `INTEGER` | False |  |  |
| `classification_method` | `VARCHAR(20)` | False |  |  |

## `transfer_suggestions`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `user_id` | `CHAR(32)` | False | FK |  |
| `counterparty_key` | `VARCHAR(160)` | False |  |  |
| `kind` | `VARCHAR(20)` | False |  |  |
| `status` | `VARCHAR(20)` | False |  |  |
| `created_at` | `DATETIME` | False |  |  |

## `user_settings`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `user_id` | `CHAR(32)` | False | PK |  |
| `safe_buffer_minor` | `BIGINT` | False |  |  |
| `payday_hint` | `INTEGER` | True |  |  |
| `discretionary_categories` | `JSON` | False |  |  |
| `nominal_tbill_rate_bps` | `INTEGER` | False |  |  |
| `ai_enabled` | `BOOLEAN` | False |  |  |
| `privacy_blur` | `BOOLEAN` | False |  |  |

## `users`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `phone` | `VARCHAR(20)` | True |  |  |
| `email` | `VARCHAR(254)` | True |  |  |
| `bvn_hash` | `VARCHAR(64)` | True |  | Hash |
| `bvn_last4` | `VARCHAR(4)` | True |  |  |
| `created_at` | `DATETIME` | False |  |  |
| `sessions_revoked_at` | `DATETIME` | True |  |  |

## `webhook_events`

| Column | Type | Nullable | Key | Protection |
|---|---|---:|---|---|
| `id` | `CHAR(32)` | False | PK |  |
| `event_key` | `VARCHAR(64)` | False |  |  |
| `event_name` | `VARCHAR(100)` | False |  |  |
| `received_at` | `DATETIME` | False |  |  |
| `processing_status` | `VARCHAR(20)` | False |  |  |
| `processing_started_at` | `DATETIME` | True |  |  |
| `processing_token` | `VARCHAR(36)` | True |  |  |
| `processed_at` | `DATETIME` | True |  |  |
