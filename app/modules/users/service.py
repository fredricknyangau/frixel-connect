"""
app/modules/users/service.py
============================
Business logic and database interactions for the users module.

MULTI-TENANCY CHANGE (Phase 1):
  Every function that reads users from the database now requires tenant_id
  and adds AND tenant_id = $N to every WHERE clause.

  WHY is tenant_id in EVERY query?
  Without it, an admin from tenant A who somehow obtains a user UUID from
  tenant B (e.g., by brute-forcing UUIDs or via a bug in another endpoint)
  could read or modify that user. Adding tenant_id to the WHERE clause means
  the query returns zero rows for cross-tenant UUIDs — the same result as if
  the user didn't exist at all. We return 404, not 403, for this case.

  WHY 404 and not 403?
  A 403 says "I found the resource, but you can't have it." That confirms the
  resource exists — leaking that tenant B has a user with that UUID. A 404 says
  "no such resource in your context." An attacker learns nothing about whether
  tenant B's data exists at all. This is sometimes called "security through
  plausible deniability" and is standard practice in multi-tenant APIs.
"""

from uuid import UUID
from typing import Optional

import asyncpg

from app.core.exceptions import NotFoundException, ConflictException
from app.core.security import hash_password
from app.modules.users.schemas import CreateCustomerRequest, UserUpdate, AdminUserCreate, AdminUserUpdate


async def get_my_profile(
    conn: asyncpg.Connection,
    user_id: UUID,
    tenant_id: UUID,
) -> dict:
    """
    Retrieves the profile for a single user, scoped to the caller's tenant.

    Raises NotFoundException if:
      - The user doesn't exist at all.
      - The user exists but belongs to a different tenant (same 404 — no leakage).
    """
    row = await conn.fetchrow(
        """
        SELECT id, email, phone, role, reseller_id, tenant_id, is_active, created_at
        FROM users
        WHERE id = $1
          AND tenant_id = $2
        """,
        user_id,
        tenant_id,
    )
    if not row:
        raise NotFoundException("User", str(user_id))

    return dict(row)


async def update_my_profile(
    conn: asyncpg.Connection,
    user_id: UUID,
    tenant_id: UUID,
    data: UserUpdate,
) -> dict:
    """
    Updates a customer's own phone number, scoped to their tenant.
    """
    # Fetch current profile (also validates ownership + tenant membership)
    user = await get_my_profile(conn, user_id, tenant_id)

    if data.phone is not None and data.phone != user["phone"]:
        # Phone uniqueness within the same tenant
        existing = await conn.fetchrow(
            """
            SELECT id FROM users
            WHERE phone = $1
              AND tenant_id = $2
              AND id != $3
            """,
            data.phone,
            tenant_id,
            user_id,
        )
        if existing:
            raise ConflictException("An account with this phone number already exists.")

        row = await conn.fetchrow(
            """
            UPDATE users
            SET phone = $1, updated_at = NOW()
            WHERE id = $2 AND tenant_id = $3
            RETURNING id, email, phone, role, reseller_id, tenant_id, is_active, created_at
            """,
            data.phone,
            user_id,
            tenant_id,
        )
        return dict(row)

    return user


async def list_customers(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    caller_role: str,
    caller_id: UUID,
) -> list[dict]:
    """
    Returns customers scoped to the caller's tenant.

    Visibility:
      - Admin:    all customers in this tenant.
      - Reseller: only customers they created (reseller_id = caller_id),
                  AND still within the same tenant.
    """
    if caller_role == "admin":
        rows = await conn.fetch(
            """
            SELECT id, email, phone, role, reseller_id, tenant_id, is_active, created_at
            FROM users
            WHERE tenant_id = $1
              AND role = 'customer'
            ORDER BY created_at DESC
            """,
            tenant_id,
        )
    else:
        rows = await conn.fetch(
            """
            SELECT id, email, phone, role, reseller_id, tenant_id, is_active, created_at
            FROM users
            WHERE tenant_id = $1
              AND role = 'customer'
              AND reseller_id = $2
            ORDER BY created_at DESC
            """,
            tenant_id,
            caller_id,
        )

    return [dict(row) for row in rows]


async def create_customer(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    data: CreateCustomerRequest,
    reseller_id: Optional[UUID],
) -> dict:
    """
    Creates a new customer under the given tenant.

    tenant_id comes from the calling reseller or admin's JWT — the caller
    cannot create a customer in a different tenant.
    """
    # Check for email/phone conflicts within this tenant
    existing = await conn.fetchrow(
        """
        SELECT id, email, phone FROM users
        WHERE (email = $1 OR phone = $2)
          AND tenant_id = $3
        """,
        data.email,
        data.phone,
        tenant_id,
    )
    if existing:
        if existing["email"] == data.email:
            raise ConflictException("An account with this email address already exists.")
        else:
            raise ConflictException("An account with this phone number already exists.")

    hashed = hash_password(data.password)

    user = await conn.fetchrow(
        """
        INSERT INTO users (email, phone, hashed_password, role, reseller_id, tenant_id)
        VALUES ($1, $2, $3, 'customer', $4, $5)
        RETURNING id, email, phone, role, reseller_id, tenant_id, is_active, created_at
        """,
        data.email,
        data.phone,
        hashed,
        reseller_id,
        tenant_id,
    )

    return dict(user)


async def list_all_users(
    conn: asyncpg.Connection,
    tenant_id: UUID,
) -> list[dict]:
    """Lists every user in the tenant (admin only)."""
    rows = await conn.fetch(
        """
        SELECT id, email, phone, role, reseller_id, tenant_id, is_active, created_at
        FROM users
        WHERE tenant_id = $1
        ORDER BY created_at DESC
        """,
        tenant_id,
    )
    return [dict(row) for row in rows]


