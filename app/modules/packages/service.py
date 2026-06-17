"""
app/modules/packages/service.py
================================
Business logic for the packages module.

The key pattern here is the DYNAMIC UPDATE query in update_package().
Most tutorials show UPDATE queries with hardcoded column lists:
  UPDATE packages SET name=$1, price_kes=$2 WHERE id=$3

That works for full-replace updates but is wrong for partial updates: if
you call it with price_kes=None (field not in request body), you've just
set the price to NULL in the DB — silently corrupting data.

The dynamic approach: build the SET clause at runtime using only the fields
that were actually provided (not None). This is the correct pattern for
PATCH-style partial updates.
"""

from uuid import UUID

import asyncpg

from app.core.exceptions import NotFoundException, ConflictException
from app.modules.packages.schemas import PackageCreate, PackageUpdate


async def get_all_packages(conn: asyncpg.Connection) -> list[dict]:
    """
    Returns all active packages ordered by price ascending.

    Why only active packages?
    Soft-deleted packages (is_active=False) are ghost records — they exist
    for financial history integrity but should not be purchasable or visible
    to customers. The is_active index on packages makes this filter fast.
    """
    rows = await conn.fetch(
        """
        SELECT id, name, description, price_kes, duration_days,
               speed_mbps, is_active, created_at, updated_at
        FROM packages
        WHERE is_active = TRUE
        ORDER BY price_kes ASC
        """,
    )
    # conn.fetch() returns a list of asyncpg Record objects.
    # dict() converts each Record so the router/schema layer gets plain dicts.
    return [dict(row) for row in rows]


async def get_package_by_id(conn: asyncpg.Connection, package_id: UUID) -> dict:
    """
    Fetches a single package by its UUID.

    Raises NotFoundException if:
      - The ID doesn't exist in the DB at all.
      - The package has been soft-deleted (is_active=False).

    Why treat soft-deleted as not-found?
    From the client's perspective, a deleted package doesn't exist. Returning
    it with a "deleted" status would let customers try to buy it, requiring
    another check in the payment flow. Treating it as 404 here closes that gap.
    """
    row = await conn.fetchrow(
        """
        SELECT id, name, description, price_kes, duration_days,
               speed_mbps, is_active, created_at, updated_at
        FROM packages
        WHERE id = $1 AND is_active = TRUE
        """,
        package_id,
    )

    if row is None:
        # We pass the string version of the UUID so the error message is readable.
        raise NotFoundException("Package", str(package_id))

    return dict(row)


async def create_package(
    conn: asyncpg.Connection,
    data: PackageCreate,
    created_by_user_id: UUID,
) -> dict:
    """
    Inserts a new package row.

    created_by_user_id is taken from the authenticated admin's JWT token,
    NOT from the request body. The client cannot claim a package was created
    by a different admin — the router extracts it from the verified token.

    We check for name uniqueness explicitly before inserting so we can return
    a readable ConflictException instead of a raw asyncpg UniqueViolationError.
    The DB UNIQUE constraint still catches any race condition we miss here.
    """
    # Check if a package with this name already exists (active or inactive).
    # We check inactive too: if an admin soft-deleted "Daily 10Mbps" and then
    # tries to create it again, we should allow that (restore the name).
    # So we only block creation if an ACTIVE package has the same name.
    existing = await conn.fetchrow(
        "SELECT id FROM packages WHERE name = $1 AND is_active = TRUE",
        data.name,
    )
    if existing:
        raise ConflictException(f"An active package named '{data.name}' already exists.")

    row = await conn.fetchrow(
        """
        INSERT INTO packages
            (name, description, price_kes, duration_days, speed_mbps, created_by)
        VALUES
            ($1, $2, $3, $4, $5, $6)
        RETURNING id, name, description, price_kes, duration_days,
                  speed_mbps, is_active, created_at, updated_at
        """,
        data.name,
        data.description,
        data.price_kes,
        data.duration_days,
        data.speed_mbps,
        created_by_user_id,
    )

    return dict(row)


