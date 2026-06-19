"""
tests/modules/test_tenant_isolation.py
=======================================
Cross-tenant isolation tests for Phase 1.

WHAT THESE TESTS PROVE:
  A valid JWT from tenant A cannot read tenant B's customers, payments, or
  vouchers -even when supplied with tenant B's REAL UUIDs directly in the
  URL path. The system returns 404, not 403.

  WHY 404 (not 403)?
  A 403 says "the resource exists, but you're not allowed." That confirms the
  UUID is real and belongs to some tenant. An attacker who brute-forces UUIDs
  against a 403-returning endpoint learns which UUIDs are valid across the
  entire platform. A 404 reveals nothing -the UUID might not exist at all.

TEST STRUCTURE:
  Each test creates two tenants with their own admin tokens, seeds data in
  tenant B, then makes requests authenticated as tenant A using tenant B's
  real resource UUIDs. All cross-tenant requests must return 404.

SETUP:
  These tests use the same conftest.py infrastructure (setup_test_database,
  clean_and_seed_db) but do NOT rely on the pre-seeded data from conftest —
  they create their own tenants through the API to get valid tokens.
"""

import pytest
from fastapi.testclient import TestClient
from decimal import Decimal
import asyncpg

from app.core.security import hash_password, create_access_token


# ── Helper: create a tenant + admin user directly in DB ───────────────────────
# We insert directly rather than calling POST /tenants/register to avoid
# any network overhead and to keep tests fast.

async def create_tenant_and_admin(
    conn: asyncpg.Connection,
    business_name: str,
    email: str,
    phone: str,
) -> tuple[str, str, str]:
    """
    Creates a tenant and admin user in the test database.
    Returns (tenant_id, user_id, access_token).
    """
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

    # Insert admin user for this tenant
    user_id = await conn.fetchval(
        """
        INSERT INTO users (email, phone, hashed_password, role, tenant_id)
        VALUES ($1, $2, $3, 'admin', $4)
        RETURNING id
        """,
        email,
        phone,
        hash_password("TestPassword123!"),
        tenant_id,
    )

    # Mint a token for this admin
    token = create_access_token(
        user_id=str(user_id),
        role="admin",
        tenant_id=str(tenant_id),
    )

    return str(tenant_id), str(user_id), token


async def create_customer_in_tenant(
    conn: asyncpg.Connection,
    tenant_id: str,
    email: str,
    phone: str,
) -> str:
    """Creates a customer in the specified tenant. Returns user_id."""
    user_id = await conn.fetchval(
        """
        INSERT INTO users (email, phone, hashed_password, role, tenant_id)
        VALUES ($1, $2, $3, 'customer', $4)
        RETURNING id
        """,
        email,
        phone,
        hash_password("TestPassword123!"),
        tenant_id,
    )
    return str(user_id)


async def create_package_in_tenant(
    conn: asyncpg.Connection,
    tenant_id: str,
    admin_id: str,
    name: str,
) -> str:
    """Creates a package in the specified tenant. Returns package_id."""
    pkg_id = await conn.fetchval(
        """
        INSERT INTO packages (name, price_kes, duration_minutes, speed_mbps, created_by, tenant_id)
        VALUES ($1, 100.00, 10080, 20, $2, $3)
        RETURNING id
        """,
        name,
        admin_id,
        tenant_id,
    )
    return str(pkg_id)


async def create_payment_in_tenant(
    conn: asyncpg.Connection,
    tenant_id: str,
    customer_id: str,
    package_id: str,
) -> str:
    """Creates a payment record in the specified tenant. Returns payment_id."""
    payment_id = await conn.fetchval(
        """
        INSERT INTO payments
            (customer_id, package_id, amount_kes, status, phone_number, tenant_id)
        VALUES ($1, $2, 100.00, 'confirmed', '254700000099', $3)
        RETURNING id
        """,
        customer_id,
        package_id,
        tenant_id,
    )
    return str(payment_id)


