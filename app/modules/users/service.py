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
from app.modules.users.schemas import CreateCustomerRequest, UserUpdate, AdminUserCreate, AdminUserUpdate


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

async def admin_create_user(
    conn: asyncpg.Connection,
    data: AdminUserCreate,
) -> dict:
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

    hashed = hash_password(data.password)

    user = await conn.fetchrow(
        """
        INSERT INTO users (email, phone, hashed_password, role, reseller_id)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, email, phone, role, reseller_id, is_active, created_at
        """,
        data.email,
        data.phone,
        hashed,
        data.role,
        data.reseller_id,
    )
    return dict(user)

async def admin_update_user(
    conn: asyncpg.Connection,
    user_id: UUID,
    data: AdminUserUpdate,
) -> dict:
    # Fetch current
    current = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    if not current:
        raise NotFoundException("User", str(user_id))

    updates = {}
    
    if data.email is not None and data.email != current["email"]:
        existing = await conn.fetchrow("SELECT id FROM users WHERE email = $1 AND id != $2", data.email, user_id)
        if existing:
            raise ConflictException("Email already in use.")
        updates["email"] = data.email
        
    if data.phone is not None and data.phone != current["phone"]:
        existing = await conn.fetchrow("SELECT id FROM users WHERE phone = $1 AND id != $2", data.phone, user_id)
        if existing:
            raise ConflictException("Phone already in use.")
        updates["phone"] = data.phone

    if data.password is not None:
        updates["hashed_password"] = hash_password(data.password)
        
    if data.role is not None:
        updates["role"] = data.role
        
    if data.reseller_id is not None:
        # Pydantic's Optional will be explicitly passed, but sometimes we want to unset it.
        # However, None might mean "don't update" in a PATCH. 
        # But wait, Pydantic's default is None. If we want to allow unsetting, we'd need more complex logic.
        # Let's assume if they pass it, we update it.
        # If we really want to unset, maybe we need a special value. But let's just update if it's in model_fields_set.
        pass # Handle below via model_dump(exclude_unset=True)

    # A better approach for PATCH:
    update_data = data.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["hashed_password"] = hash_password(update_data.pop("password"))
        
    if "email" in update_data and update_data["email"] != current["email"]:
        existing = await conn.fetchrow("SELECT id FROM users WHERE email = $1 AND id != $2", update_data["email"], user_id)
        if existing:
            raise ConflictException("Email already in use.")
            
    if "phone" in update_data and update_data["phone"] != current["phone"]:
        existing = await conn.fetchrow("SELECT id FROM users WHERE phone = $1 AND id != $2", update_data["phone"], user_id)
        if existing:
            raise ConflictException("Phone already in use.")

    if not update_data:
        # No fields to update
        row = await conn.fetchrow("SELECT id, email, phone, role, reseller_id, is_active, created_at FROM users WHERE id = $1", user_id)
        return dict(row)

    update_data["updated_at"] = "NOW()"
    
    set_clauses = []
    values = []
    
    for i, (key, value) in enumerate(update_data.items(), start=1):
        if value == "NOW()":
            set_clauses.append(f"{key} = NOW()")
        else:
            set_clauses.append(f"{key} = ${i}")
            values.append(value)
            
    values.append(user_id)
    query = f"""
        UPDATE users
        SET {', '.join(set_clauses)}
        WHERE id = ${len(values)}
        RETURNING id, email, phone, role, reseller_id, is_active, created_at
    """
    
    row = await conn.fetchrow(query, *values)
    return dict(row)

async def admin_deactivate_user(
    conn: asyncpg.Connection,
    user_id: UUID,
) -> None:
    row = await conn.fetchrow("SELECT id FROM users WHERE id = $1", user_id)
    if not row:
        raise NotFoundException("User", str(user_id))
        
    await conn.execute("UPDATE users SET is_active = False, updated_at = NOW() WHERE id = $1", user_id)
