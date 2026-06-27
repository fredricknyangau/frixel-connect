"""
tests/modules/test_reconciliation.py
======================================
Integration and unit tests for the background reconciliation cron,
manual retry admin endpoint, stuck payment query, and durable worker task retry loop.
"""

from decimal import Decimal
from unittest.mock import ANY, AsyncMock, MagicMock, patch
from uuid import UUID, uuid4
import asyncpg
import pytest
from arq import Retry
from fastapi.testclient import TestClient

from app.core.security import hash_password, create_access_token
from app.worker import generate_voucher_task, reconcile_payments_cron
from tests.conftest import DEFAULT_TENANT_ID, TEST_PASSWORD


async def get_test_customer_and_package_ids(conn: asyncpg.Connection):
    """Utility to retrieve seeded customer and package IDs."""
    customer_id = await conn.fetchval("SELECT id FROM users WHERE email = $1", "customer@zealsync.dev")
    package_id = await conn.fetchval("SELECT id FROM packages WHERE name = $1", "Daily 10Mbps")
    return customer_id, package_id


async def create_tenant_and_admin(
    conn: asyncpg.Connection,
    business_name: str,
    email: str,
    phone: str,
) -> tuple[str, str, str]:
    """Creates a tenant and admin user. Returns (tenant_id, user_id, token)."""
    tenant_id = await conn.fetchval(
        """
        INSERT INTO tenants (business_name, owner_email, owner_phone, subscription_tier, max_customers, status)
        VALUES ($1, $2, $3, 'starter', 50, 'active')
        RETURNING id
        """,
        business_name, email, phone
    )
    user_id = await conn.fetchval(
        """
        INSERT INTO users (email, phone, hashed_password, role, tenant_id)
        VALUES ($1, $2, $3, 'admin', $4)
        RETURNING id
        """,
        email, phone, hash_password(TEST_PASSWORD), tenant_id
    )
    token = create_access_token(user_id=str(user_id), role="admin", tenant_id=str(tenant_id))
    return str(tenant_id), str(user_id), token


