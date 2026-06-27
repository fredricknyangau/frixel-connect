"""
tests/modules/test_routers.py
==============================
Tests for router CRUD, cross-tenant isolation, fallback mechanisms,
and heartbeat status monitoring.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import asyncpg
from fastapi.testclient import TestClient

from app.core.security import hash_password, create_access_token, decrypt_secret
from app.modules.routers.service import router_heartbeat_loop
from app.modules.vouchers.service import generate_voucher


# ── Helper: create a tenant + admin user directly in DB ───────────────────────
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
        email, phone, hash_password("TestPassword123!"), tenant_id
    )
    token = create_access_token(user_id=str(user_id), role="admin", tenant_id=str(tenant_id))
    return str(tenant_id), str(user_id), token


@pytest.mark.asyncio
async def test_routers_crud(client: TestClient, conn: asyncpg.Connection):
    """Verifies that admins can register, retrieve, list, update, and delete routers, and credentials are encrypted."""
    # Setup Tenant A
    tenant_id, admin_id, token = await create_tenant_and_admin(
        conn, "Tenant ISP A", "admin_a_router@test.com", "254711999901"
    )
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create Router
    payload = {
        "name": "Router A",
        "host": "192.168.1.100",
        "port": 8728,
        "username": "admin",
        "password": "MikroTikPassword123",
        "site_name": "Main Site"
    }
    resp = client.post("/api/v1/admin/routers", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    router_id = data["id"]

    # Assert return fields
    assert data["name"] == "Router A"
    assert data["host"] == "192.168.1.100"
    assert data["port"] == 8728
    assert data["username"] == "admin"
    assert data["site_name"] == "Main Site"
    assert data["status"] == "unknown"
    assert data["tenant_id"] == tenant_id

    # Assert password is NOT returned in response
    assert "password" not in data
    assert "password_encrypted" not in data
    assert "password_decrypted" not in data

    # Check DB representation
    db_row = await conn.fetchrow("SELECT * FROM routers WHERE id = $1", router_id)
    assert db_row is not None
    assert db_row["password_encrypted"] != "MikroTikPassword123"
    assert decrypt_secret(db_row["password_encrypted"]) == "MikroTikPassword123"

    # 2. List Routers
    resp = client.get("/api/v1/admin/routers", headers=headers)
    assert resp.status_code == 200
    routers_list = resp.json()
    assert len(routers_list) == 1
    assert routers_list[0]["id"] == router_id
    assert "password" not in routers_list[0]
    assert "password_encrypted" not in routers_list[0]

    # 3. Get Router
    resp = client.get(f"/api/v1/admin/routers/{router_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == router_id
    assert "password" not in resp.json()

    # 4. Update Router (e.g. name, port, password)
    update_payload = {
        "name": "Router A Updated",
        "port": 8729,
        "password": "NewMikroTikPassword456"
    }
    resp = client.put(f"/api/v1/admin/routers/{router_id}", json=update_payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Router A Updated"
    assert data["port"] == 8729
    assert "password" not in data

    # Verify DB update
    db_row = await conn.fetchrow("SELECT * FROM routers WHERE id = $1", router_id)
    assert decrypt_secret(db_row["password_encrypted"]) == "NewMikroTikPassword456"

    # 5. Delete Router
    resp = client.delete(f"/api/v1/admin/routers/{router_id}", headers=headers)
    assert resp.status_code == 204

    # Verify deletion
    resp = client.get(f"/api/v1/admin/routers/{router_id}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_router_name_unique_per_tenant(client: TestClient, conn: asyncpg.Connection):
    """Verifies router name uniqueness is scoped per tenant."""
    tenant_id, admin_id, token = await create_tenant_and_admin(
        conn, "Tenant ISP B", "admin_b_router@test.com", "254711999902"
    )
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "name": "Router-Name-1",
        "host": "192.168.1.10",
        "port": 8728,
        "username": "admin",
        "password": "Password",
        "site_name": "Site 1"
    }
    # First create
    resp = client.post("/api/v1/admin/routers", json=payload, headers=headers)
    assert resp.status_code == 201

    # Try creating with duplicate name -> 409 Conflict
    resp = client.post("/api/v1/admin/routers", json=payload, headers=headers)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_routers_cross_tenant_isolation(client: TestClient, conn: asyncpg.Connection):
    """Verifies that Tenant B's admin cannot retrieve, update, or delete Tenant A's router config."""
    # Setup Tenant A
    tenant_a_id, admin_a_id, token_a = await create_tenant_and_admin(
        conn, "Tenant A", "admin_a_isolate@test.com", "254711999903"
    )
    # Setup Tenant B
    tenant_b_id, admin_b_id, token_b = await create_tenant_and_admin(
        conn, "Tenant B", "admin_b_isolate@test.com", "254711999904"
    )

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Tenant A creates router
    payload = {
        "name": "Router A",
        "host": "192.168.1.1",
        "port": 8728,
        "username": "admin",
        "password": "Password",
        "site_name": "Site A"
    }
    resp = client.post("/api/v1/admin/routers", json=payload, headers=headers_a)
    assert resp.status_code == 201
    router_a_id = resp.json()["id"]

    # Tenant B tries to retrieve Tenant A's router -> 404 Not Found (not 403)
    resp = client.get(f"/api/v1/admin/routers/{router_a_id}", headers=headers_b)
    assert resp.status_code == 404

    # Tenant B tries to update Tenant A's router -> 404 Not Found (not 403)
    update_payload = {"name": "Hacked Router"}
    resp = client.put(f"/api/v1/admin/routers/{router_a_id}", json=update_payload, headers=headers_b)
    assert resp.status_code == 404

    # Tenant B tries to delete Tenant A's router -> 404 Not Found (not 403)
    resp = client.delete(f"/api/v1/admin/routers/{router_a_id}", headers=headers_b)
    assert resp.status_code == 404

    # Verify Router A still exists in the database
    db_row = await conn.fetchrow("SELECT name FROM routers WHERE id = $1", router_a_id)
    assert db_row is not None
    assert db_row["name"] == "Router A"


@pytest.mark.asyncio
async def test_router_id_recorded_without_mikrotik_provisioning(conn: asyncpg.Connection):
    """Verifies that voucher generation records router_id while RADIUS remains authoritative."""
    # Setup Tenant + Package + Customer
    tenant_id, admin_id, token = await create_tenant_and_admin(
        conn, "Tenant Dynamic", "admin_dynamic@test.com", "254711999905"
    )

    # Create a customer
    customer_id = await conn.fetchval(
        """
        INSERT INTO users (email, phone, hashed_password, role, tenant_id)
        VALUES ($1, $2, $3, 'customer', $4)
        RETURNING id
        """,
        "dynamic_customer@test.com", "254711999906", hash_password("TestPassword123!"), tenant_id
    )

    # Create a package
    package_id = await conn.fetchval(
        """
        INSERT INTO packages (name, price_kes, duration_minutes, speed_mbps, created_by, tenant_id)
        VALUES ($1, 50.00, 1440, 10, $2, $3)
        RETURNING id
        """,
        "Daily Test Pkg", admin_id, tenant_id
    )

    # --- Case 1: Customer has NO router_id assigned ---
    payment_id_1 = await conn.fetchval(
        """
        INSERT INTO payments (customer_id, package_id, amount_kes, status, phone_number, tenant_id)
        VALUES ($1, $2, 50.00, 'pending', '254711999906', $3)
        RETURNING id
        """,
        customer_id, package_id, tenant_id
    )

    code_1 = await generate_voucher(conn, str(payment_id_1), UUID(tenant_id))
    assert code_1 is not None

    voucher_1 = await conn.fetchrow("SELECT router_id FROM vouchers WHERE payment_id = $1", payment_id_1)
    assert voucher_1["router_id"] is None

    # --- Case 2: Customer has a specific router_id assigned ---
    # First, register a router for this tenant
    router_id = await conn.fetchval(
        """
        INSERT INTO routers (tenant_id, name, host, port, username, password_encrypted, site_name, status)
        VALUES ($1, 'Site Router', '192.168.10.1', 8728, 'admin_user', 'ciphertext_key', 'Dynamic Site', 'online')
        RETURNING id
        """,
        tenant_id
    )

    # Update customer with this router_id
    await conn.execute("UPDATE users SET router_id = $1 WHERE id = $2", router_id, customer_id)

    payment_id_2 = await conn.fetchval(
        """
        INSERT INTO payments (customer_id, package_id, amount_kes, status, phone_number, tenant_id)
        VALUES ($1, $2, 50.00, 'pending', '254711999906', $3)
        RETURNING id
        """,
        customer_id, package_id, tenant_id
    )

    code_2 = await generate_voucher(conn, str(payment_id_2), UUID(tenant_id))
    assert code_2 is not None

    voucher_2 = await conn.fetchrow("SELECT router_id FROM vouchers WHERE payment_id = $1", payment_id_2)
    assert voucher_2["router_id"] == router_id

    radcheck_count = await conn.fetchval(
        "SELECT COUNT(*) FROM radcheck WHERE username IN ($1, $2)",
        code_1,
        code_2,
    )
    assert radcheck_count == 2


@pytest.mark.asyncio
@patch("app.modules.routers.service.get_mikrotik_client")
async def test_router_heartbeat_monitoring(mock_get_client, conn: asyncpg.Connection, db_pool: asyncpg.Pool):
    """Verifies that the heartbeat scheduled task marks unreachable routers as offline after 3 consecutive failures."""
    # Setup Tenant
    tenant_id, admin_id, token = await create_tenant_and_admin(
        conn, "Tenant Heartbeat", "admin_hb@test.com", "254711999907"
    )

    # Register Router 1 (will succeed)
    r1_id = await conn.fetchval(
        """
        INSERT INTO routers (tenant_id, name, host, port, username, password_encrypted, site_name, status)
        VALUES ($1, 'R1-Success', '192.168.1.1', 8728, 'admin', 'cipher', 'Site A', 'unknown')
        RETURNING id
        """,
        tenant_id
    )

    # Register Router 2 (will fail)
    r2_id = await conn.fetchval(
        """
        INSERT INTO routers (tenant_id, name, host, port, username, password_encrypted, site_name, status)
        VALUES ($1, 'R2-Fail', '192.168.1.2', 8728, 'admin', 'cipher', 'Site B', 'unknown')
        RETURNING id
        """,
        tenant_id
    )

    # Mock clients
    client_ok = MagicMock()
    client_ok.get_user_profile_names = AsyncMock(return_value=["default", "10Mbps"])

    client_fail = MagicMock()
    client_fail.get_user_profile_names = AsyncMock(side_effect=Exception("Connection timed out"))

    # When get_mikrotik_client is called, route based on host parameter
    def side_effect(router_dict):
        if router_dict and router_dict["host"] == "192.168.1.1":
            return client_ok
        return client_fail

    mock_get_client.side_effect = side_effect

    # Mock asyncio.sleep to run loop 3 times
    sleep_count = 0
    original_sleep = asyncio.sleep

    async def mock_sleep(seconds):
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count > 3:
            raise asyncio.CancelledError()
        await original_sleep(0.001)

    import app.database
    original_pool = app.database._pool
    app.database._pool = db_pool

    try:
        # Run the heartbeat loop
        with patch("asyncio.sleep", mock_sleep):
            await router_heartbeat_loop()
    finally:
        app.database._pool = original_pool

    # Verify Router 1 is online (succeeded on all attempts)
    r1 = await conn.fetchrow("SELECT status, last_heartbeat_at FROM routers WHERE id = $1", r1_id)
    assert r1["status"] == "online"
    assert r1["last_heartbeat_at"] is not None

    # Verify Router 2 is offline (failed 3 times)
    r2 = await conn.fetchrow("SELECT status, last_heartbeat_at FROM routers WHERE id = $1", r2_id)
    assert r2["status"] == "offline"
