"""
app/modules/tenants/service.py
================================
Business logic for tenant registration and retrieval.

WHY register_tenant MUST BE ONE TRANSACTION:
  A tenant row and its first admin user must be created atomically.
  If we create the tenant and then the user INSERT fails (e.g. email
  conflict from a race condition), we are left with a tenant that has
  no admin user at all. That tenant is an orphaned, unusable record:
  no one can log into it, no one can delete it through the API, and
  the owner has no way to access their account. A full ROLLBACK on
  failure guarantees we never enter this state.

  The "what if both succeed but the response is lost in transit?" case
  is handled by the UNIQUE constraint on owner_email: the ISP owner can
  safely retry registration and the second attempt will get a
  ConflictException(409) rather than silently creating a duplicate tenant.
"""

from uuid import UUID

import asyncpg

from app.core.exceptions import ConflictException, NotFoundException
from app.core.security import hash_password
from app.modules.tenants.schemas import TenantRegisterRequest


# Default subscription tier limits
TIER_MAX_CUSTOMERS = {
    "starter":    50,
    "growth":     500,
    "scale":      5000,
    "enterprise": 999999,
}


async def register_tenant(
    conn: asyncpg.Connection,
    data: TenantRegisterRequest,
) -> dict:
    """
    Creates a tenant and its first admin user in a single database transaction.

    Steps:
      1. Check owner_email uniqueness in tenants (readable error before DB constraint fires)
      2. Check email uniqueness in users (same reason)
      3. Open a transaction
      4. INSERT into tenants
      5. INSERT into users with role='admin' and tenant_id pointing to the new tenant
      6. Return both rows

    Returns a dict with keys: "tenant" and "user"
    """

    # ── Pre-flight uniqueness checks ─────────────────────────────────────────
    # Check tenants.owner_email first — this is the most likely conflict.
    existing_tenant = await conn.fetchrow(
        "SELECT id FROM tenants WHERE owner_email = $1",
        str(data.owner_email),
    )
    if existing_tenant:
        raise ConflictException(
            f"A tenant account with email '{data.owner_email}' already exists."
        )

    # Also check users.email — the admin user we're about to create must not
    # conflict with a user in another tenant. The users.email UNIQUE constraint
    # is global (not per-tenant) to prevent cross-tenant email confusion.
    # NOTE: after Phase 1 this constraint might be revisited to be per-tenant,
    # but for now global uniqueness is simpler and safer.
    existing_user = await conn.fetchrow(
        "SELECT id FROM users WHERE email = $1",
        str(data.owner_email),
    )
    if existing_user:
        raise ConflictException(
            f"A user account with email '{data.owner_email}' already exists."
        )

    # Also check phone uniqueness in tenants
    existing_phone = await conn.fetchrow(
        "SELECT id FROM tenants WHERE owner_phone = $1",
        data.owner_phone,
    )
    if existing_phone:
        raise ConflictException(
            f"A tenant account with phone '{data.owner_phone}' already exists."
        )

    # ── Hash the password before the transaction ──────────────────────────────
    # bcrypt takes ~100ms. We do this outside the transaction to keep the
    # transaction as short as possible. Long transactions hold locks.
    hashed = hash_password(data.password)

    # ── Single transaction: create tenant + admin user ────────────────────────
    async with conn.transaction():
        # 1. Create the tenant
        tenant_row = await conn.fetchrow(
            """
            INSERT INTO tenants (
                business_name, owner_email, owner_phone,
                subscription_tier, max_customers, status
            )
            VALUES ($1, $2, $3, 'starter', $4, 'active')
            RETURNING id, business_name, owner_email, owner_phone,
                      subscription_tier, max_customers, status, created_at
            """,
            data.business_name,
            str(data.owner_email),
            data.owner_phone,
            TIER_MAX_CUSTOMERS["starter"],
        )

        tenant_id = tenant_row["id"]

        # 2. Create the admin user belonging to this tenant.
        #    The admin user's email = the tenant's owner_email — same person.
        #    reseller_id = NULL for admin users (they have no parent reseller).
        user_row = await conn.fetchrow(
            """
            INSERT INTO users (
                email, phone, hashed_password, role, reseller_id, tenant_id
            )
            VALUES ($1, $2, $3, 'admin', NULL, $4)
            RETURNING id, email, phone, role, reseller_id, tenant_id,
                      is_active, created_at
            """,
            str(data.owner_email),
            data.owner_phone,
            hashed,
            tenant_id,
        )

    return {
        "tenant": dict(tenant_row),
        "user": dict(user_row),
    }


async def get_tenant_by_id(
    conn: asyncpg.Connection,
    tenant_id: UUID,
) -> dict:
    """
    Fetches a single tenant by UUID.
    Raises NotFoundException if not found.
    """
    row = await conn.fetchrow(
        """
        SELECT id, business_name, owner_email, owner_phone,
               subscription_tier, max_customers, status, created_at
        FROM tenants
        WHERE id = $1
        """,
        tenant_id,
    )
    if not row:
        raise NotFoundException("Tenant", str(tenant_id))
    return dict(row)


async def get_tenant_stats(
    conn: asyncpg.Connection,
    tenant_id: UUID,
) -> dict:
    """
    Returns aggregate stats for a tenant's dashboard:
      - active_customers: number of users with role='customer' and is_active=True
      - total_packages: number of active packages
    Used by GET /tenants/me to show the admin their usage vs their tier limit.
    """
    active_customers = await conn.fetchval(
        """
        SELECT COUNT(*)
        FROM users
        WHERE tenant_id = $1
          AND role = 'customer'
          AND is_active = TRUE
        """,
        tenant_id,
    )
    total_packages = await conn.fetchval(
        """
        SELECT COUNT(*)
        FROM packages
        WHERE tenant_id = $1
          AND is_active = TRUE
        """,
        tenant_id,
    )
    return {
        "active_customers": active_customers,
        "total_packages": total_packages,
    }
