"""Phase 7 RPT requirement coverage."""

from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import pytest
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import main
from app.core.db import get_db
from app.core.security import current_user
from app.models import (
    Account,
    AccountType,
    Base,
    BookkeeperInvite,
    Consent,
    Direction,
    Institution,
    ReportShareLink,
    Transaction,
    TransactionUseLabel,
    User,
)

NOW = datetime(2026, 10, 28, 12, tzinfo=UTC)


def test_RPT_2_RPT_3_migration_0022_is_reversible():
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import Column, MetaData, Table, Uuid, create_engine, inspect

    path = Path(__file__).parents[1] / "alembic/versions/0022_phase7_reports.py"
    spec = importlib.util.spec_from_file_location("phase7_migration", path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    metadata = MetaData()
    Table("users", metadata, Column("id", Uuid(), primary_key=True))
    metadata.create_all(engine)
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        tables = set(inspect(connection).get_table_names())
        assert {"report_share_links", "bookkeeper_invites"} <= tables
        migration.downgrade()
        assert "report_share_links" not in inspect(connection).get_table_names()
    engine.dispose()


@pytest.mark.asyncio
async def test_RPT_1_RPT_2_RPT_3_RPT_4_reports_exports_sharing_and_bookkeeper_access():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        owner = User(email="owner@example.com", created_at=NOW)
        bookkeeper = User(email="books@example.com", created_at=NOW)
        stranger = User(email="stranger@example.com", created_at=NOW)
        institution = Institution(name="Fixture", code="RPT7", savings_rate_bps=0)
        db.add_all((owner, bookkeeper, stranger, institution))
        await db.flush()
        consent = Consent(
            user_id=owner.id,
            institution="Fixture",
            scope="transactions:read",
            granted_at=NOW,
            expires_at=NOW + timedelta(days=30),
        )
        db.add(consent)
        await db.flush()
        account = Account(
            user_id=owner.id,
            institution_id=institution.id,
            consent_id=consent.id,
            account_number_masked="****0000",
            type=AccountType.current,
            current_balance_minor=100_000,
        )
        db.add(account)
        await db.flush()
        income = Transaction(
            account_id=account.id,
            posted_at=NOW - timedelta(days=10),
            amount_minor=100_000,
            direction=Direction.credit,
            narration_raw="CLIENT PAYMENT",
            narration_clean="CLIENT PAYMENT",
            decoded_merchant="Client",
            category="Uncategorised",
            channel="NIP",
            dedupe_hash=uuid4().hex * 2,
        )
        business = Transaction(
            account_id=account.id,
            posted_at=NOW - timedelta(days=8),
            amount_minor=30_000,
            direction=Direction.debit,
            narration_raw="POWER BILL",
            narration_clean="POWER BILL",
            decoded_merchant="Power",
            category="Bills & Utilities",
            channel="WEB",
            dedupe_hash=uuid4().hex * 2,
        )
        unsure = Transaction(
            account_id=account.id,
            posted_at=NOW - timedelta(days=2),
            amount_minor=20_000,
            direction=Direction.debit,
            narration_raw="UNKNOWN TRANSFER",
            narration_clean="UNKNOWN TRANSFER",
            decoded_merchant="Unknown",
            category="Uncategorised",
            channel="NIP",
            dedupe_hash=uuid4().hex * 2,
            parse_confidence_bps=4500,
        )
        db.add_all((income, business, unsure))
        await db.flush()
        db.add(
            TransactionUseLabel(
                transaction_id=business.id,
                user_id=owner.id,
                suggested_label="business",
                confidence_bps=8000,
                confirmed_label="business",
                updated_at=NOW,
            )
        )
        await db.commit()

    active_user = {"value": owner}

    async def database():
        async with sessions() as db:
            yield db

    async def identity():
        return active_user["value"]

    main.app.dependency_overrides[get_db] = database
    main.app.dependency_overrides[current_user] = identity
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://test"
        ) as client:
            report_response = await client.get("/reports/monthly/2026-10")
            assert report_response.status_code == 200
            report = report_response.json()
            assert report["income_minor"] == 100_000
            assert report["expenses_minor"] == 50_000
            assert report["net_cash_flow_minor"] == 50_000
            assert report["business_expenses_minor"] == 30_000
            assert report["unsure_expenses_minor"] == 20_000
            assert str(unsure.id) in {item["transaction_id"] for item in report["uncertain_items"]}

            csv_export = await client.get(
                "/reports/monthly/2026-10/export", params={"format": "csv"}
            )
            assert csv_export.status_code == 200
            assert b"business" in csv_export.content and b"unsure" in csv_export.content
            pdf_export = await client.get(
                "/reports/monthly/2026-10/export", params={"format": "pdf"}
            )
            assert pdf_export.status_code == 200
            assert pdf_export.content.startswith(b"%PDF")
            from io import BytesIO

            pdf_text = "\n".join(
                page.extract_text() or "" for page in PdfReader(BytesIO(pdf_export.content)).pages
            )
            assert "Net cash flow" in pdf_text
            assert "low confidence" in pdf_text

            shared = await client.post(
                "/reports/monthly/2026-10/share-links", json={"expires_in_days": 2}
            )
            assert shared.status_code == 201
            shared_body = shared.json()
            token = urlparse(shared_body["url"]).path.rsplit("/", 1)[-1]
            public_report = await client.get(f"/shared/reports/{token}")
            assert public_report.status_code == 200
            async with sessions() as db:
                stored = (await db.scalars(select(ReportShareLink))).one()
                assert token not in stored.token_hash
            assert (
                await client.delete(f"/report-share-links/{shared_body['id']}")
            ).status_code == 204
            assert (await client.get(f"/shared/reports/{token}")).status_code == 404

            invite = await client.post("/bookkeeper-invites", json={"email": "books@example.com"})
            assert invite.status_code == 201
            invite_body = invite.json()
            invite_token = urlparse(invite_body["invite_url"]).path.split("/")[-2]
            assert (
                await client.post("/bookkeeper-invites", json={"email": "second@example.com"})
            ).status_code == 409

            active_user["value"] = stranger
            assert (
                await client.post(f"/bookkeeper-invites/{invite_token}/accept")
            ).status_code == 404
            active_user["value"] = bookkeeper
            accepted = await client.post(f"/bookkeeper-invites/{invite_token}/accept")
            assert accepted.status_code == 200
            assert (
                await client.get(f"/bookkeeper/clients/{owner.id}/reports/monthly/2026-10")
            ).status_code == 200
            ledger = await client.get(f"/bookkeeper/clients/{owner.id}/transactions")
            assert ledger.status_code == 200 and len(ledger.json()) == 3

            active_user["value"] = owner
            assert (
                await client.delete(f"/bookkeeper-invites/{invite_body['id']}")
            ).status_code == 204
            active_user["value"] = bookkeeper
            assert (
                await client.get(f"/bookkeeper/clients/{owner.id}/reports/monthly/2026-10")
            ).status_code == 404
            async with sessions() as db:
                stored_invite = (await db.scalars(select(BookkeeperInvite))).one()
                assert invite_token not in stored_invite.token_hash
    finally:
        main.app.dependency_overrides.clear()
        await engine.dispose()
