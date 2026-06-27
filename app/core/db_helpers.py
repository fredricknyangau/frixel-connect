"""
app/core/db_helpers.py
========================
Shared database helpers for tenant-scoped resource lookups.

The `table` parameter in get_or_404 uses f-string interpolation but is NEVER
user-supplied — it always comes from hardcoded application constants in calling
code (e.g. "packages", "users"). This is not an SQL injection risk because the
table name is never derived from request input.
"""

from uuid import UUID

import asyncpg

from app.core.exceptions import NotFoundException


async def get_or_404(
    conn: asyncpg.Connection,
    table: str,
    resource_id: str | UUID,
    tenant_id: str | UUID,
    resource_name: str = "Resource",
) -> asyncpg.Record:
    """
    Fetches a single record by id AND tenant_id.

    Raises NotFoundException if:
      - The record does not exist at all
      - The record exists but belongs to a different tenant

    NEVER distinguishes between these two cases in the error message.
    Both return "{resource_name} not found" — no information oracle (T7).
    """
    row = await conn.fetchrow(
        f"SELECT * FROM {table} WHERE id = $1 AND tenant_id = $2",
        resource_id,
        tenant_id,
    )
    if row is None:
        raise NotFoundException(resource_name, str(resource_id))
    return row
