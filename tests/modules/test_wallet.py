"""
tests/modules/test_wallet.py
=============================
Integration and unit tests for Phase 4: Reseller Wallet & Ledger.

Asserts:
  1. Wallet GET endpoint permissions and payload structure.
  2. Daraja C2B validation webhook (validation rules, HTTP 200 return codes).
  3. Daraja C2B confirmation webhook (topups, unique receipt idempotency).
  4. Reseller direct voucher generation (balance checks, debiting, automatic payment creation).
  5. Multi-tenant customer/package isolation checks for voucher generation.
  6. Concurrency locking using parallel transaction executions.
"""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password, create_access_token
from app.modules.wallets.service import (
    topup_wallet,
    debit_wallet,
    get_wallet_balance,
    get_wallet_transactions,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def create_tenant_and_reseller(
    conn: asyncpg.Connection,
    business_name: str,
    email: str,
    phone: str,
    wallet_ref: str = None,
) -> tuple[str, str, str, str]:
    """
    Creates a tenant and reseller user in the test database.
    Returns (tenant_id, reseller_id, access_token, wallet_reference).
    """
    if not wallet_ref:
        import random
        wallet_ref = f"WS{random.randint(10000, 99999)}"

    # Insert tenant
    tenant_id = await conn.fetchval(
        """
        INSERT INTO tenants (business_name, owner_email, owner_phone,
                             subscription_tier, max_customers, status)
        VALUES ($1, $2, $3, 'starter', 50, 'active')
        RETURNING id
        """,
        business_name,
        email,
        phone,
    )

    # Insert reseller user
    reseller_id = await conn.fetchval(
        """
        INSERT INTO users (email, phone, hashed_password, role, tenant_id, wallet_reference)
        VALUES ($1, $2, $3, 'reseller', $4, $5)
        RETURNING id
        """,
        email,
        phone,
        hash_password("TestPassword123!"),
        tenant_id,
        wallet_ref,
    )

    # Mint token
    token = create_access_token(
        user_id=str(reseller_id),
        role="reseller",
        tenant_id=str(tenant_id),
    )

    return str(tenant_id), str(reseller_id), token, wallet_ref


async def create_customer_in_tenant(
    conn: asyncpg.Connection,
    tenant_id: str,
    email: str,
    phone: str,
    reseller_id: str = None,
) -> str:
    """Creates a customer user in the specified tenant."""
    res_uuid = UUID(reseller_id) if reseller_id else None
    user_id = await conn.fetchval(
        """
        INSERT INTO users (email, phone, hashed_password, role, tenant_id, reseller_id)
        VALUES ($1, $2, $3, 'customer', $4, $5)
        RETURNING id
        """,
        email,
        phone,
        hash_password("TestPassword123!"),
        UUID(tenant_id),
        res_uuid,
    )
    return str(user_id)


async def create_package_in_tenant(
    conn: asyncpg.Connection,
    tenant_id: str,
    name: str,
    price: Decimal = Decimal("50.00"),
    is_active: bool = True,
) -> str:
    """Creates a package in the specified tenant."""
    pkg_id = await conn.fetchval(
        """
        INSERT INTO packages (name, price_kes, duration_days, speed_mbps, created_by, tenant_id, is_active)
        VALUES ($1, $2, 1, 10, NULL, $3, $4)
        RETURNING id
        """,
        name,
        price,
        UUID(tenant_id),
        is_active,
    )
    return str(pkg_id)


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_wallet_balance_and_transactions(client: TestClient, conn: asyncpg.Connection):
    """Asserts that a reseller can retrieve their wallet balance and transaction ledger."""
    # 1. Create tenant and reseller
    tenant_id, reseller_id, token, _ = await create_tenant_and_reseller(
        conn, "Reseller Wallet Corp", "reseller_wallet@test.com", "254722000001"
    )

    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get wallet balance (initial should be 0.00)
    resp = client.get("/api/v1/reseller/wallet", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert Decimal(data["balance"]) == Decimal("0.00")
    assert len(data["transactions"]) == 0

    # 3. Simulate wallet topup directly via service
    async with conn.transaction():
        await topup_wallet(
            conn,
            tenant_id=UUID(tenant_id),
            reseller_id=UUID(reseller_id),
            amount=Decimal("1500.50"),
            reference="TXN_TEST_TOPUP",
        )

    # 4. Get wallet balance again
    resp = client.get("/api/v1/reseller/wallet", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert Decimal(data["balance"]) == Decimal("1500.50")
    assert len(data["transactions"]) == 1
    assert data["transactions"][0]["type"] == "topup"
    assert Decimal(data["transactions"][0]["amount_kes"]) == Decimal("1500.50")
    assert Decimal(data["transactions"][0]["balance_after"]) == Decimal("1500.50")
    assert data["transactions"][0]["reference"] == "TXN_TEST_TOPUP"


@pytest.mark.asyncio
async def test_wallet_endpoint_rbac(client: TestClient, conn: asyncpg.Connection):
    """Asserts that non-reseller roles are rejected from the wallet endpoint."""
    # 1. Admin login token
    admin_token = create_access_token(
        user_id=str(uuid4()),
        role="admin",
        tenant_id="aaaaaaaa-0000-0000-0000-000000000001",
    )
    # 2. Customer login token
    customer_token = create_access_token(
        user_id=str(uuid4()),
        role="customer",
        tenant_id="aaaaaaaa-0000-0000-0000-000000000001",
    )

    # Admin access check
    resp = client.get(
        "/api/v1/reseller/wallet",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 403

    # Customer access check
    resp = client.get(
        "/api/v1/reseller/wallet",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_daraja_c2b_validation(client: TestClient, conn: asyncpg.Connection):
    """Asserts that C2B validation correctly validates reseller references."""
    # 1. Create a reseller with reference WS55555
    _, _, _, wallet_ref = await create_tenant_and_reseller(
        conn, "C2B ISP", "c2b_reseller@test.com", "254722000002", wallet_ref="WS55555"
    )

    # 2. Call C2B validation with the correct reference
    payload_valid = {
        "TransactionType": "Pay Bill Validation",
        "BillRefNumber": "WS55555",
        "MSISDN": "254712345678",
        "TransAmount": "500",
    }
    resp = client.post("/api/v1/webhooks/daraja/c2b", json=payload_valid)
    assert resp.status_code == 200
    assert resp.json() == {
        "ResultCode": 0,
        "ResultDesc": "Service completed successfully",
    }

    # 3. Call C2B validation with an invalid reference
    payload_invalid = {
        "TransactionType": "Pay Bill Validation",
        "BillRefNumber": "WS99999",
        "MSISDN": "254712345678",
        "TransAmount": "500",
    }
    resp = client.post("/api/v1/webhooks/daraja/c2b", json=payload_invalid)
    assert resp.status_code == 200
    assert resp.json() == {
        "ResultCode": 1,
        "ResultDesc": "Invalid wallet reference",
    }


@pytest.mark.asyncio
async def test_daraja_c2b_confirmation_and_idempotency(client: TestClient, conn: asyncpg.Connection):
    """Asserts that C2B confirmation tops up the wallet and handles duplicate webhooks idempotently."""
    # 1. Create reseller
    _, reseller_id, token, wallet_ref = await create_tenant_and_reseller(
        conn, "C2B Confirm ISP", "c2b_confirm@test.com", "254722000003", wallet_ref="WS66666"
    )

    # 2. Call confirmation webhook
    payload = {
        "TransactionType": "Pay Bill Confirmation",
        "BillRefNumber": wallet_ref,
        "TransID": "MPESAREF123",
        "TransAmount": "400.00",
        "MSISDN": "254712345678",
    }
    resp = client.post("/api/v1/webhooks/daraja/c2b", json=payload)
    assert resp.status_code == 200
    assert resp.json() == {
        "ResultCode": 0,
        "ResultDesc": "Service completed successfully",
    }

    # Verify balance was updated
    balance = await get_wallet_balance(conn, UUID(reseller_id))
    assert balance == Decimal("400.00")

    # 3. Send duplicate webhook with same TransID
    resp = client.post("/api/v1/webhooks/daraja/c2b", json=payload)
    assert resp.status_code == 200
    assert resp.json() == {
        "ResultCode": 0,
        "ResultDesc": "Service completed successfully",
    }

    # Verify balance is still KES 400.00 (was not topped up twice)
    balance = await get_wallet_balance(conn, UUID(reseller_id))
    assert balance == Decimal("400.00")


@pytest.mark.asyncio
@patch("app.modules.vouchers.service.get_mikrotik_client")
async def test_generate_reseller_voucher_success(mock_get_client, client: TestClient, conn: asyncpg.Connection):
    """Asserts that reseller voucher generation succeeds when wallet balance is sufficient."""
    # Mock MikroTik
    mock_mikrotik = MagicMock()
    mock_get_client.return_value = mock_mikrotik
    mock_mikrotik.generate_hotspot_user = AsyncMock(return_value={"ret": "*10"})

    # 1. Create reseller
    tenant_id, reseller_id, token, _ = await create_tenant_and_reseller(
        conn, "Voucher Gen ISP", "voucher_reseller@test.com", "254722000004"
    )

    # 2. Topup wallet
    async with conn.transaction():
        await topup_wallet(
            conn,
            tenant_id=UUID(tenant_id),
            reseller_id=UUID(reseller_id),
            amount=Decimal("300.00"),
            reference="TOPUP_VOUCHER_GEN",
        )

    # 3. Create active package and customer
    pkg_id = await create_package_in_tenant(conn, tenant_id, "Promo Package", price=Decimal("120.00"))
    customer_id = await create_customer_in_tenant(
        conn, tenant_id, "customer_res@test.com", "254722000005", reseller_id=reseller_id
    )

    # 4. Request voucher generation
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post(
        "/api/v1/reseller/vouchers/generate",
        json={
            "customer_id": customer_id,
            "package_id": pkg_id,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "code" in data
    assert data["status"] == "active"
    assert data["package_name"] == "Promo Package"

    # 5. Verify database checks
    # Wallet balance debited
    balance = await get_wallet_balance(conn, UUID(reseller_id))
    assert balance == Decimal("180.00")

    # Transaction ledger entry created
    transactions = await get_wallet_transactions(conn, UUID(reseller_id))
    assert len(transactions) == 2
    assert transactions[0]["type"] == "debit"
    assert Decimal(transactions[0]["amount_kes"]) == Decimal("120.00")
    assert Decimal(transactions[0]["balance_after"]) == Decimal("180.00")

    # Payment row is confirmed
    payment_row = await conn.fetchrow(
        "SELECT status, mpesa_receipt_number FROM payments WHERE customer_id = $1",
        UUID(customer_id),
    )
    assert payment_row is not None
    assert payment_row["status"] == "confirmed"
    assert payment_row["mpesa_receipt_number"].startswith("WAL-")

    # MikroTik API was invoked
    mock_mikrotik.generate_hotspot_user.assert_called_once()


@pytest.mark.asyncio
@patch("app.modules.vouchers.service.get_mikrotik_client")
async def test_generate_reseller_voucher_insufficient_balance(mock_get_client, client: TestClient, conn: asyncpg.Connection):
    """Asserts that voucher generation fails with HTTP 402 if wallet balance is too low."""
    mock_mikrotik = MagicMock()
    mock_get_client.return_value = mock_mikrotik

    # 1. Create reseller
    tenant_id, reseller_id, token, _ = await create_tenant_and_reseller(
        conn, "No Balance ISP", "no_bal_reseller@test.com", "254722000006"
    )

    # 2. Create customer and package
    pkg_id = await create_package_in_tenant(conn, tenant_id, "Promo Package", price=Decimal("120.00"))
    customer_id = await create_customer_in_tenant(
        conn, tenant_id, "cust_nobal@test.com", "254722000007", reseller_id=reseller_id
    )

    # 3. Call endpoint (balance is 0)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post(
        "/api/v1/reseller/vouchers/generate",
        json={
            "customer_id": customer_id,
            "package_id": pkg_id,
        },
        headers=headers,
    )
    assert resp.status_code == 402
    assert "insufficient balance" in resp.json()["detail"].lower()

    # 4. Verify no debit happened, no payment inserted
    balance = await get_wallet_balance(conn, UUID(reseller_id))
    assert balance == Decimal("0.00")

    payment_count = await conn.fetchval("SELECT COUNT(*) FROM payments")
    assert payment_count == 0

    mock_mikrotik.generate_hotspot_user.assert_not_called()


@pytest.mark.asyncio
async def test_generate_reseller_voucher_isolation_checks(client: TestClient, conn: asyncpg.Connection):
    """Asserts that a reseller cannot generate vouchers for customers/packages of a different tenant."""
    # Tenant A & Reseller A
    tenant_a_id, reseller_a_id, token_a, _ = await create_tenant_and_reseller(
        conn, "Tenant A", "reseller_a@test.com", "254722000010"
    )
    # Topup Reseller A
    async with conn.transaction():
        await topup_wallet(conn, UUID(tenant_a_id), UUID(reseller_a_id), Decimal("500.00"), "TOPUP_A")

    # Tenant B & Reseller B & Customer B & Package B
    tenant_b_id, reseller_b_id, token_b, _ = await create_tenant_and_reseller(
        conn, "Tenant B", "reseller_b@test.com", "254722000011"
    )
    customer_b_id = await create_customer_in_tenant(conn, tenant_b_id, "cust_b@test.com", "254722000012")
    pkg_b_id = await create_package_in_tenant(conn, tenant_b_id, "B Package")

    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Reseller A tries to generate voucher for Customer B (fails 404)
    resp = client.post(
        "/api/v1/reseller/vouchers/generate",
        json={
            "customer_id": customer_b_id,
            "package_id": pkg_b_id,
        },
        headers=headers_a,
    )
    assert resp.status_code == 404
    assert "customer" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_generate_reseller_voucher_inactive_package(client: TestClient, conn: asyncpg.Connection):
    """Asserts that trying to generate a voucher for an inactive package fails with 409."""
    # 1. Create reseller
    tenant_id, reseller_id, token, _ = await create_tenant_and_reseller(
        conn, "Inactive Pkg ISP", "inactive_pkg@test.com", "254722000020"
    )

    # 2. Topup wallet
    async with conn.transaction():
        await topup_wallet(conn, UUID(tenant_id), UUID(reseller_id), Decimal("500.00"), "TOPUP_INACTIVE")

    # 3. Create inactive package
    pkg_id = await create_package_in_tenant(
        conn, tenant_id, "Inactive Package", price=Decimal("100.00"), is_active=False
    )
    customer_id = await create_customer_in_tenant(
        conn, tenant_id, "cust_inactive@test.com", "254722000021"
    )

    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post(
        "/api/v1/reseller/vouchers/generate",
        json={
            "customer_id": customer_id,
            "package_id": pkg_id,
        },
        headers=headers,
    )
    assert resp.status_code == 409
    assert "inactive" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_wallet_concurrency_locking(db_pool: asyncpg.Pool):
    """
    Executes multiple concurrent top-up transactions in parallel using asyncio.gather.
    Ensures that row-level locking (SELECT id FROM users WHERE id = $1 FOR UPDATE)
    prevents race conditions, resulting in the correct final balance.
    """
    # 1. Create reseller user in DB
    # We acquire a direct connection to set up the reseller.
    async with db_pool.acquire() as setup_conn:
        tenant_id, reseller_id, _, _ = await create_tenant_and_reseller(
            setup_conn, "Concurrency ISP", "concurrency@test.com", "254722000030"
        )

    # We will run 10 concurrent topups of KES 100 each.
    # Each task acquires its own database connection from the pool.
    num_tasks = 10
    topup_amount = Decimal("100.00")
    res_uuid = UUID(reseller_id)
    ten_uuid = UUID(tenant_id)

    async def execute_parallel_topup(index: int):
        # Acquire connection from the test pool
        async with db_pool.acquire() as conn:
            # We must use transaction wrapper so SELECT ... FOR UPDATE retains lock
            async with conn.transaction():
                await topup_wallet(
                    conn,
                    tenant_id=ten_uuid,
                    reseller_id=res_uuid,
                    amount=topup_amount,
                    reference=f"CONC_TXN_{index}",
                )

    # Gather tasks concurrently
    tasks = [execute_parallel_topup(i) for i in range(num_tasks)]
    await asyncio.gather(*tasks)

    # Assert final balance is exactly 10 * 100.00 = 1000.00
    async with db_pool.acquire() as verify_conn:
        final_balance = await get_wallet_balance(verify_conn, res_uuid)
        assert final_balance == Decimal("1000.00")

        # Verify 10 transactions were logged in the ledger
        transactions = await get_wallet_transactions(verify_conn, res_uuid, limit=50)
        assert len(transactions) == 10
