"""
app/modules/vouchers/service.py
================================
Service logic for voucher code generation, MikroTik hotspot user creation,
and database persistence — fully tenant-scoped and router-scoped.
"""

import asyncio
import logging
import secrets
from typing import Optional
from uuid import UUID

import asyncpg

from app.database import get_db
from app.integrations.mikrotik import get_mikrotik_client, MikroTikError
from app.core.exceptions import NotFoundException

logger = logging.getLogger(__name__)

# Alphabet excluding easily confused characters (0, 1, O, I, l)
VOUCHER_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_voucher_code(length: int = 10) -> str:
    """Generates a cryptographically secure random voucher code."""
    return "".join(secrets.choice(VOUCHER_ALPHABET) for _ in range(length))


async def _provision_radius_credentials(
    conn: asyncpg.Connection,
    username: str,
    password: str,
    speed_mbps: int,
    data_quota_mb: Optional[int] = None,
) -> None:
    """Helper to write RADIUS credentials to radcheck and radreply tables (idempotent)."""
    # 1. Clear any existing records for this user to be safe
    await conn.execute("DELETE FROM radcheck WHERE username = $1", username)
    await conn.execute("DELETE FROM radreply WHERE username = $1", username)

    # 2. Insert Cleartext-Password into radcheck
    await conn.execute(
        """
        INSERT INTO radcheck (username, attribute, op, value)
        VALUES ($1, 'Cleartext-Password', ':=', $2)
        """,
        username,
        password,
    )

    # 3. Insert Mikrotik-Rate-Limit into radreply
    await conn.execute(
        """
        INSERT INTO radreply (username, attribute, op, value)
        VALUES ($1, 'Mikrotik-Rate-Limit', ':=', $2)
        """,
        username,
        f"{speed_mbps}M",
    )

    # 4. Insert optional Mikrotik-Total-Limit into radreply
    if data_quota_mb:
        limit_bytes = data_quota_mb * 1024 * 1024
        await conn.execute(
            """
            INSERT INTO radreply (username, attribute, op, value)
            VALUES ($1, 'Mikrotik-Total-Limit', ':=', $2)
            """,
            username,
            str(limit_bytes),
        )


