from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import UUID

import asyncpg
import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.modules.vouchers.service import generate_voucher
from tests.conftest import DEFAULT_TENANT_ID, TEST_PASSWORD


async def _seed_customer_subscription(conn: asyncpg.Connection):
    customer = await conn.fetchrow("SELECT id FROM users WHERE email = $1", "customer@zealsync.dev")
    package = await conn.fetchrow("SELECT id FROM packages WHERE name = $1", "Daily 10Mbps")
    sub_id = await conn.fetchval(
        """
        INSERT INTO subscriptions (tenant_id, customer_id, package_id, current_period_end, auto_renew)
        VALUES ($1, $2, $3, $4, TRUE)
        RETURNING id
        """,
        UUID(DEFAULT_TENANT_ID),
        customer["id"],
        package["id"],
        datetime.now(timezone.utc) + timedelta(days=30),
    )
    token = create_access_token(
        user_id=str(customer["id"]),
        role="customer",
        tenant_id=DEFAULT_TENANT_ID,
    )
    return sub_id, customer["id"], package["id"], token


def _admin_headers(conn_user_id: str) -> dict:
    token = create_access_token(
        user_id=conn_user_id,
        role="admin",
        tenant_id=DEFAULT_TENANT_ID,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_reseller_endpoint(client: TestClient, conn: asyncpg.Connection):
    admin_id = await conn.fetchval("SELECT id FROM users WHERE email = $1", "admin@zealsync.dev")
    reseller_id = await conn.fetchval("SELECT id FROM users WHERE email = $1", "reseller@zealsync.dev")
    customer_id = await conn.fetchval("SELECT id FROM users WHERE email = $1", "customer@zealsync.dev")

    resp = client.post(
        "/api/v1/admin/resellers",
        json={
            "email": "new_reseller@zealsync.dev",
            "phone": "254711123456",
            "password": TEST_PASSWORD,
        },
        headers=_admin_headers(str(admin_id)),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["role"] == "reseller"
    assert data["tenant_id"] == DEFAULT_TENANT_ID

    reseller_token = create_access_token(str(reseller_id), "reseller", DEFAULT_TENANT_ID)
    customer_token = create_access_token(str(customer_id), "customer", DEFAULT_TENANT_ID)

    forbidden_payload = {
        "email": "blocked_reseller@zealsync.dev",
        "phone": "254711123457",
        "password": TEST_PASSWORD,
    }
    assert client.post(
        "/api/v1/admin/resellers",
        json=forbidden_payload,
        headers={"Authorization": f"Bearer {reseller_token}"},
    ).status_code == 403
    assert client.post(
        "/api/v1/admin/resellers",
        json=forbidden_payload,
        headers={"Authorization": f"Bearer {customer_token}"},
    ).status_code == 403


@pytest.mark.asyncio
async def test_customer_subscription_me_get_and_update(client: TestClient, conn: asyncpg.Connection):
    _, _, package_id, token = await _seed_customer_subscription(conn)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/v1/subscriptions/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["package_id"] == str(package_id)
    assert data["package_name"] == "Daily 10Mbps"
    assert data["auto_renew"] is True

    resp = client.put("/api/v1/subscriptions/me", json={"auto_renew": False}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["auto_renew"] is False

    stored = await conn.fetchval("SELECT auto_renew FROM subscriptions WHERE id = $1", UUID(data["id"]))
    assert stored is False


@pytest.mark.asyncio
async def test_customer_invoices_me_are_scoped(client: TestClient, conn: asyncpg.Connection):
    customer_id = await conn.fetchval("SELECT id FROM users WHERE email = $1", "customer@zealsync.dev")
    package_id = await conn.fetchval("SELECT id FROM packages WHERE name = $1", "Daily 10Mbps")
    payment_id = await conn.fetchval(
        """
        INSERT INTO payments (tenant_id, customer_id, package_id, amount_kes, status, mpesa_receipt_number, phone_number)
        VALUES ($1, $2, $3, 50.00, 'confirmed', 'INVME001', '254700000003')
        RETURNING id
        """,
        UUID(DEFAULT_TENANT_ID),
        customer_id,
        package_id,
    )
    invoice_id = await conn.fetchval(
        "INSERT INTO invoices (tenant_id, payment_id) VALUES ($1, $2) RETURNING id",
        UUID(DEFAULT_TENANT_ID),
        payment_id,
    )

    token = create_access_token(str(customer_id), "customer", DEFAULT_TENANT_ID)
    resp = client.get("/api/v1/invoices/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert [item["id"] for item in data] == [str(invoice_id)]
    assert data[0]["amount_kes"] == 50


@pytest.mark.asyncio
async def test_tenant_me_includes_usage_and_billing_fields(client: TestClient, conn: asyncpg.Connection):
    admin_id = await conn.fetchval("SELECT id FROM users WHERE email = $1", "admin@zealsync.dev")
    resp = client.get("/api/v1/tenants/me", headers=_admin_headers(str(admin_id)))

    assert resp.status_code == 200
    data = resp.json()
    assert data["current_customer_count"] == 1
    assert data["billing_status"] == "active"
    assert data["next_billing_date"] is not None


@pytest.mark.asyncio
@patch("app.modules.tenants.service.daraja_client")
async def test_tenant_billing_pay_now_creates_platform_payment(
    mock_daraja,
    client: TestClient,
    conn: asyncpg.Connection,
):
    mock_daraja.stk_push = AsyncMock(return_value={"CheckoutRequestID": "PLATFORM-CHECKOUT-1"})
    admin_id = await conn.fetchval("SELECT id FROM users WHERE email = $1", "admin@zealsync.dev")

    resp = client.post("/api/v1/tenants/me/billing/pay-now", headers=_admin_headers(str(admin_id)))
    assert resp.status_code == 202
    data = resp.json()
    assert data["tenant_id"] == DEFAULT_TENANT_ID
    assert data["status"] == "pending"
    assert data["mpesa_checkout_id"] == "PLATFORM-CHECKOUT-1"

    stored = await conn.fetchrow(
        "SELECT tenant_id, mpesa_checkout_id FROM platform_payments WHERE id = $1",
        UUID(data["id"]),
    )
    assert str(stored["tenant_id"]) == DEFAULT_TENANT_ID
    assert stored["mpesa_checkout_id"] == "PLATFORM-CHECKOUT-1"


@pytest.mark.asyncio
@patch("app.integrations.mikrotik.MikroTikClient.generate_hotspot_user")
async def test_voucher_generation_does_not_call_mikrotik_hotspot_user(
    mock_generate_hotspot_user,
    conn: asyncpg.Connection,
):
    customer_id = await conn.fetchval("SELECT id FROM users WHERE email = $1", "customer@zealsync.dev")
    package_id = await conn.fetchval("SELECT id FROM packages WHERE name = $1", "Daily 10Mbps")
    payment_id = await conn.fetchval(
        """
        INSERT INTO payments (tenant_id, customer_id, package_id, amount_kes, status, phone_number)
        VALUES ($1, $2, $3, 50.00, 'confirmed', '254700000003')
        RETURNING id
        """,
        UUID(DEFAULT_TENANT_ID),
        customer_id,
        package_id,
    )

    code = await generate_voucher(conn, str(payment_id), is_final_attempt=True)
    mock_generate_hotspot_user.assert_not_called()

    radcheck_count = await conn.fetchval("SELECT COUNT(*) FROM radcheck WHERE username = $1", code)
    assert radcheck_count == 1