async def admin_create_user(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    data: AdminUserCreate,
) -> dict:
    """Admin creates a user of any role within the tenant."""
    existing = await conn.fetchrow(
        """
        SELECT id, email, phone FROM users
        WHERE (email = $1 OR phone = $2)
          AND tenant_id = $3
        """,
        data.email,
        data.phone,
        tenant_id,
    )
    if existing:
        if existing["email"] == data.email:
            raise ConflictException("An account with this email address already exists.")
        else:
            raise ConflictException("An account with this phone number already exists.")

    hashed = hash_password(data.password)

    user = await conn.fetchrow(
        """
        INSERT INTO users (email, phone, hashed_password, role, reseller_id, tenant_id)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id, email, phone, role, reseller_id, tenant_id, is_active, created_at
        """,
        data.email,
        data.phone,
        hashed,
        data.role,
        data.reseller_id,
        tenant_id,
    )
    return dict(user)


async def admin_update_user(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    user_id: UUID,
    data: AdminUserUpdate,
) -> dict:
    """Admin partially updates a user within the tenant."""
    # Confirm user exists in this tenant
    current = await conn.fetchrow(
        "SELECT * FROM users WHERE id = $1 AND tenant_id = $2",
        user_id,
        tenant_id,
    )
    if not current:
        raise NotFoundException("User", str(user_id))

    update_data = data.model_dump(exclude_unset=True)

    if "password" in update_data:
        update_data["hashed_password"] = hash_password(update_data.pop("password"))

    if "email" in update_data and update_data["email"] != current["email"]:
        existing = await conn.fetchrow(
            "SELECT id FROM users WHERE email = $1 AND tenant_id = $2 AND id != $3",
            update_data["email"],
            tenant_id,
            user_id,
        )
        if existing:
            raise ConflictException("Email already in use.")

    if "phone" in update_data and update_data["phone"] != current["phone"]:
        existing = await conn.fetchrow(
            "SELECT id FROM users WHERE phone = $1 AND tenant_id = $2 AND id != $3",
            update_data["phone"],
            tenant_id,
            user_id,
        )
        if existing:
            raise ConflictException("Phone already in use.")

    if not update_data:
        row = await conn.fetchrow(
            """
            SELECT id, email, phone, role, reseller_id, tenant_id, is_active, created_at
            FROM users WHERE id = $1 AND tenant_id = $2
            """,
            user_id,
            tenant_id,
        )
        return dict(row)

    # Build dynamic SET clause
    set_clauses = []
    values = []
    for i, (key, value) in enumerate(update_data.items(), start=1):
        set_clauses.append(f"{key} = ${i}")
        values.append(value)

    # updated_at always refreshed
    set_clauses.append("updated_at = NOW()")
    values.extend([user_id, tenant_id])

    query = f"""
        UPDATE users
        SET {', '.join(set_clauses)}
        WHERE id = ${len(values) - 1} AND tenant_id = ${len(values)}
        RETURNING id, email, phone, role, reseller_id, tenant_id, is_active, created_at
    """

    row = await conn.fetchrow(query, *values)
    return dict(row)


async def admin_deactivate_user(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    user_id: UUID,
) -> None:
    """Soft-deactivates a user within the tenant."""
    row = await conn.fetchrow(
        "SELECT id FROM users WHERE id = $1 AND tenant_id = $2",
        user_id,
        tenant_id,
    )
    if not row:
        raise NotFoundException("User", str(user_id))

    await conn.execute(
        "UPDATE users SET is_active = FALSE, updated_at = NOW() WHERE id = $1 AND tenant_id = $2",
        user_id,
        tenant_id,
    )


async def export_customer_data(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    user_id: UUID,
) -> dict:
    """Exports all PII tied to a customer."""
    user = await conn.fetchrow(
        "SELECT id, email, phone, role, created_at FROM users WHERE id = $1 AND tenant_id = $2",
        user_id, tenant_id
    )
    if not user:
        raise NotFoundException("User", str(user_id))
        
    payments = await conn.fetch(
        "SELECT id, amount_kes, status, mpesa_receipt_number, phone_number, created_at FROM payments WHERE customer_id = $1",
        user_id
    )
    
    vouchers = await conn.fetch(
        "SELECT id, code, status, expires_at, created_at FROM vouchers WHERE customer_id = $1",
        user_id
    )
    
    subscriptions = await conn.fetch(
        "SELECT id, status, current_period_end FROM subscriptions WHERE customer_id = $1",
        user_id
    )
    
    return {
        "user": dict(user),
        "payments": [dict(p) for p in payments],
        "vouchers": [dict(v) for v in vouchers],
        "subscriptions": [dict(s) for s in subscriptions]
    }


async def anonymize_customer(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    user_id: UUID,
) -> None:
    """Anonymizes a customer's PII without deleting financial records."""
    user = await conn.fetchrow(
        "SELECT id, role FROM users WHERE id = $1 AND tenant_id = $2",
        user_id, tenant_id
    )
    if not user:
        raise NotFoundException("User", str(user_id))
        
    anon_email = f"deleted-{user_id}@anonymized.local"
    anon_phone = f"del-{str(user_id)[:8]}"
    
    await conn.execute(
        """
        UPDATE users 
        SET email = $1, phone = $2, is_active = FALSE, hashed_password = 'DELETED', updated_at = NOW()
        WHERE id = $3 AND tenant_id = $4
        """,
        anon_email, anon_phone, user_id, tenant_id
    )
    
    # Revoke refresh tokens
    await conn.execute("UPDATE refresh_tokens SET revoked = TRUE WHERE user_id = $1", user_id)
