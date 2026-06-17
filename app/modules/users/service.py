"""
app/modules/users/service.py
============================
Business logic and database interactions for the users module.

This layer sits between the HTTP router and raw database queries, encapsulating
database transaction logic, data mapping, and authorization checks.
"""

from uuid import UUID
from typing import Optional

import asyncpg

from app.core.exceptions import NotFoundException, ConflictException
from app.core.security import hash_password
from app.modules.users.schemas import CreateCustomerRequest, UserUpdate


async def get_my_profile(conn: asyncpg.Connection, user_id: UUID) -> dict:
    """
    Retrieves the complete profile for a single user by ID.

    Raises:
        NotFoundException: If the user record cannot be found.
    """
    row = await conn.fetchrow(
        """
        SELECT id, email, phone, role, reseller_id, is_active, created_at
        FROM users
        WHERE id = $1
        """,
        user_id,
    )
    if not row:
        raise NotFoundException("User", str(user_id))

    return dict(row)


async def update_my_profile(
    conn: asyncpg.Connection,
    user_id: UUID,
    data: UserUpdate,
) -> dict:
    """
    Updates the contact information of a customer (phone number).

    Why restrict customer updates to phone number?
    Customers should not be allowed to self-modify credentials such as email,
    role, or active status (which could bypass billing or deactivation logic).
    Admin actions are performed through administrative commands, not self-service routes.

    Validation:
        - Verifies that the new phone number is not already in use by another user
          to avoid violating the database unique constraint and causing dirty states.
    """
    # 1. Fetch current profile to ensure user exists
    user = await get_my_profile(conn, user_id)

    # 2. Check if a new, different phone number is requested
    if data.phone is not None and data.phone != user["phone"]:
        # Verify the phone is unique across other users
        existing = await conn.fetchrow(
            "SELECT id FROM users WHERE phone = $1 AND id != $2",
            data.phone,
            user_id,
        )
        if existing:
            raise ConflictException("An account with this phone number already exists.")

        # Update the user profile with the new phone number
        row = await conn.fetchrow(
            """
            UPDATE users
            SET phone = $1, updated_at = NOW()
            WHERE id = $2
            RETURNING id, email, phone, role, reseller_id, is_active, created_at
            """,
            data.phone,
            user_id,
        )
        return dict(row)

    # If the phone was not updated, return the original profile row
    return user


async def list_customers(
    conn: asyncpg.Connection,
    caller_role: str,
    caller_id: UUID,
) -> list[dict]:
    """
    Returns a list of customer accounts.

    Visibility mapping:
        - Admin: Can see all customers in the system.
        - Reseller: Can only see customer profiles they registered (where reseller_id = caller_id).
    """
    if caller_role == "admin":
        rows = await conn.fetch(
            """
            SELECT id, email, phone, role, reseller_id, is_active, created_at
            FROM users
            WHERE role = 'customer'
            ORDER BY created_at DESC
            """
        )
    else:
        rows = await conn.fetch(
            """
            SELECT id, email, phone, role, reseller_id, is_active, created_at
            FROM users
            WHERE role = 'customer' AND reseller_id = $1
            ORDER BY created_at DESC
            """,
            caller_id,
        )

    return [dict(row) for row in rows]


async def create_customer(
    conn: asyncpg.Connection,
    data: CreateCustomerRequest,
    reseller_id: Optional[UUID],
) -> dict:
    """
    Creates a new customer record under a specific reseller.

    Validation:
        - Ensures neither email nor phone is already registered.
        - Hashes password using bcrypt.
        - Sets the role to 'customer' explicitly.
    """
    # 1. Check for email or phone conflicts
    existing = await conn.fetchrow(
        "SELECT id, email, phone FROM users WHERE email = $1 OR phone = $2",
        data.email,
        data.phone,
    )
    if existing:
        if existing["email"] == data.email:
            raise ConflictException("An account with this email address already exists.")
        else:
            raise ConflictException("An account with this phone number already exists.")

    # 2. Hash the customer password using bcrypt (standard security practice)
    hashed = hash_password(data.password)

    # 3. Create the customer record
    user = await conn.fetchrow(
        """
        INSERT INTO users (email, phone, hashed_password, role, reseller_id)
        VALUES ($1, $2, $3, 'customer', $4)
        RETURNING id, email, phone, role, reseller_id, is_active, created_at
        """,
        data.email,
        data.phone,
        hashed,
        reseller_id,
    )

    return dict(user)


async def list_all_users(conn: asyncpg.Connection) -> list[dict]:
    """
    Lists every user in the database (admin only).
    """
    rows = await conn.fetch(
        """
        SELECT id, email, phone, role, reseller_id, is_active, created_at
        FROM users
        ORDER BY created_at DESC
        """
    )
    return [dict(row) for row in rows]
