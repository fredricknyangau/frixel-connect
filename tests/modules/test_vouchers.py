"""
tests/modules/test_vouchers.py
==============================
Integration tests for Phase 5: RADIUS Integration & Live Session Control.

Asserts:
  1. Voucher generation inserts credentials into FreeRADIUS (radcheck, radreply).
  2. Voucher revocation deletes credentials and triggers CoA Disconnect-Request.
  3. Session sync cron job correctly pulls active radacct sessions into the local sessions table.
"""

import asyncio
from unittest.mock import AsyncMock, patch
from uuid import UUID

import asyncpg
import pytest
from fastapi.testclient import TestClient

from app.modules.vouchers.service import generate_voucher
from app.worker import sync_radius_sessions_cron

@pytest.fixture
async def sample_payment(conn: asyncpg.Connection) -> str:
    """Creates a sample payment and returns its ID."""
    # 1. Ensure a customer exists in default tenant
    tenant_id = "aaaaaaaa-0000-0000-0000-000000000001"
    customer = await conn.fetchrow("SELECT id, phone FROM users WHERE role = 'customer' LIMIT 1")
    
    # 2. Ensure a package exists
    pkg = await conn.fetchrow("SELECT id, price_kes, speed_mbps FROM packages LIMIT 1")
    
    # 3. Insert confirmed payment
    payment_id = await conn.fetchval(
        """
        INSERT INTO payments (customer_id, package_id, amount_kes, status, phone_number, mpesa_checkout_id, mpesa_receipt_number, tenant_id)
        VALUES ($1, $2, $3, 'confirmed', $4, 'WS_CHK_123', 'WS_RCT_123', $5)
        RETURNING id
        """,
        customer["id"],
        pkg["id"],
        pkg["price_kes"],
        customer["phone"],
        tenant_id
    )
    return str(payment_id)


@pytest.mark.asyncio
async def test_voucher_generation_provisions_radius(
    client: TestClient, conn: asyncpg.Connection, sample_payment: str
):
    """Asserts that generating a voucher inserts Cleartext-Password into radcheck and Rate-Limit into radreply."""
    # Generate voucher directly via service
    async with conn.transaction():
        code = await generate_voucher(conn, sample_payment, is_final_attempt=True)

    assert code is not None

    # Check FreeRADIUS tables
    radcheck_row = await conn.fetchrow("SELECT username, attribute, value FROM radcheck WHERE username = $1", code)
    assert radcheck_row is not None
    assert radcheck_row["attribute"] == "Cleartext-Password"
    assert radcheck_row["value"] == code

    radreply_rows = await conn.fetch("SELECT username, attribute, value FROM radreply WHERE username = $1", code)
    assert len(radreply_rows) > 0
    attributes = {row["attribute"]: row["value"] for row in radreply_rows}
    assert "Mikrotik-Rate-Limit" in attributes


@pytest.mark.asyncio
@patch("app.modules.vouchers.service.asyncio.to_thread")
async def test_voucher_revocation_triggers_coa(
    mock_to_thread, client: TestClient, conn: asyncpg.Connection, sample_payment: str
):
    """Asserts that revoking a voucher deletes radcheck/radreply and sends a CoA disconnect."""
    # Generate a voucher first
    async with conn.transaction():
        code = await generate_voucher(conn, sample_payment, is_final_attempt=True)
    
    # Get the voucher ID
    voucher = await conn.fetchrow("SELECT id FROM vouchers WHERE code = $1", code)
    voucher_id = str(voucher["id"])

    # Simulate an active session in radacct
    await conn.execute(
        """
        INSERT INTO radacct (acctsessionid, acctuniqueid, username, nasipaddress, acctstarttime)
        VALUES ('sess_123', 'uniq_123', $1, '192.168.88.1', NOW())
        """,
        code
    )

    # Get admin token for the endpoint
    tenant_id = "aaaaaaaa-0000-0000-0000-000000000001"
    admin = await conn.fetchrow("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
    from app.core.security import create_access_token
    token = create_access_token(str(admin["id"]), "admin", tenant_id)

    # Revoke voucher via API
    resp = client.post(
        f"/api/v1/vouchers/{voucher_id}/revoke",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200

    # Verify radcheck and radreply are empty
    radcheck_count = await conn.fetchval("SELECT COUNT(*) FROM radcheck WHERE username = $1", code)
    radreply_count = await conn.fetchval("SELECT COUNT(*) FROM radreply WHERE username = $1", code)
    assert radcheck_count == 0
    assert radreply_count == 0

    # Verify CoA disconnect was called in thread
    mock_to_thread.assert_called_once()
    args, _ = mock_to_thread.call_args
    # The first argument is the function send_coa_disconnect
    from app.integrations.radius_coa import send_coa_disconnect
    assert args[0] == send_coa_disconnect
    assert args[1] == '192.168.88.1'
    assert args[2] == code
    assert args[3] == 'sess_123'


@pytest.mark.asyncio
async def test_sync_radius_sessions_cron(
    conn: asyncpg.Connection, sample_payment: str
):
    """Asserts that the session sync cron job copies radacct rows into the local sessions table."""
    # Generate a voucher
    async with conn.transaction():
        code = await generate_voucher(conn, sample_payment, is_final_attempt=True)
    
    voucher = await conn.fetchrow("SELECT id FROM vouchers WHERE code = $1", code)
    voucher_id = voucher["id"]

    # Insert a simulated active session in FreeRADIUS radacct
    await conn.execute(
        """
        INSERT INTO radacct (acctsessionid, acctuniqueid, username, nasipaddress, framedipaddress, callingstationid, acctinputoctets, acctoutputoctets, acctstarttime)
        VALUES ('sess_sync', 'uniq_sync', $1, '192.168.88.1', '10.0.0.5', 'AA:BB:CC:DD:EE:FF', 1024, 2048, NOW())
        """,
        code
    )

    # Mock the context for the cron
    class MockPool:
        def acquire(self):
            class ContextManager:
                async def __aenter__(self):
                    return conn
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    pass
            return ContextManager()

    ctx = {"db_pool": MockPool()}

    # Run the cron job manually
    await sync_radius_sessions_cron(ctx)

    # Verify local sessions table was populated
    session_row = await conn.fetchrow("SELECT * FROM sessions WHERE acct_unique_id = 'uniq_sync'")
    assert session_row is not None
    assert session_row["voucher_id"] == voucher_id
    assert session_row["mac_address"] == "AA:BB:CC:DD:EE:FF"
    assert str(session_row["ip_address"]) == "10.0.0.5"
    assert session_row["bytes_uploaded"] == 1024
    assert session_row["bytes_downloaded"] == 2048
    assert session_row["ended_at"] is None

    # Simulate session end in FreeRADIUS
    await conn.execute(
        "UPDATE radacct SET acctstoptime = NOW(), acctinputoctets = 5000 WHERE acctuniqueid = 'uniq_sync'"
    )

    # Run the cron job again to test UPSERT
    await sync_radius_sessions_cron(ctx)

    session_row_updated = await conn.fetchrow("SELECT * FROM sessions WHERE acct_unique_id = 'uniq_sync'")
    assert session_row_updated["ended_at"] is not None
    assert session_row_updated["bytes_uploaded"] == 5000
