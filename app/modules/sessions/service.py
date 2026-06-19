"""
app/modules/sessions/service.py
================================
Service layer for network sessions -fully tenant-scoped.

MULTI-TENANCY CHANGE (Phase 1):
  Both functions now scope to tenant_id. A customer in tenant A cannot
  see sessions belonging to tenant B's customers.
"""

import logging
from uuid import UUID

import asyncpg

logger = logging.getLogger(__name__)


async def get_customer_sessions(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    customer_id: str,
) -> list[dict]:
    """Retrieves all sessions for a customer within a tenant."""
    rows = await conn.fetch(
        """
        SELECT
            id,
            voucher_id,
            customer_id,
            mac_address,
            ip_address,
            bytes_uploaded,
            bytes_downloaded,
            started_at,
            ended_at,
            created_at
        FROM sessions
        WHERE customer_id = $1
          AND tenant_id = $2
        ORDER BY started_at DESC
        """,
        customer_id,
        tenant_id,
    )
    return [dict(r) for r in rows]


async def get_all_sessions(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Retrieves a paginated list of all sessions in a tenant."""
    rows = await conn.fetch(
        """
        SELECT
            id,
            voucher_id,
            customer_id,
            mac_address,
            ip_address,
            bytes_uploaded,
            bytes_downloaded,
            started_at,
            ended_at,
            created_at
        FROM sessions
        WHERE tenant_id = $1
        ORDER BY started_at DESC
        LIMIT $2 OFFSET $3
        """,
        tenant_id,
        limit,
        offset,
    )
    return [dict(r) for r in rows]
