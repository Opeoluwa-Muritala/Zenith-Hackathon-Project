"""Verified operation descriptions for the backend demonstration journey."""
# ruff: noqa: E501

DEMO_OPERATIONS = {
    ("get", "/health"): (
        "Check API liveness",
        "Public process liveness; does not check Neon or Mono.",
        (),
    ),
    ("post", "/auth/otp/request"): (
        "Request a login OTP",
        "Public email or E.164 phone login. Creates a hashed challenge with configured expiry (five minutes by default) and delivers through the configured sender. Demo identities use the presenter inbox. Identifier and IP limits: five requests per minute, plus the configured resend cooldown. Non-allowlisted demo requests receive the same sent response without creating a code.",
        (422, 429, 503),
    ),
    ("post", "/auth/otp/verify"): (
        "Verify login OTP",
        "Public verification consumes one valid code, creates the local user on first login, and issues access and refresh tokens. The configured attempt limit defaults to five per code; identifier and IP limits are five requests per minute. Submitted codes are never returned.",
        (401, 422, 429),
    ),
    ("post", "/auth/refresh"): (
        "Rotate refresh token",
        "Public token rotation. A valid refresh token is consumed and replaced; replay revokes that token family. The supplied token is never logged.",
        (401, 422),
    ),
    ("post", "/auth/logout"): (
        "Log out a refresh-token family",
        "Revoke the signed-in user's supplied refresh-token family. Existing access JWTs remain valid until expiry; use logout-all to revoke them immediately.",
        (401, 422),
    ),
    ("post", "/auth/logout-all"): (
        "Revoke all user sessions",
        "Revoke all refresh families and reject access tokens issued before the user's revocation timestamp.",
        (401,),
    ),
    ("post", "/onboarding/bvn/start"): (
        "Start BVN bank-account discovery",
        "Validate an 11-digit BVN before calling Mono Lookup. Calls are potentially billable, including failures. Persist a ten-minute session/cooldown and return OTP method hints only. Failed provider attempts retain the cooldown; no transparent HTTP retries. Per-user process limit: five starts per minute, with a ten-minute stored cooldown.",
        (401, 422, 429, 502, 503),
    ),
    ("post", "/onboarding/bvn/send-otp"): (
        "Send Mono consent OTP",
        "Choose an OTP delivery method for the user's ten-minute Lookup session; alternate_phone requires phone_number. Uses a separate Lookup key and makes one provider request. Optional session_id selects an owned session; omitted selects the latest. Five requests per user per minute; Mono calls may be billable.",
        (401, 409, 410, 422, 429, 502, 503),
    ),
    ("post", "/onboarding/bvn/confirm"): (
        "Confirm BVN discovery",
        "Submit the Mono OTP and upsert discovered accounts with encrypted account numbers. Return selectable IDs and last-four digits, without balances or full numbers. Reconfirmation of a completed, unexpired session reuses stored results. Five requests per user per minute; the first provider request may be billable.",
        (401, 409, 410, 422, 429, 502, 503),
    ),
    ("post", "/accounts/discovered/select"): (
        "Select discovered accounts",
        "Mark unticked owned rows skipped. Selected rows remain discovered until Mono confirms linking. No Mono request is made.",
        (401, 404, 422),
    ),
    ("get", "/accounts/skipped"): (
        "List skipped accounts",
        "Return owned skipped rows with IDs and last-four account digits for later hosted linking.",
        (401,),
    ),
    ("post", "/accounts/discovered/{row_id}/link"): (
        "Link a selected discovered account",
        "Resolve bank coverage and initiate hosted Mono Connect with read-only auth scope and a saved reference. Return mono_url. Unmapped institutions are omitted so Mono offers bank selection. Five link requests per user per minute; optional paid account matching is disabled by default.",
        (401, 404, 409, 422, 429, 502, 503),
    ),
    ("post", "/accounts/skipped/{row_id}/link"): (
        "Link a skipped account",
        "Reuse hosted linking without a new BVN lookup; the user still authorises on Mono's page. Five link requests per user per minute. Account matching is disabled by default.",
        (401, 404, 409, 422, 429, 502, 503),
    ),
    ("post", "/accounts/link/initiate"): (
        "Initiate hosted Connect Link",
        "Initiate the existing consent's hosted Mono authorisation and return its URL and reference. No bank credentials pass through this API. Five requests per user per minute; initiation is attempted once.",
        (401, 404, 409, 422, 429, 502, 503),
    ),
    ("get", "/accounts/link/status"): (
        "Read link and data status",
        "Poll the user's reference for link status, Mono data_status and local account_id when created. Reads only the database and does not poll Mono.",
        (401, 404, 422),
    ),
    ("post", "/accounts/link/exchange"): (
        "Exchange a Connect authorisation code",
        "Existing code-exchange alternative: exchange the user's Connect code and save a provider link. The hosted-link webhook flow does not require this endpoint.",
        (401, 404, 409, 422, 502),
    ),
    ("post", "/accounts/link"): (
        "Link a mock fixture account",
        "Local fixture flow available only with the mock provider. Creates a synthetic linked account; does not contact Mono. It is not used by the sandbox demo.",
        (401, 404, 409, 422),
    ),
    ("get", "/accounts"): (
        "List accounts grouped by category",
        "Return accounts with active consent, grouped by category, with counts and totals separated by currency. Include cached freshness and unmapped-institution flags. No provider request.",
        (401,),
    ),
    ("get", "/accounts/{account_id}"): (
        "Read account balance and freshness",
        "Read the user's active account, masked number, available balance, nullable ledger balance, pause flag and data status. Unknown or revoked accounts return 404.",
        (401, 404, 422),
    ),
    ("post", "/accounts/{account_id}/refresh"): (
        "Refresh one account",
        "Request Mono real-time balance data once; processing returns requested with cached data until a webhook arrives. Completed updated balances return synced; no-new-data responses return cached; failures return delayed. Paused accounts reject refresh. Cooldown defaults to one hour and uses Retry-After on 429. Mono always enforces at least five minutes, even with a shorter configured fixture cooldown.",
        (401, 404, 409, 422, 429),
    ),
    ("post", "/accounts/{account_id}/pause"): (
        "Pause account sync",
        "Pause the user's account. Refresh and sync respect this flag; existing records remain available.",
        (401, 404, 422),
    ),
    ("post", "/accounts/{account_id}/resume"): (
        "Resume account sync",
        "Clear the user's pause flag. This request does not immediately fetch financial data.",
        (401, 404, 422),
    ),
    ("post", "/accounts/{account_id}/unlink"): (
        "Unlink and purge one account",
        "Purge linked local transactions, recurring records and obligations, revoke consent, then attempt Mono unlink. Failure retains an encrypted durable retry target processed by the scheduler. User-level derived insights and AI conversations are also purged.",
        (401, 404, 422),
    ),
    ("post", "/sync"): (
        "Sync eligible linked accounts",
        "Fetch transactions for non-paused connected accounts after provider data-readiness checks. Incremental windows overlap by three days and dedupe transactions. Rebuild recurring records, obligations and insights. This is manual recovery, not a scheduler.",
        (401, 409, 422, 502, 503),
    ),
    ("get", "/transactions"): (
        "List filtered transactions",
        "Return active-consent transactions newest first. Filter by account, dates, category, merchant ID and credit/debit. limit is 1–100; offset is 0–10000. Return original narration, decoded label and category source.",
        (401, 422),
    ),
    ("get", "/transactions/recent"): (
        "Read recent cross-account activity",
        "Return newest activity across active accounts; limit defaults to five and is capped at twenty. Account names are currently null; institution and masked number identify the account.",
        (401, 422),
    ),
    ("patch", "/transactions/{transaction_id}/category"): (
        "Reclassify a transaction",
        "Set a category for an owned transaction. apply_to_future also upserts a normalised counterparty rule and updates existing matching transactions; ingestion applies it to future transactions.",
        (401, 404, 422),
    ),
    ("get", "/category-rules"): (
        "List counterparty category rules",
        "Read the user's persistent category overrides. No provider call.",
        (401,),
    ),
    ("delete", "/category-rules/{rule_id}"): (
        "Delete a category rule",
        "Delete an owned future-category rule. Previously categorised transactions are unchanged.",
        (401, 404, 422),
    ),
    ("get", "/analytics/spending"): (
        "Read spending by period and category",
        "Sum debits across active accounts for this_month, last_month or an inclusive custom from/to range of at most 366 days. Return kobo amounts and percentages. Own-account transfers are not excluded; the response says detection is unavailable.",
        (401, 422),
    ),
    ("get", "/assets"): (
        "List manual assets",
        "Read the user's manual assets and write-time valuations. Does not fetch a live FX rate.",
        (401,),
    ),
    ("post", "/assets"): (
        "Create a manual asset",
        "Create an owned NGN/USD asset and calculate its next update reminder. USD uses a cached configured rate or an explicitly supplied rate when no provider is configured. No reminder worker exists.",
        (401, 422, 503),
    ),
    ("put", "/assets/{asset_id}"): (
        "Update a manual asset",
        "Replace the user's asset values, store the write-time FX rate and recalculate reminder timestamps. USD requires a usable configured or supplied rate.",
        (401, 404, 422, 503),
    ),
    ("delete", "/assets/{asset_id}"): (
        "Delete a manual asset",
        "Delete the owned manual asset. No provider request.",
        (401, 404, 422),
    ),
    ("get", "/net-position"): (
        "Read cash and investment position",
        "Return connected non-paused NGN cash plus linked investments and manual assets converted using stored rates. Paused and revoked links are excluded. fx_rate_warning flags USD assets older than the configured rate TTL; it is based on asset update time.",
        (401,),
    ),
    ("get", "/budget"): (
        "Read the effective monthly budget",
        "Return the latest effective monthly limit or null fields when unset.",
        (401,),
    ),
    ("put", "/budget"): (
        "Set a monthly budget",
        "Append a new budget setting effective immediately. Amounts are NGN kobo.",
        (401, 422),
    ),
    ("get", "/budget/velocity"): (
        "Read spending velocity",
        "Compare this month's debits with the effective limit and project month-end spend. Return on_track, warning or exceeded. No overspending push job runs.",
        (401, 404),
    ),
    ("get", "/obligations"): (
        "List upcoming obligations",
        "List the user's non-dismissed obligations by due date, including days_until_due.",
        (401,),
    ),
    ("post", "/obligations"): (
        "Create a manual obligation",
        "Create a manual loan, direct debit or subscription. An optional account_id must belong to the user. Does not send reminders.",
        (401, 404, 422),
    ),
    ("get", "/obligations/{obligation_id}"): (
        "Read an obligation and repayments",
        "Read an owned obligation with matched payment history, amount, cadence and due date.",
        (401, 404, 422),
    ),
    ("patch", "/obligations/{obligation_id}"): (
        "Review or edit an obligation",
        "Update the owned obligation's supported fields; status can confirm or dismiss it. Existing matched payments are retained.",
        (401, 404, 422),
    ),
    ("post", "/consents"): (
        "Create local consent",
        "Create consent with the supplied institution, scope and expiry. Does not itself authorise Mono or link an account.",
        (401, 422),
    ),
    ("get", "/consents"): (
        "List stored consents",
        "Return the user's active and revoked consent records. scope is the stored requested value; it is not verified provider permission information.",
        (401,),
    ),
    ("delete", "/consents/{consent_id}"): (
        "Revoke consent and purge linked accounts",
        "Revoke owned consent, purge linked account data and attempt remote unlink. Failed unlinks remain in the encrypted scheduler queue.",
        (401, 404, 422),
    ),
    ("get", "/privacy/consents"): (
        "List active read-only links",
        "Return each active provider link with institution, link time, data status and the read-only scope requested at link time.",
        (401,),
    ),
    ("post", "/privacy/wipe"): (
        "Revoke all access and wipe user data",
        "Require a fresh six-digit OTP, durably queue remote unlinks, attempt them immediately, delete all user-owned data and sessions, and retain only the minimal wipe audit plus any unfinished encrypted unlink work.",
        (401, 409, 422),
    ),
    ("get", "/plan"): (
        "Read plan and entitlements",
        "Return the free or paid SME flag, live-sync trial state, account cap and feature entitlements. Reading this route does not start the trial.",
        (401,),
    ),
    ("post", "/billing/upgrade-events"): (
        "Record an upgrade tap",
        "Record the authenticated user's paywall surface and desired SME tier for pricing research. This route never starts checkout or charges a payment method.",
        (401, 422),
    ),
    ("post", "/webhooks/mono"): (
        "Receive verified Mono events",
        "Public receiver authenticated by mono-webhook-secret, compared in constant time. Handles account_connected, account_updated and account_unlinked. Saves event-key processing metadata but no raw payload. Completed duplicates are ignored; failed deliveries may retry on redelivery. Returns receipt acknowledgement before background processing.",
        (401, 413, 422),
    ),
}

ERROR_MESSAGES = {
    401: "Authentication is missing, invalid or expired.",
    404: "Owned resource was not found.",
    409: "Resource state prevents this operation.",
    410: "Lookup session expired; restart discovery.",
    413: "Request exceeds the allowed size.",
    422: "Invalid input or date range; sensitive input values are omitted.",
    429: "Rate limit or cooldown reached.",
    500: "Internal server error.",
    502: "Mono could not complete this request.",
    503: "Provider or delivery service is temporarily unavailable.",
}
