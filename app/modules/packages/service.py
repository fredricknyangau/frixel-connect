"""
app/modules/packages/service.py
================================
Business logic for the packages module — fully tenant-scoped.

MULTI-TENANCY CHANGE (Phase 1):
  All queries now include AND tenant_id = $N.

  Package name uniqueness is now PER-TENANT, not global. Two different ISPs
  can both have a "Daily 10Mbps" package — that's fine. The UNIQUE constraint
  in the DB (002_create_packages.sql) is currently global, but we enforce
  uniqueness in the service by scoping the check to tenant_id. A future
  migration (dropping the global unique and adding a composite unique on
  (tenant_id, name)) would move this to the database layer.

  The dynamic UPDATE query pattern is unchanged — see the module docstring
  for a full explanation of how it works.
"""

from uuid import UUID

import asyncpg

from app.core.exceptions import NotFoundException, ConflictException
from app.modules.packages.schemas import PackageCreate, PackageUpdate


async def get_all_packages(
    conn: asyncpg.Connection,
    tenant_id: UUID,
) -> list[dict]:
    """Returns all active packages for this tenant, ordered by price."""
    rows = await conn.fetch(
        """
        SELECT id, name, description, price_kes, duration_days,
               speed_mbps, data_quota_mb, is_active, created_at, updated_at
        FROM packages
        WHERE tenant_id = $1
          AND is_active = TRUE
        ORDER BY price_kes ASC
        """,
        tenant_id,
    )
    return [dict(row) for row in rows]


async def get_package_by_id(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    package_id: UUID,
) -> dict:
    """
    Fetches a single active package by UUID within the tenant.

    Returns 404 if:
      - The ID doesn't exist.
      - The package exists but belongs to a different tenant (404, not 403 — see module docstring).
      - The package is soft-deleted.
    """
    row = await conn.fetchrow(
        """
        SELECT id, name, description, price_kes, duration_days,
               speed_mbps, data_quota_mb, is_active, created_at, updated_at
        FROM packages
        WHERE id = $1
          AND tenant_id = $2
          AND is_active = TRUE
        """,
        package_id,
        tenant_id,
    )

    if row is None:
        raise NotFoundException("Package", str(package_id))

    return dict(row)


async def create_package(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    data: PackageCreate,
    created_by_user_id: UUID,
) -> dict:
    """
    Inserts a new package for this tenant.
    Package name uniqueness is scoped to the tenant.
    """
    # Check active package name uniqueness within this tenant
    existing = await conn.fetchrow(
        """
        SELECT id FROM packages
        WHERE name = $1
          AND tenant_id = $2
          AND is_active = TRUE
        """,
        data.name,
        tenant_id,
    )
    if existing:
        raise ConflictException(f"An active package named '{data.name}' already exists.")

    row = await conn.fetchrow(
        """
        INSERT INTO packages
            (name, description, price_kes, duration_days, speed_mbps, data_quota_mb, created_by, tenant_id)
        VALUES
            ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id, name, description, price_kes, duration_days,
                  speed_mbps, data_quota_mb, is_active, created_at, updated_at
        """,
        data.name,
        data.description,
        data.price_kes,
        data.duration_days,
        data.speed_mbps,
        data.data_quota_mb,
        created_by_user_id,
        tenant_id,
    )

    return dict(row)


async def update_package(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    package_id: UUID,
    data: PackageUpdate,
) -> dict:
    """
    Partially updates a package — only touches fields that are not None.
    Scoped to the tenant.
    """
    # Confirm the package exists in this tenant
    await get_package_by_id(conn, tenant_id, package_id)

    fields = []
    values = []
    param_index = 1

    updatable_fields = {
        "name":          data.name,
        "description":   data.description,
        "price_kes":     data.price_kes,
        "duration_days": data.duration_days,
        "speed_mbps":    data.speed_mbps,
        "data_quota_mb": data.data_quota_mb,
    }

    for column, value in updatable_fields.items():
        if value is not None:
            fields.append(f"{column} = ${param_index}")
            values.append(value)
            param_index += 1

    if not fields:
        return await get_package_by_id(conn, tenant_id, package_id)

    fields.append("updated_at = NOW()")

    set_clause = ", ".join(fields)
    values.extend([package_id, tenant_id])

    query = f"""
        UPDATE packages
        SET {set_clause}
        WHERE id = ${param_index}
          AND tenant_id = ${param_index + 1}
          AND is_active = TRUE
        RETURNING id, name, description, price_kes, duration_days,
                  speed_mbps, data_quota_mb, is_active, created_at, updated_at
    """

    row = await conn.fetchrow(query, *values)

    if row is None:
        raise NotFoundException("Package", str(package_id))

    return dict(row)


async def deactivate_package(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    package_id: UUID,
) -> None:
    """Soft-deletes a package within the tenant."""
    result = await conn.execute(
        """
        UPDATE packages
        SET is_active = FALSE, updated_at = NOW()
        WHERE id = $1
          AND tenant_id = $2
          AND is_active = TRUE
        """,
        package_id,
        tenant_id,
    )

    if result == "UPDATE 0":
        raise NotFoundException("Package", str(package_id))