@pytest.mark.asyncio
async def test_get_stuck_payments(conn: asyncpg.Connection, client: TestClient):
    """
    Asserts that:
      1. Confirmed payments older than 2 minutes with no vouchers are returned.
      2. Confirmed payments newer than 2 minutes are NOT returned.
      3. Confirmed payments with vouchers are NOT returned.
      4. Non-confirmed (pending) payments are NOT returned.
      5. Tenant isolation works (Tenant A admin doesn't see Tenant B stuck payments).
    """
    customer_id, package_id = await get_test_customer_and_package_ids(conn)

    # 1. Stuck payment (Tenant A, confirmed, 3 mins old, no voucher)
    stuck_id = await conn.fetchval(
        """
        INSERT INTO payments (customer_id, package_id, amount_kes, status, phone_number, mpesa_checkout_id, tenant_id, created_at)
        VALUES ($1, $2, 50.00, 'confirmed', '254708374149', 'checkout-1', $3, NOW() - INTERVAL '3 minutes')
        RETURNING id
        """,
        customer_id, package_id, UUID(DEFAULT_TENANT_ID)
    )

    # 2. Too recent payment (Tenant A, confirmed, 1 min old, no voucher)
    recent_id = await conn.fetchval(
        """
        INSERT INTO payments (customer_id, package_id, amount_kes, status, phone_number, mpesa_checkout_id, tenant_id, created_at)
        VALUES ($1, $2, 50.00, 'confirmed', '254708374149', 'checkout-2', $3, NOW() - INTERVAL '1 minute')
        RETURNING id
        """,
        customer_id, package_id, UUID(DEFAULT_TENANT_ID)
    )

    # 3. Confirmed but already has voucher (Tenant A, confirmed, 3 mins old, has voucher)
    has_voucher_payment_id = await conn.fetchval(
        """
        INSERT INTO payments (customer_id, package_id, amount_kes, status, phone_number, mpesa_checkout_id, tenant_id, created_at)
        VALUES ($1, $2, 50.00, 'confirmed', '254708374149', 'checkout-3', $3, NOW() - INTERVAL '3 minutes')
        RETURNING id
        """,
        customer_id, package_id, UUID(DEFAULT_TENANT_ID)
    )
    await conn.execute(
        """
        INSERT INTO vouchers (payment_id, customer_id, package_id, code, status, tenant_id)
        VALUES ($1, $2, $3, 'VOUCH3R123', 'active', $4)
        """,
        has_voucher_payment_id, customer_id, package_id, UUID(DEFAULT_TENANT_ID)
    )

    # 4. Pending payment (Tenant A, pending, 3 mins old, no voucher)
    pending_id = await conn.fetchval(
        """
        INSERT INTO payments (customer_id, package_id, amount_kes, status, phone_number, mpesa_checkout_id, tenant_id, created_at)
        VALUES ($1, $2, 50.00, 'pending', '254708374149', 'checkout-4', $3, NOW() - INTERVAL '3 minutes')
        RETURNING id
        """,
        customer_id, package_id, UUID(DEFAULT_TENANT_ID)
    )

    # 5. Create Tenant B and insert a Tenant B stuck payment
    tenant_b_id, tenant_b_admin_id, token_b = await create_tenant_and_admin(
        conn, "Tenant B ISP", "admin_b_recon@test.com", "254711999912"
    )
    # Create customer & package for Tenant B
    cust_b_id = await conn.fetchval(
        "INSERT INTO users (email, phone, hashed_password, role, tenant_id) VALUES ($1, $2, $3, 'customer', $4) RETURNING id",
        "customer_b@test.com", "254711999913", hash_password(TEST_PASSWORD), UUID(tenant_b_id)
    )
    pkg_b_id = await conn.fetchval(
        "INSERT INTO packages (name, price_kes, duration_minutes, speed_mbps, created_by, tenant_id) VALUES ($1, $2, 1440, 10, $3, $4) RETURNING id",
        "B Daily", Decimal("50.00"), UUID(tenant_b_admin_id), UUID(tenant_b_id)
    )
    stuck_b_id = await conn.fetchval(
        """
        INSERT INTO payments (customer_id, package_id, amount_kes, status, phone_number, mpesa_checkout_id, tenant_id, created_at)
        VALUES ($1, $2, 50.00, 'confirmed', '254711999913', 'checkout-5', $3, NOW() - INTERVAL '3 minutes')
        RETURNING id
        """,
        cust_b_id, pkg_b_id, UUID(tenant_b_id)
    )

    # ── Test Tenant A stuck payments list ──
    admin_a_id = await conn.fetchval("SELECT id FROM users WHERE email = 'admin@zealsync.dev'")
    token_a = create_access_token(user_id=str(admin_a_id), role="admin", tenant_id=DEFAULT_TENANT_ID)
    headers_a = {"Authorization": f"Bearer {token_a}"}

    resp_a = client.get("/api/v1/admin/payments/stuck", headers=headers_a)
    assert resp_a.status_code == 200
    stuck_a_list = resp_a.json()
    
    # Must only return Payment 1 (stuck_id)
    assert len(stuck_a_list) == 1
    assert stuck_a_list[0]["id"] == str(stuck_id)

    # ── Test Tenant B stuck payments list ──
    headers_b = {"Authorization": f"Bearer {token_b}"}
    resp_b = client.get("/api/v1/admin/payments/stuck", headers=headers_b)
    assert resp_b.status_code == 200
    stuck_b_list = resp_b.json()

    # Must only return stuck_b_id
    assert len(stuck_b_list) == 1
    assert stuck_b_list[0]["id"] == str(stuck_b_id)


