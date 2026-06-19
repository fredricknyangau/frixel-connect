"""
app/modules/routers/service.py
==============================
Service layer for router configuration, credential encryption/decryption,
and background heartbeat monitoring.
"""

import asyncio
from datetime import datetime
import logging
from typing import Optional
from uuid import UUID

import asyncpg

from app.core.exceptions import NotFoundException, ConflictException
from app.core.security import encrypt_secret
from app.integrations.mikrotik import get_mikrotik_client
from app.modules.routers.schemas import RouterCreate, RouterUpdate

logger = logging.getLogger(__name__)


async def create_router(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    payload: RouterCreate,
) -> dict:
    """
    Registers a new router under the tenant.
    Encrypts the router password using Fernet symmetric encryption.
    """
    # Enforce name uniqueness within the tenant
    existing = await conn.fetchval(
        "SELECT id FROM routers WHERE tenant_id = $1 AND name = $2",
        tenant_id,
        payload.name,
    )
    if existing:
        raise ConflictException(f"A router with name '{payload.name}' already exists.")

    encrypted_password = encrypt_secret(payload.password)

    row = await conn.fetchrow(
        """
        INSERT INTO routers (tenant_id, name, host, port, username, password_encrypted, site_name, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, 'unknown')
        RETURNING id, tenant_id, name, host, port, username, site_name, status, last_heartbeat_at, created_at,
                  wireguard_public_key, wireguard_assigned_ip, wireguard_peer_public_key
        """,
        tenant_id,
        payload.name,
        payload.host,
        payload.port,
        payload.username,
        encrypted_password,
        payload.site_name,
    )
    return dict(row)


async def get_routers(
    conn: asyncpg.Connection,
    tenant_id: UUID,
) -> list[dict]:
    """Retrieves all routers registered to the tenant."""
    rows = await conn.fetch(
        """
        SELECT id, tenant_id, name, host, port, username, site_name, status, last_heartbeat_at, created_at,
               wireguard_public_key, wireguard_assigned_ip, wireguard_peer_public_key
        FROM routers
        WHERE tenant_id = $1
        ORDER BY created_at DESC
        """,
        tenant_id,
    )
    return [dict(r) for r in rows]


async def get_router_by_id(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    router_id: UUID,
) -> Optional[dict]:
    """
    Retrieves a specific router config.
    Returns None for cross-tenant requests (404-not-403 rule).
    """
    row = await conn.fetchrow(
        """
        SELECT id, tenant_id, name, host, port, username, site_name, status, last_heartbeat_at, created_at,
               wireguard_public_key, wireguard_assigned_ip, wireguard_peer_public_key
        FROM routers
        WHERE id = $1 AND tenant_id = $2
        """,
        router_id,
        tenant_id,
    )
    return dict(row) if row else None


async def update_router(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    router_id: UUID,
    payload: RouterUpdate,
) -> dict:
    """Updates router connection parameters and re-encrypts password if changed."""
    existing = await conn.fetchrow(
        "SELECT id, name FROM routers WHERE id = $1 AND tenant_id = $2",
        router_id,
        tenant_id,
    )
    if not existing:
        raise NotFoundException("Router", str(router_id))

    if payload.name is not None and payload.name != existing["name"]:
        conflict = await conn.fetchval(
            "SELECT id FROM routers WHERE tenant_id = $1 AND name = $2 AND id != $3",
            tenant_id,
            payload.name,
            router_id,
        )
        if conflict:
            raise ConflictException(f"A router with name '{payload.name}' already exists.")

    updates = []
    params = [router_id, tenant_id]

    if payload.name is not None:
        params.append(payload.name)
        updates.append(f"name = ${len(params)}")
    if payload.host is not None:
        params.append(payload.host)
        updates.append(f"host = ${len(params)}")
    if payload.port is not None:
        params.append(payload.port)
        updates.append(f"port = ${len(params)}")
    if payload.username is not None:
        params.append(payload.username)
        updates.append(f"username = ${len(params)}")
    if payload.password is not None:
        params.append(encrypt_secret(payload.password))
        updates.append(f"password_encrypted = ${len(params)}")
    if payload.site_name is not None:
        params.append(payload.site_name)
        updates.append(f"site_name = ${len(params)}")

    if not updates:
        # Nothing to update, fetch latest details
        return await get_router_by_id(conn, tenant_id, router_id)

    query = f"""
        UPDATE routers
        SET {', '.join(updates)}
        WHERE id = $1 AND tenant_id = $2
        RETURNING id, tenant_id, name, host, port, username, site_name, status, last_heartbeat_at, created_at,
                  wireguard_public_key, wireguard_assigned_ip, wireguard_peer_public_key
    """
    row = await conn.fetchrow(query, *params)
    return dict(row)