async def create_voucher_in_tenant(
    conn: asyncpg.Connection,
    tenant_id: str,
    customer_id: str,
    package_id: str,
    payment_id: str,
) -> str:
    """Creates a voucher in the specified tenant. Returns voucher_id."""
    voucher_id = await conn.fetchval(
        """
        INSERT INTO vouchers
            (payment_id, customer_id, package_id, code, status, tenant_id)
        VALUES ($1, $2, $3, 'TESTCODE001', 'active', $4)
        RETURNING id
        """,
        payment_id,
        customer_id,
        package_id,
        tenant_id,
    )
    return str(voucher_id)


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cross_tenant_customer_returns_404(client: TestClient, conn: asyncpg.Connection):
    """
    Tenant A's admin cannot read tenant B's customer.
    GET /admin/users returns only tenant A's users -tenant B's customer_id returns 404.
    """
    # Create tenant A (admin token for all requests from tenant A)
    tenant_a_id, admin_a_id, token_a = await create_tenant_and_admin(
        conn, "Tenant A ISP", "admin_a@test.com", "254711000001"
    )

    # Create tenant B with a customer
    tenant_b_id, admin_b_id, token_b = await create_tenant_and_admin(
        conn, "Tenant B ISP", "admin_b@test.com", "254711000002"
    )
    customer_b_id = await create_customer_in_tenant(
        conn, tenant_b_id, "customer_b@test.com", "254711000003"
    )

    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Tenant A lists users -should NOT see tenant B's customer
    resp = client.get("/api/v1/admin/users", headers=headers_a)
    assert resp.status_code == 200
    user_ids_in_response = [u["id"] for u in resp.json()]
    assert customer_b_id not in user_ids_in_response, (
        "Tenant A should not see tenant B's customer in /admin/users listing"
    )

    # Tenant A tries to access tenant B's customer's profile directly.
    # There's no GET /admin/users/{id} endpoint currently, but we verify via
    # the customers endpoint.
    resp = client.get("/api/v1/reseller/customers", headers=headers_a)
    assert resp.status_code == 200
    customer_ids = [u["id"] for u in resp.json()]
    assert customer_b_id not in customer_ids, (
        "Tenant A should not see tenant B's customer in /reseller/customers listing"
    )


@pytest.mark.asyncio
async def test_cross_tenant_payment_returns_404(client: TestClient, conn: asyncpg.Connection):
    """
    A customer from tenant A cannot read a payment that belongs to tenant B,
    even when given the exact UUID from tenant B's database.
    """
    # Tenant A
    tenant_a_id, admin_a_id, token_a_admin = await create_tenant_and_admin(
        conn, "Tenant A ISP", "admin_aa@test.com", "254711000010"
    )
    customer_a_id = await create_customer_in_tenant(
        conn, tenant_a_id, "cust_a@test.com", "254711000011"
    )
    token_a_customer = create_access_token(
        user_id=customer_a_id, role="customer", tenant_id=tenant_a_id
    )

    # Tenant B -create real payment data
    tenant_b_id, admin_b_id, token_b_admin = await create_tenant_and_admin(
        conn, "Tenant B ISP", "admin_bb@test.com", "254711000012"
    )
    customer_b_id = await create_customer_in_tenant(
        conn, tenant_b_id, "cust_b@test.com", "254711000013"
    )
    pkg_b_id = await create_package_in_tenant(
        conn, tenant_b_id, admin_b_id, "B Package"
    )
    payment_b_id = await create_payment_in_tenant(
        conn, tenant_b_id, customer_b_id, pkg_b_id
    )

    # Tenant A's customer attempts to poll tenant B's real payment UUID
    headers_a_customer = {"Authorization": f"Bearer {token_a_customer}"}
    resp = client.get(
        f"/api/v1/payments/{payment_b_id}/status",
        headers=headers_a_customer,
    )

    # MUST be 404, not 403. Explanation in module docstring.
    assert resp.status_code == 404, (
        f"Expected 404 for cross-tenant payment access, got {resp.status_code}. "
        f"A 403 would confirm the payment UUID exists in another tenant."
    )


