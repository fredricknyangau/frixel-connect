"""
app/modules/sessions/service.py
================================
Service layer managing queries to the sessions table.

DESIGN NOTE AND ARCHITECTURAL LIMITATION:
  Hotspot session records are generated and recorded by the MikroTik router's
  internal accounting engine, NOT directly by our HTTP REST API. The API cannot
  intercept raw hotspot traffic.
  Therefore, the local `sessions` table acts strictly as a cache or mirror of
  the router's active state.
  In this v1 architecture, sessions are either synced from MikroTik's active list
  manually or will be updated asynchronously via a cron sync script querying
  MikroTik's REST endpoint and updating PostgreSQL.
"""

import logging
import asyncpg

logger = logging.getLogger(__name__)


async def get_customer_sessions(conn: asyncpg.Connection, customer_id: str) -> list[dict]:
    """
    Retrieves all hotspot login sessions belonging to a specific customer.
    Results are sorted chronologically with the newest session first.
    """
    query = """
        SELECT
            id,
            voucher_id,
            customer_id,
            mac_address,
            -- asyncpg automatically casts INET database types to strings
            -- which serializes cleanly in our Pydantic schemas.
            ip_address,
            bytes_uploaded,
            bytes_downloaded,
            started_at,
            ended_at,
            created_at
        FROM sessions
        WHERE customer_id = $1
        ORDER BY started_at DESC
    """
    rows = await conn.fetch(query, customer_id)
    return [dict(r) for r in rows]


async def get_all_sessions(
    conn: asyncpg.Connection,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """
    Retrieves a paginated list of all sessions in the system.
    Pagination is strictly enforced using LIMIT and OFFSET to prevent unbounded database
    fetches from degrading API response times under high transaction load.
    """
    query = """
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
        ORDER BY started_at DESC
        LIMIT $1 OFFSET $2
    """
    rows = await conn.fetch(query, limit, offset)
    return [dict(r) for r in rows]