async def delete_router(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    router_id: UUID,
) -> None:
    """Deletes a router configuration."""
    existing = await conn.fetchrow(
        "SELECT id, wireguard_peer_public_key FROM routers WHERE id = $1 AND tenant_id = $2",
        router_id,
        tenant_id,
    )
    if not existing:
        raise NotFoundException("Router", str(router_id))

    # Remove WireGuard peer first if present
    if existing["wireguard_peer_public_key"]:
        from app.integrations.wireguard import remove_wireguard_peer
        try:
            remove_wireguard_peer(existing["wireguard_peer_public_key"])
        except Exception as e:
            logger.error(f"Failed to remove WireGuard peer for router {router_id} during delete: {e}")

    await conn.execute(
        "DELETE FROM routers WHERE id = $1 AND tenant_id = $2",
        router_id,
        tenant_id,
    )


# ── Heartbeat Scheduled Job ──────────────────────────────────────────────────

async def router_heartbeat_loop() -> None:
    """
    Simple background scheduled task checking every router's status.
    Runs every 60 seconds. Marks a router offline after 3 consecutive failures.
    """
    from app.database import get_db

    logger.info("Router Heartbeat: starting scheduled background monitor")
    # In-memory dictionary tracking consecutive heartbeat failures per router ID.
    consecutive_failures: dict[UUID, int] = {}

    while True:
        try:
            await asyncio.sleep(60)

            async with get_db() as conn:
                # Fetch all registered routers across all tenants that are not in pending_setup or testing
                routers = await conn.fetch(
                    """
                    SELECT id, tenant_id, name, host, port, username, password_encrypted 
                    FROM routers
                    WHERE status NOT IN ('pending_setup', 'testing')
                    """
                )

                for r in routers:
                    router_id = r["id"]
                    try:
                        # Instantiate the client against this specific router using our factory
                        client = get_mikrotik_client(dict(r))
                        
                        # Call get_user_profile_names() as our heartbeat check
                        await client.get_user_profile_names()

                        # Success: reset failures and update status to online
                        consecutive_failures[router_id] = 0
                        await conn.execute(
                            """
                            UPDATE routers
                            SET status = 'online', last_heartbeat_at = NOW()
                            WHERE id = $1
                            """,
                            router_id,
                        )
                    except Exception as e:
                        # Handle failure and increment counter
                        failures = consecutive_failures.get(router_id, 0) + 1
                        consecutive_failures[router_id] = failures
                        logger.warning(
                            f"Router Heartbeat: Failure {failures}/3 for router '{r['name']}' "
                            f"(ID: {router_id}): {e}"
                        )

                        # Threshold met: mark router offline
                        if failures >= 3:
                            await conn.execute(
                                """
                                UPDATE routers
                                SET status = 'offline'
                                WHERE id = $1
                                """,
                                router_id,
                            )
        except asyncio.CancelledError:
            logger.info("Router Heartbeat: background monitor shutting down")
            break
        except Exception as e:
            logger.error(f"Router Heartbeat: unexpected error in monitor loop: {e}", exc_info=True)
            await asyncio.sleep(10)