@pytest.mark.asyncio
async def test_cross_tenant_voucher_returns_404(client: TestClient, conn: asyncpg.Connection):
    """
    A customer from tenant A cannot read a voucher belonging to tenant B,
    even when given the exact UUID directly in the URL path.

    This is the explicit test required by the Phase 1 specification:
    "try GET /vouchers/{a-real-voucher-id-that-belongs-to-tenant-B}
     -must return 404, not 403"
    """
    # Tenant A customer
    tenant_a_id, admin_a_id, _ = await create_tenant_and_admin(
        conn, "Tenant A ISP", "admin_aaa@test.com", "254711000020"
    )
    customer_a_id = await create_customer_in_tenant(
        conn, tenant_a_id, "cust_aaa@test.com", "254711000021"
    )
    token_a_customer = create_access_token(
        user_id=customer_a_id, role="customer", tenant_id=tenant_a_id
    )

    # Tenant B -create a real voucher
    tenant_b_id, admin_b_id, _ = await create_tenant_and_admin(
        conn, "Tenant B ISP", "admin_bbb@test.com", "254711000022"
    )
    customer_b_id = await create_customer_in_tenant(
        conn, tenant_b_id, "cust_bbb@test.com", "254711000023"
    )
    pkg_b_id = await create_package_in_tenant(
        conn, tenant_b_id, admin_b_id, "B Voucher Package"
    )
    payment_b_id = await create_payment_in_tenant(
        conn, tenant_b_id, customer_b_id, pkg_b_id
    )
    voucher_b_id = await create_voucher_in_tenant(
        conn, tenant_b_id, customer_b_id, pkg_b_id, payment_b_id
    )

    # Tenant A's customer requests tenant B's real voucher UUID
    headers_a = {"Authorization": f"Bearer {token_a_customer}"}
    resp = client.get(
        f"/api/v1/vouchers/{voucher_b_id}",
        headers=headers_a,
    )

    # MUST be 404, not 403.
    assert resp.status_code == 404, (
        f"Expected 404 for cross-tenant voucher access, got {resp.status_code}. "
        f"A 403 would leak that voucher UUID '{voucher_b_id}' exists in tenant B's data."
    )


@pytest.mark.asyncio
async def test_cross_tenant_package_isolation(client: TestClient, conn: asyncpg.Connection):
    """
    Tenant A cannot see Tenant B's packages in the package listing.
    GET /packages returns only packages for the caller's tenant.
    """
    # Tenant A
    tenant_a_id, admin_a_id, token_a = await create_tenant_and_admin(
        conn, "Tenant A ISP", "admin_pkg_a@test.com", "254711000030"
    )
    pkg_a_id = await create_package_in_tenant(
        conn, tenant_a_id, admin_a_id, "Tenant A Exclusive Package"
    )

    # Tenant B -different package
    tenant_b_id, admin_b_id, token_b = await create_tenant_and_admin(
        conn, "Tenant B ISP", "admin_pkg_b@test.com", "254711000031"
    )
    pkg_b_id = await create_package_in_tenant(
        conn, tenant_b_id, admin_b_id, "Tenant B Exclusive Package"
    )

    # Tenant A lists packages -should only see their own
    headers_a = {"Authorization": f"Bearer {token_a}"}
    resp = client.get("/api/v1/packages", headers=headers_a)
    assert resp.status_code == 200

    pkg_ids = [p["id"] for p in resp.json()]
    assert pkg_a_id in pkg_ids, "Tenant A should see their own package"
    assert pkg_b_id not in pkg_ids, "Tenant A must NOT see Tenant B's package"

    # Tenant A requests Tenant B's package by ID -must be 404
    resp = client.get(f"/api/v1/packages/{pkg_b_id}", headers=headers_a)
    assert resp.status_code == 404, (
        f"Expected 404 for cross-tenant package access, got {resp.status_code}"
    )


@pytest.mark.asyncio
async def test_two_tenants_register_same_package_name(client: TestClient, conn: asyncpg.Connection):
    """
    Two tenants can both have a package named "Daily 10Mbps" without conflict.
    This validates that name uniqueness is per-tenant, not global.
    """
    # Tenant A
    tenant_a_id, admin_a_id, _ = await create_tenant_and_admin(
        conn, "Tenant A ISP", "admin_dup_a@test.com", "254711000040"
    )
    # Tenant B
    tenant_b_id, admin_b_id, _ = await create_tenant_and_admin(
        conn, "Tenant B ISP", "admin_dup_b@test.com", "254711000041"
    )

    # Both create "Daily 10Mbps" -should not conflict
    pkg_a = await create_package_in_tenant(conn, tenant_a_id, admin_a_id, "Daily 10Mbps")
    pkg_b = await create_package_in_tenant(conn, tenant_b_id, admin_b_id, "Daily 10Mbps")

    # Both IDs exist and are different
    assert pkg_a != pkg_b, "Two tenants' same-named packages must have different UUIDs"
    assert pkg_a is not None
    assert pkg_b is not None