async def update_package(
    conn: asyncpg.Connection,
    package_id: UUID,
    data: PackageUpdate,
) -> dict:
    """
    Partially updates a package — only touches fields that are not None.

    HOW THE DYNAMIC UPDATE WORKS:
    We build a list of "field = $N" clauses at runtime, only for fields the
    client actually sent. asyncpg requires positional parameters ($1, $2, ...)
    so we number them dynamically as we add each field.

    Example — client sends {"price_kes": 75}:
      fields   = ["price_kes = $1", "updated_at = $2"]
      values   = [Decimal('75'), datetime.now()]
      query    = "UPDATE packages SET price_kes = $1, updated_at = $2
                  WHERE id = $3 AND is_active = TRUE RETURNING ..."
      params   = [Decimal('75'), datetime.now(), package_id]

    Example — client sends {"name": "Super Plan", "speed_mbps": 50}:
      fields   = ["name = $1", "speed_mbps = $2", "updated_at = $3"]
      values   = ["Super Plan", 50, datetime.now()]
      query    = "UPDATE packages SET name=$1, speed_mbps=$2, updated_at=$3
                  WHERE id = $4 AND is_active = TRUE RETURNING ..."
      params   = ["Super Plan", 50, datetime.now(), package_id]

    This is clean, safe (parameterised), and avoids hardcoding all possible
    field combinations.
    """
    # First, confirm the package exists and is active.
    await get_package_by_id(conn, package_id)

    # Build the dynamic SET clause.
    fields = []   # e.g. ["name = $1", "price_kes = $2"]
    values = []   # e.g. ["New Name", Decimal('75')]
    param_index = 1  # asyncpg parameters start at $1

    # Map of schema field names to DB column names (same here, but explicit).
    updatable_fields = {
        "name":          data.name,
        "description":   data.description,
        "price_kes":     data.price_kes,
        "duration_days": data.duration_days,
        "speed_mbps":    data.speed_mbps,
    }

    for column, value in updatable_fields.items():
        if value is not None:
            fields.append(f"{column} = ${param_index}")
            values.append(value)
            param_index += 1

    if not fields:
        # Client sent an empty body {} — nothing to update.
        # Rather than erroring, just return the current state.
        return await get_package_by_id(conn, package_id)

    # Always update updated_at when any field changes.
    fields.append(f"updated_at = NOW()")

    # The WHERE clause parameter comes after all the SET parameters.
    set_clause = ", ".join(fields)
    values.append(package_id)  # The WHERE id = $N parameter

    query = f"""
        UPDATE packages
        SET {set_clause}
        WHERE id = ${param_index} AND is_active = TRUE
        RETURNING id, name, description, price_kes, duration_days,
                  speed_mbps, is_active, created_at, updated_at
    """

    # *values unpacks the list as positional arguments.
    # asyncpg.execute/fetchrow accept: query, param1, param2, ...
    # Not: query, [param1, param2] (that's a list, not positional).
    row = await conn.fetchrow(query, *values)

    if row is None:
        raise NotFoundException("Package", str(package_id))

    return dict(row)


async def deactivate_package(conn: asyncpg.Connection, package_id: UUID) -> None:
    """
    Soft-deletes a package by setting is_active=False.

    WHY SOFT DELETE INSTEAD OF HARD DELETE:
    The payments table has a FK to packages.id with ON DELETE RESTRICT.
    If you hard-delete a package that has payments referencing it, PostgreSQL
    will refuse with a foreign key violation error. Even if we cascade the
    delete, we'd lose the ability to answer "what package did this customer
    pay for?" in financial reports, audits, and disputes.

    Soft delete solves both problems:
      1. The FK constraint is never violated (the row still exists).
      2. Financial history is preserved.
      3. The package disappears from all active queries (is_active=TRUE filter).

    This is a permanent decision for this system. We never hard-delete packages.
    """
    result = await conn.execute(
        """
        UPDATE packages
        SET is_active = FALSE, updated_at = NOW()
        WHERE id = $1 AND is_active = TRUE
        """,
        package_id,
    )

    # conn.execute() returns a string like "UPDATE 1" or "UPDATE 0".
    # "UPDATE 0" means the WHERE clause matched nothing — either the ID
    # doesn't exist, or the package was already deactivated.
    if result == "UPDATE 0":
        raise NotFoundException("Package", str(package_id))