@pytest.mark.asyncio
@patch("app.core.redis.get_redis_pool")
async def test_retry_provision_payment_endpoint(mock_get_redis, conn: asyncpg.Connection, client: TestClient):
    """
    Asserts that:
      1. Correctly enqueues voucher task for stuck confirmed payments.
      2. Rejects invalid UUID -> 400.
      3. Returns 404 for non-existent or cross-tenant payments.
      4. Rejects non-confirmed payments or payments with existing vouchers -> 400.
    """
    customer_id, package_id = await get_test_customer_and_package_ids(conn)

    # Create mock Redis client
    mock_redis = MagicMock()
    mock_redis.enqueue_job = AsyncMock()
    mock_get_redis.return_value = mock_redis

    # Create Tenant A admin token
    admin_a_id = await conn.fetchval("SELECT id FROM users WHERE email = 'admin@zealsync.dev'")
    token_a = create_access_token(user_id=str(admin_a_id), role="admin", tenant_id=DEFAULT_TENANT_ID)
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 1. Stuck payment (Tenant A, confirmed, 3 mins old, no voucher)
    stuck_id = await conn.fetchval(
        """
        INSERT INTO payments (customer_id, package_id, amount_kes, status, phone_number, mpesa_checkout_id, tenant_id, created_at)
        VALUES ($1, $2, 50.00, 'confirmed', '254708374149', 'checkout-11', $3, NOW() - INTERVAL '3 minutes')
        RETURNING id
        """,
        customer_id, package_id, UUID(DEFAULT_TENANT_ID)
    )

    # Successful call
    resp = client.post(f"/api/v1/admin/payments/{stuck_id}/retry-provision", headers=headers_a)
    assert resp.status_code == 202
    assert resp.json() == {"message": "Provisioning task enqueued."}
    mock_redis.enqueue_job.assert_called_once_with(
        "generate_voucher_task",
        str(stuck_id),
        DEFAULT_TENANT_ID,
        _request_id=ANY,
    )
    mock_redis.enqueue_job.reset_mock()

    # 2. Invalid UUID
    resp = client.post("/api/v1/admin/payments/not-a-uuid/retry-provision", headers=headers_a)
    assert resp.status_code == 400

    # 3. Non-existent payment UUID
    non_existent = str(uuid4())
    resp = client.post(f"/api/v1/admin/payments/{non_existent}/retry-provision", headers=headers_a)
    assert resp.status_code == 404

    # 4. Cross-tenant payment (Tenant B payment requested by Tenant A admin)
    tenant_b_id, tenant_b_admin_id, token_b = await create_tenant_and_admin(
        conn, "Tenant B ISP", "admin_b_retry@test.com", "254711999914"
    )
    cust_b_id = await conn.fetchval(
        "INSERT INTO users (email, phone, hashed_password, role, tenant_id) VALUES ($1, $2, $3, 'customer', $4) RETURNING id",
        "customer_b2@test.com", "254711999915", hash_password(TEST_PASSWORD), UUID(tenant_b_id)
    )
    pkg_b_id = await conn.fetchval(
        "INSERT INTO packages (name, price_kes, duration_minutes, speed_mbps, created_by, tenant_id) VALUES ($1, $2, 1440, 10, $3, $4) RETURNING id",
        "B Daily 2", Decimal("50.00"), UUID(tenant_b_admin_id), UUID(tenant_b_id)
    )
    stuck_b_id = await conn.fetchval(
        """
        INSERT INTO payments (customer_id, package_id, amount_kes, status, phone_number, mpesa_checkout_id, tenant_id, created_at)
        VALUES ($1, $2, 50.00, 'confirmed', '254711999915', 'checkout-12', $3, NOW() - INTERVAL '3 minutes')
        RETURNING id
        """,
        cust_b_id, pkg_b_id, UUID(tenant_b_id)
    )
    resp = client.post(f"/api/v1/admin/payments/{stuck_b_id}/retry-provision", headers=headers_a)
    assert resp.status_code == 404

    # 5. Pending payment -> 400 Bad Request
    pending_id = await conn.fetchval(
        """
        INSERT INTO payments (customer_id, package_id, amount_kes, status, phone_number, mpesa_checkout_id, tenant_id, created_at)
        VALUES ($1, $2, 50.00, 'pending', '254708374149', 'checkout-13', $3, NOW() - INTERVAL '3 minutes')
        RETURNING id
        """,
        customer_id, package_id, UUID(DEFAULT_TENANT_ID)
    )
    resp = client.post(f"/api/v1/admin/payments/{pending_id}/retry-provision", headers=headers_a)
    assert resp.status_code == 400

    # 6. Payment already has voucher -> 400 Bad Request
    has_v_id = await conn.fetchval(
        """
        INSERT INTO payments (customer_id, package_id, amount_kes, status, phone_number, mpesa_checkout_id, tenant_id, created_at)
        VALUES ($1, $2, 50.00, 'confirmed', '254708374149', 'checkout-14', $3, NOW() - INTERVAL '3 minutes')
        RETURNING id
        """,
        customer_id, package_id, UUID(DEFAULT_TENANT_ID)
    )
    await conn.execute(
        """
        INSERT INTO vouchers (payment_id, customer_id, package_id, code, status, tenant_id)
        VALUES ($1, $2, $3, 'VOUCH3R999', 'active', $4)
        """,
        has_v_id, customer_id, package_id, UUID(DEFAULT_TENANT_ID)
    )
    resp = client.post(f"/api/v1/admin/payments/{has_v_id}/retry-provision", headers=headers_a)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reconcile_payments_cron(conn: asyncpg.Connection, db_pool: asyncpg.Pool):
    """Asserts that the reconcile cron job correctly selects and enqueues stuck payments."""
    customer_id, package_id = await get_test_customer_and_package_ids(conn)

    # 1. Stuck payment (Tenant A, confirmed, 3 mins old, no voucher)
    stuck_id = await conn.fetchval(
        """
        INSERT INTO payments (customer_id, package_id, amount_kes, status, phone_number, mpesa_checkout_id, tenant_id, created_at)
        VALUES ($1, $2, 50.00, 'confirmed', '254708374149', 'checkout-cron-1', $3, NOW() - INTERVAL '3 minutes')
        RETURNING id
        """,
        customer_id, package_id, UUID(DEFAULT_TENANT_ID)
    )

    # 2. Too recent payment (Tenant A, confirmed, 1 min old, no voucher)
    recent_id = await conn.fetchval(
        """
        INSERT INTO payments (customer_id, package_id, amount_kes, status, phone_number, mpesa_checkout_id, tenant_id, created_at)
        VALUES ($1, $2, 50.00, 'confirmed', '254708374149', 'checkout-cron-2', $3, NOW() - INTERVAL '1 minute')
        RETURNING id
        """,
        customer_id, package_id, UUID(DEFAULT_TENANT_ID)
    )

    # Create mock Redis client and worker context
    mock_redis = MagicMock()
    mock_redis.enqueue_job = AsyncMock()
    ctx = {
        "db_pool": db_pool,
        "redis": mock_redis,
    }

    # Call cron function directly
    await reconcile_payments_cron(ctx)

    # Verify stuck payment is enqueued, recent payment is not
    mock_redis.enqueue_job.assert_called_once_with(
        "generate_voucher_task",
        str(stuck_id),
        DEFAULT_TENANT_ID,
    )