async def generate_voucher(
    conn: asyncpg.Connection,
    payment_id: str,
    is_final_attempt: bool = False,
) -> str:
    """
    Core voucher generation pipeline:
      1. Fetch payment + package details (scoped to payment's tenant_id).
      2. Retrieve customer's assigned router_id from users table.
      3. Generate a secure voucher code.
      4. Call MikroTik against the assigned router.
      5. Insert voucher with tenant_id and router_id.
      6. Return the voucher code.

    Task Queue Integration:
      - If call fails and is_final_attempt=False, raises exception immediately
        without writing to database (triggering arq retry).
      - If call fails and is_final_attempt=True, records the voucher in DB
        with status 'pending_provision' and raises the exception.
    """
    # ── Step 1: Fetch payment, package, and tenant ────────────────────────────
    row = await conn.fetchrow(
        """
        SELECT
            p.customer_id,
            p.package_id,
            p.amount_kes,
            p.status AS payment_status,
            p.tenant_id,
            pkg.duration_days,
            pkg.speed_mbps,
            pkg.data_quota_mb
        FROM payments p
        JOIN packages pkg ON p.package_id = pkg.id
        WHERE p.id = $1
        """,
        payment_id,
    )
    if not row:
        raise ValueError(f"Payment {payment_id} not found when generating voucher")

    customer_id = row["customer_id"]
    package_id  = row["package_id"]
    tenant_id   = row["tenant_id"]
    duration_days = row["duration_days"]
    speed_mbps    = row["speed_mbps"]
    data_quota_mb = row["data_quota_mb"]

    # ── Step 2: Retrieve customer's assigned router_id ───────────────────────
    user_row = await conn.fetchrow(
        "SELECT router_id FROM users WHERE id = $1 AND tenant_id = $2",
        customer_id,
        tenant_id,
    )
    router_id = user_row["router_id"] if user_row else None

    # Fetch router credentials
    router_row = None
    if router_id:
        router_row = await conn.fetchrow(
            """
            SELECT host, port, username, password_encrypted
            FROM routers
            WHERE id = $1 AND tenant_id = $2
            """,
            router_id,
            tenant_id,
        )

    # ── Step 3: Generate globally unique voucher code ─────────────────────────
    code = generate_voucher_code()
    collision = await conn.fetchval(
        "SELECT COUNT(*) FROM vouchers WHERE code = $1",
        code,
    )
    if collision > 0:
        code = generate_voucher_code()

    # ── Step 4: Call MikroTik ─────────────────────────────────────────────────
    profile    = f"{speed_mbps}Mbps"
    time_limit = f"{duration_days}d"

    # Instantiate client dynamically (falls back to settings if router_row is None)
    client = get_mikrotik_client(dict(router_row) if router_row else None)

    logger.info(
        f"Voucher: provisioning '{code}' on MikroTik router '{router_id or 'global'}' "
        f"for payment {payment_id} (tenant {tenant_id})"
    )

    success = False
    provision_error = None
    try:
        await client.generate_hotspot_user(
            username=code,
            password=code,
            profile=profile,
            time_limit=time_limit,
        )
        success = True
        logger.info(f"Voucher: successfully provisioned '{code}' on MikroTik")
    except Exception as e:
        provision_error = e
        logger.warning(f"Voucher: MikroTik provisioning failed for '{code}': {e}")
        # If not final attempt, raise immediately to let task queue retry
        if not is_final_attempt:
            raise e

    # ── Step 5: Insert voucher with tenant_id and router_id ──────────────────
    status = "active" if success else "pending_provision"

    try:
        # Provision FreeRADIUS credentials within the database transaction
        await _provision_radius_credentials(
            conn=conn,
            username=code,
            password=code,
            speed_mbps=speed_mbps,
            data_quota_mb=data_quota_mb,
        )

        await conn.execute(
            """
            INSERT INTO vouchers (payment_id, customer_id, package_id, code, status, tenant_id, router_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            payment_id,
            customer_id,
            package_id,
            code,
            status,
            tenant_id,
            router_id,
        )
        logger.info(f"Voucher: recorded '{code}' in DB with status '{status}' under router '{router_id or 'global'}'")
    except Exception as e:
        logger.error(f"Voucher: failed to insert '{code}' into DB or provision RADIUS: {e}")
        raise e

    # Raise original exception if provisioning failed to record task failure
    if not success and provision_error:
        raise provision_error

    return code


async def generate_voucher_task(payment_id: str) -> None:
    """FastAPI BackgroundTask wrapper (legacy fallback)."""
    try:
        async with get_db() as conn:
            await generate_voucher(conn, payment_id, is_final_attempt=True)
    except Exception as e:
        logger.error(f"Voucher Background Task: failed for payment {payment_id}: {e}", exc_info=True)


async def get_customer_vouchers(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    customer_id: str,
) -> list[dict]:
    """Retrieves all vouchers for a customer within a tenant."""
    rows = await conn.fetch(
        """
        SELECT v.id, v.code, v.status, v.expires_at, v.customer_id,
               v.activated_at, v.created_at, v.router_id,
               pkg.name AS package_name
        FROM vouchers v
        JOIN packages pkg ON v.package_id = pkg.id
        WHERE v.customer_id = $1
          AND v.tenant_id = $2
        ORDER BY v.created_at DESC
        """,
        customer_id,
        tenant_id,
    )
    return [dict(r) for r in rows]


async def get_voucher_by_id(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    voucher_id: str,
) -> Optional[dict]:
    """Retrieves a specific voucher within a tenant."""
    row = await conn.fetchrow(
        """
        SELECT v.id, v.code, v.status, v.expires_at, v.customer_id,
               v.activated_at, v.created_at, v.router_id,
               pkg.name AS package_name
        FROM vouchers v
        JOIN packages pkg ON v.package_id = pkg.id
        WHERE v.id = $1
          AND v.tenant_id = $2
        """,
        voucher_id,
        tenant_id,
    )
    return dict(row) if row else None


async def get_reseller_vouchers(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    reseller_id: str,
) -> list[dict]:
    """Retrieves vouchers for a reseller's customers within a tenant."""
    rows = await conn.fetch(
        """
        SELECT v.id, v.code, v.status, v.expires_at, v.customer_id,
               v.activated_at, v.created_at, v.router_id,
               pkg.name AS package_name
        FROM vouchers v
        JOIN packages pkg ON v.package_id = pkg.id
        JOIN users u ON v.customer_id = u.id
        WHERE u.reseller_id = $1
          AND v.tenant_id = $2
        ORDER BY v.created_at DESC
        """,
        reseller_id,
        tenant_id,
    )
    return [dict(r) for r in rows]


async def get_all_vouchers(
    conn: asyncpg.Connection,
    tenant_id: UUID,
) -> list[dict]:
    """Retrieves all vouchers in the tenant (admin view)."""
    rows = await conn.fetch(
        """
        SELECT v.id, v.code, v.status, v.expires_at, v.customer_id,
               v.activated_at, v.created_at, v.router_id,
               pkg.name AS package_name
        FROM vouchers v
        JOIN packages pkg ON v.package_id = pkg.id
        WHERE v.tenant_id = $1
        ORDER BY v.created_at DESC
        """,
        tenant_id,
    )
    return [dict(r) for r in rows]


async def admin_revoke_voucher(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    voucher_id: str,
) -> dict:
    """
    Revokes a voucher within the tenant.
    Returns 404 for cross-tenant voucher UUIDs (not 403).
    """
    # Fetch with tenant_id scope — cross-tenant UUIDs return None → 404
    voucher = await conn.fetchrow(
        "SELECT id, code, status, customer_id, router_id FROM vouchers WHERE id = $1 AND tenant_id = $2",
        voucher_id,
        tenant_id,
    )
    if not voucher:
        raise NotFoundException("Voucher", voucher_id)

    updated_row = await conn.fetchrow(
        """
        UPDATE vouchers
        SET status = 'revoked'
        WHERE id = $1 AND tenant_id = $2
        RETURNING id, code, status, router_id
        """,
        voucher_id,
        tenant_id,
    )

    # Delete RADIUS credentials
    await conn.execute("DELETE FROM radcheck WHERE username = $1", voucher["code"])
    await conn.execute("DELETE FROM radreply WHERE username = $1", voucher["code"])

    # Fetch active session and trigger CoA Disconnect-Request
    active_session = await conn.fetchrow(
        """
        SELECT HOST(nasipaddress) AS router_ip, acctsessionid
        FROM radacct
        WHERE username = $1 AND acctstoptime IS NULL
        ORDER BY acctstarttime DESC
        LIMIT 1
        """,
        voucher["code"]
    )
    if active_session:
        from app.integrations.radius_coa import send_coa_disconnect
        # Run synchronous network I/O in thread pool to avoid blocking the event loop
        await asyncio.to_thread(
            send_coa_disconnect,
            active_session["router_ip"],
            voucher["code"],
            active_session["acctsessionid"]
        )

    router_id = voucher["router_id"]
    router_row = None
    if router_id:
        router_row = await conn.fetchrow(
            "SELECT host, port, username, password_encrypted FROM routers WHERE id = $1 AND tenant_id = $2",
            router_id,
            tenant_id,
        )

    client = get_mikrotik_client(dict(router_row) if router_row else None)

    logger.info(
        f"Voucher Revocation: deleting hotspot user '{voucher['code']}' "
        f"from router '{router_id or 'global'}'"
    )
    await client.remove_hotspot_user(voucher["code"])

    return dict(updated_row)


async def admin_retry_voucher(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    voucher_id: str,
) -> dict:
    """Manually retries provisioning a stuck voucher within the tenant."""
    row = await conn.fetchrow(
        """
        SELECT v.id, v.code, v.status, v.router_id, pkg.duration_days, pkg.speed_mbps, pkg.data_quota_mb
        FROM vouchers v
        JOIN packages pkg ON v.package_id = pkg.id
        WHERE v.id = $1
          AND v.tenant_id = $2
        """,
        voucher_id,
        tenant_id,
    )

    if not row:
        raise NotFoundException("Voucher", voucher_id)

    if row["status"] != "pending_provision":
        raise ValueError(f"Voucher {voucher_id} is not pending provision.")

    code       = row["code"]
    profile    = f"{row['speed_mbps']}Mbps"
    time_limit = f"{row['duration_days']}d"
    router_id  = row["router_id"]

    router_row = None
    if router_id:
        router_row = await conn.fetchrow(
            "SELECT host, port, username, password_encrypted FROM routers WHERE id = $1 AND tenant_id = $2",
            router_id,
            tenant_id,
        )

    client = get_mikrotik_client(dict(router_row) if router_row else None)

    logger.info(f"Voucher Retry: provisioning '{code}' on router '{router_id or 'global'}'")

    try:
        # Also ensure FreeRADIUS has the credentials on retry
        await _provision_radius_credentials(
            conn=conn,
            username=code,
            password=code,
            speed_mbps=row["speed_mbps"],
            data_quota_mb=row["data_quota_mb"],
        )

        await client.generate_hotspot_user(
            username=code,
            password=code,
            profile=profile,
            time_limit=time_limit,
        )
    except Exception as e:
        logger.error(f"Voucher Retry: failed for '{code}' on router '{router_id or 'global'}': {e}")
        raise ValueError(f"MikroTik provisioning failed: {e}")

    updated_row = await conn.fetchrow(
        """
        UPDATE vouchers
        SET status = 'active'
        WHERE id = $1 AND tenant_id = $2
        RETURNING id, code, status, router_id
        """,
        voucher_id,
        tenant_id,
    )
    return dict(updated_row)


async def provision_retry_poller() -> None:
    """
    Background poller for pending_provision vouchers.
    Legacy in-process poller.
    """
    logger.info("Voucher Poller: started background self-healing task")
    while True:
        try:
            await asyncio.sleep(300)

            async with get_db() as conn:
                rows = await conn.fetch(
                    """
                    SELECT v.id, v.code, v.tenant_id, v.router_id, pkg.duration_days, pkg.speed_mbps, pkg.data_quota_mb
                    FROM vouchers v
                    JOIN packages pkg ON v.package_id = pkg.id
                    WHERE v.status = 'pending_provision'
                    """
                )

                if rows:
                    logger.info(f"Voucher Poller: found {len(rows)} pending vouchers")

                    for v in rows:
                        code       = v["code"]
                        tenant_id  = v["tenant_id"]
                        router_id  = v["router_id"]
                        profile    = f"{v['speed_mbps']}Mbps"
                        time_limit = f"{v['duration_days']}d"

                        router_row = None
                        if router_id:
                            router_row = await conn.fetchrow(
                                "SELECT host, port, username, password_encrypted FROM routers WHERE id = $1 AND tenant_id = $2",
                                router_id,
                                tenant_id,
                            )

                        client = get_mikrotik_client(dict(router_row) if router_row else None)

                        try:
                            # Ensure FreeRADIUS credentials exist
                            await _provision_radius_credentials(
                                conn=conn,
                                username=code,
                                password=code,
                                speed_mbps=v["speed_mbps"],
                                data_quota_mb=v["data_quota_mb"],
                            )

                            await client.generate_hotspot_user(
                                username=code,
                                password=code,
                                profile=profile,
                                time_limit=time_limit,
                            )
                            await conn.execute(
                                "UPDATE vouchers SET status = 'active' WHERE id = $1",
                                v["id"],
                            )
                            logger.info(f"Voucher Poller: recovered '{code}' on router '{router_id or 'global'}'")
                        except Exception as e:
                            logger.warning(f"Voucher Poller: still failing '{code}' on router '{router_id or 'global'}': {e}")

        except asyncio.CancelledError:
            logger.info("Voucher Poller: shutting down")
            break
        except Exception as e:
            logger.error(f"Voucher Poller: unexpected error: {e}", exc_info=True)
            await asyncio.sleep(10)
