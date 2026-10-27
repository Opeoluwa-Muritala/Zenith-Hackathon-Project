from datetime import UTC, datetime
from uuid import uuid4

from app.models import (
    Account,
    AccountCategory,
    Budget,
    CategoryRule,
    CategorySource,
    DeviceToken,
    DiscoveredAccount,
    DiscoveredAccountStatus,
    FxRate,
    ManualAsset,
    ManualAssetCategory,
    ManualAssetPlatform,
    NotificationPreference,
    SyncStatus,
    Transaction,
    UpdateCadence,
)

NOW = datetime.now(UTC)


def test_account_foundation_fields_use_allowlisted_enums_and_minor_units():
    account = Account(
        category=AccountCategory.digital_bank_wallet,
        available_balance_minor=100,
        ledger_balance_minor=120,
        balance_synced_at=NOW,
        sync_status=SyncStatus.delayed,
        sync_paused=True,
    )
    assert account.category is AccountCategory.digital_bank_wallet
    assert account.available_balance_minor == 100
    assert account.sync_status is SyncStatus.delayed


def test_discovered_account_and_manual_asset_models_cover_selection_and_tracking():
    user_id = uuid4()
    discovered = DiscoveredAccount(
        user_id=user_id,
        provider="mono",
        account_name="Example Customer",
        account_designation="INDIVIDUAL",
        bank_code="057",
        nip_code="000015",
        institution_name="Example Bank",
        account_type="savings",
        account_number_encrypted="encrypted-value",
        account_number_last4="1234",
        account_number_hash="a" * 64,
        status=DiscoveredAccountStatus.discovered,
        discovered_at=NOW,
    )
    asset = ManualAsset(
        user_id=user_id,
        platform=ManualAssetPlatform.risevest,
        category=ManualAssetCategory.us_equities,
        currency="USD",
        amount_minor=12500,
        fx_rate_used=150000,
        update_cadence=UpdateCadence.biweekly,
    )
    assert discovered.status is DiscoveredAccountStatus.discovered
    assert asset.currency == "USD"
    assert asset.amount_minor == 12500


def test_financial_support_models_have_user_scoped_identity_and_defaults():
    user_id = uuid4()
    rule = CategoryRule(
        user_id=user_id, counterparty_key="chowdeck", category="food", created_at=NOW
    )
    budget = Budget(user_id=user_id, monthly_limit_minor=100000, effective_from=NOW)
    device = DeviceToken(user_id=user_id, token_hash="a" * 64, platform="android", last_seen_at=NOW)
    preferences = NotificationPreference(user_id=user_id)
    rate = FxRate(base="USD", quote="NGN", rate=150000, source="reference", fetched_at=NOW)
    assert rule.user_id == budget.user_id == device.user_id == preferences.user_id
    assert rate.base == "USD"
    assert preferences.overspending_alerts is None or preferences.overspending_alerts is True


def test_transaction_classification_fields_are_persistable():
    transaction = Transaction(
        account_id=uuid4(),
        posted_at=NOW,
        amount_minor=100,
        direction="debit",
        narration_raw="NIP/POS/CHOWDECK",
        narration_clean="NIP POS CHOWDECK",
        category="food",
        category_source=CategorySource.user_rule,
        decoded_merchant="Chowdeck",
        channel="POS",
        dedupe_hash="b" * 64,
    )
    assert transaction.decoded_merchant == "Chowdeck"
    assert transaction.category_source is CategorySource.user_rule