@pytest.mark.asyncio
@patch("app.worker.generate_voucher")
async def test_generate_voucher_task(
    mock_generate_voucher,
    db_pool: asyncpg.Pool,
    conn: asyncpg.Connection,
):
    """
    Asserts that:
      1. A successful generate_voucher returns the code.
      2. Attempts 1-3 fail and raise arq.exceptions.Retry.
      3. Attempt 4 (final) fails and bubbles up the original exception.
      4. Wrong tenant_id aborts without calling generate_voucher.
    """
    customer_id, package_id = await get_test_customer_and_package_ids(conn)
    payment_id = await conn.fetchval(
        """
        INSERT INTO payments (customer_id, package_id, amount_kes, status, phone_number, tenant_id)
        VALUES ($1, $2, 50.00, 'confirmed', '254708374149', $3)
        RETURNING id
        """,
        customer_id,
        package_id,
        UUID(DEFAULT_TENANT_ID),
    )

    ctx = {"db_pool": db_pool}
    payment_id_str = str(payment_id)
    tenant_id_str = DEFAULT_TENANT_ID

    mock_generate_voucher.return_value = "ABCDEFGH22"
    ctx["job_try"] = 1
    code = await generate_voucher_task(ctx, payment_id_str, tenant_id_str)
    assert code == "ABCDEFGH22"
    mock_generate_voucher.assert_called_with(
        ANY,
        payment_id_str,
        UUID(DEFAULT_TENANT_ID),
        is_final_attempt=False,
    )
    mock_generate_voucher.reset_mock()

    mock_generate_voucher.side_effect = ValueError("MikroTik not reachable")
    ctx["job_try"] = 1
    with pytest.raises(Retry) as exc_info:
        await generate_voucher_task(ctx, payment_id_str, tenant_id_str)
    assert exc_info.value.defer_score == 5000
    mock_generate_voucher.reset_mock()

    ctx["job_try"] = 2
    with pytest.raises(Retry) as exc_info:
        await generate_voucher_task(ctx, payment_id_str, tenant_id_str)
    assert exc_info.value.defer_score == 15000
    mock_generate_voucher.reset_mock()

    ctx["job_try"] = 3
    with pytest.raises(Retry) as exc_info:
        await generate_voucher_task(ctx, payment_id_str, tenant_id_str)
    assert exc_info.value.defer_score == 45000
    mock_generate_voucher.reset_mock()

    ctx["job_try"] = 4
    with pytest.raises(ValueError, match="MikroTik not reachable"):
        await generate_voucher_task(ctx, payment_id_str, tenant_id_str)
    mock_generate_voucher.assert_called_with(
        ANY,
        payment_id_str,
        UUID(DEFAULT_TENANT_ID),
        is_final_attempt=True,
    )
    mock_generate_voucher.reset_mock()

    wrong_tenant = str(uuid4())
    result = await generate_voucher_task(ctx, payment_id_str, wrong_tenant)
    assert result is None
    mock_generate_voucher.assert_not_called()
