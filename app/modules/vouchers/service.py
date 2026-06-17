"""
app/modules/vouchers/service.py
================================
Service logic for voucher code generation, MikroTik hotspot user creation,
and database persistence — fully tenant-scoped.

MULTI-TENANCY CHANGE (Phase 1):
  - generate_voucher: fetches payment AND validates tenant_id match.
    Stores tenant_id on the voucher row.
  - All list/get functions scope to tenant_id.
  - The 404-not-403 cross-tenant isolation rule applies here too:
    get_voucher_by_id returns None for cross-tenant UUIDs — the router
    raises 404.

WHY WE USE secrets.choice INSTEAD OF random.choice:
  Standard library `random` uses Mersenne Twister — a deterministic PRNG.
  If an attacker observes enough codes they can reconstruct the generator
  state and predict future codes. `secrets` uses OS CSPRNG (getrandom/
  /dev/urandom) — cryptographically unpredictable.
"""

import asyncio
import logging
import secrets
from typing import Optional
from uuid import UUID

import asyncpg

from app.database import get_db
from app.integrations.mikrotik import mikrotik_client, MikroTikError
from app.core.exceptions import NotFoundException

logger = logging.getLogger(__name__)

# Alphabet excluding easily confused characters (0, 1, O, I, l)
VOUCHER_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_voucher_code(length: int = 10) -> str:
    """Generates a cryptographically secure random voucher code."""
    return "".join(secrets.choice(VOUCHER_ALPHABET) for _ in range(length))


async def generate_voucher(
    conn: asyncpg.Connection,
    payment_id: str,
) -> str:
    """
    Core voucher generation pipeline:
      1. Fetch payment + package details (scoped to payment's tenant_id).
      2. Generate a secure voucher code (unique within the tenant).
      3. Call MikroTik with exponential backoff.
      4. Insert voucher with tenant_id.
      5. Return the voucher code.

    MULTI-TENANCY NOTE:
    Code uniqueness is currently global (vouchers.code UNIQUE constraint is
    table-wide). This is intentional: voucher codes are sent to MikroTik
    as hotspot usernames. If two tenants happen to generate the same code
    on the same MikroTik router, one would overwrite the other. By keeping
    code globally unique, this collision is impossible regardless of which
    router the voucher lands on.
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
            pkg.speed_mbps
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

    # ── Step 2: Generate globally unique voucher code ─────────────────────────
    code = generate_voucher_code()
    # Check global uniqueness (see module docstring for why global, not per-tenant)
    collision = await conn.fetchval(
        "SELECT COUNT(*) FROM vouchers WHERE code = $1",
        code,
    )
    if collision > 0:
        code = generate_voucher_code()  # retry once — collision probability is ~1 in 800 trillion

    # ── Step 3: Call MikroTik with exponential backoff ────────────────────────
    attempts = 4
    delays   = [5, 15, 45]
    success  = False

    profile    = f"{speed_mbps}Mbps"
    time_limit = f"{duration_days}d"

    logger.info(f"Voucher: provisioning '{code}' on MikroTik for payment {payment_id} (tenant {tenant_id})")

    for attempt in range(1, attempts + 1):
        try:
            await mikrotik_client.generate_hotspot_user(
                username=code,
                password=code,
                profile=profile,
                time_limit=time_limit,
            )
            success = True
            logger.info(f"Voucher: provisioned '{code}' on attempt {attempt}")
            break
        except (MikroTikError, Exception) as e:
            logger.warning(f"Voucher: MikroTik attempt {attempt} failed for '{code}': {e}")
            if attempt < attempts:
                delay = delays[attempt - 1]
                logger.info(f"Voucher: retrying in {delay}s...")
                await asyncio.sleep(delay)

    # ── Step 4: Insert voucher with tenant_id ─────────────────────────────────
    status = "active" if success else "pending_provision"

    try:
        await conn.execute(
            """
            INSERT INTO vouchers (payment_id, customer_id, package_id, code, status, tenant_id)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            payment_id,
            customer_id,
            package_id,
            code,
            status,
            tenant_id,
        )
        logger.info(f"Voucher: recorded '{code}' in DB with status '{status}'")
    except Exception as e:
        logger.error(f"Voucher: failed to insert '{code}' into DB: {e}")
        raise e

    return code


async def generate_voucher_task(payment_id: str) -> None:
    """
    FastAPI BackgroundTask wrapper.
    (Phase 3 replaces this with a durable arq job — the function signature
    is preserved so the webhook handler needs no changes in Phase 3, only
    the enqueue mechanism changes.)
    """
    try:
        async with get_db() as conn:
            await generate_voucher(conn, payment_id)
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
               v.activated_at, v.created_at,
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
    """
    Retrieves a specific voucher within a tenant.

    Returns None (not a NotFoundException) when the voucher exists in a
    different tenant. The ROUTER raises NotFoundException on None, producing
    a 404. This way:
      - Same-tenant, voucher exists → returns dict
      - Same-tenant, voucher doesn't exist → returns None → router raises 404
      - Cross-tenant UUID → returns None → router raises 404 (not 403)

    404 vs 403 matters: returning 403 for a cross-tenant UUID would tell
    the caller "this UUID exists somewhere in our system, just not for you."
    That leaks information. 404 reveals nothing.
    """
    row = await conn.fetchrow(
        """
        SELECT v.id, v.code, v.status, v.expires_at, v.customer_id,
               v.activated_at, v.created_at,
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
               v.activated_at, v.created_at,
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
               v.activated_at, v.created_at,
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
        "SELECT id, code, status FROM vouchers WHERE id = $1 AND tenant_id = $2",
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
        RETURNING id, code, status
        """,
        voucher_id,
        tenant_id,
    )

    logger.info(f"Voucher Revocation: deleting hotspot user '{voucher['code']}' from RouterOS")
    await mikrotik_client.remove_hotspot_user(voucher["code"])

    return dict(updated_row)


async def admin_retry_voucher(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    voucher_id: str,
) -> dict:
    """Manually retries provisioning a stuck voucher within the tenant."""
    row = await conn.fetchrow(
        """
        SELECT v.id, v.code, v.status, pkg.duration_days, pkg.speed_mbps
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

    logger.info(f"Voucher Retry: provisioning '{code}'")

    try:
        await mikrotik_client.generate_hotspot_user(
            username=code,
            password=code,
            profile=profile,
            time_limit=time_limit,
        )
    except Exception as e:
        logger.error(f"Voucher Retry: failed for '{code}': {e}")
        raise ValueError(f"MikroTik provisioning failed: {e}")

    updated_row = await conn.fetchrow(
        """
        UPDATE vouchers
        SET status = 'active'
        WHERE id = $1 AND tenant_id = $2
        RETURNING id, code, status
        """,
        voucher_id,
        tenant_id,
    )
    return dict(updated_row)


async def provision_retry_poller() -> None:
    """
    Background poller for pending_provision vouchers.
    Phase 3 replaces this with a durable arq cron job — this remains
    active until Phase 3 is applied.
    """
    logger.info("Voucher Poller: started background self-healing task")
    while True:
        try:
            await asyncio.sleep(300)

            async with get_db() as conn:
                rows = await conn.fetch(
                    """
                    SELECT v.id, v.code, pkg.duration_days, pkg.speed_mbps
                    FROM vouchers v
                    JOIN packages pkg ON v.package_id = pkg.id
                    WHERE v.status = 'pending_provision'
                    """
                )

                if rows:
                    logger.info(f"Voucher Poller: found {len(rows)} pending vouchers")

                    for v in rows:
                        code       = v["code"]
                        profile    = f"{v['speed_mbps']}Mbps"
                        time_limit = f"{v['duration_days']}d"

                        try:
                            await mikrotik_client.generate_hotspot_user(
                                username=code,
                                password=code,
                                profile=profile,
                                time_limit=time_limit,
                            )
                            await conn.execute(
                                "UPDATE vouchers SET status = 'active' WHERE id = $1",
                                v["id"],
                            )
                            logger.info(f"Voucher Poller: recovered '{code}'")
                        except Exception as e:
                            logger.warning(f"Voucher Poller: still failing '{code}': {e}")

        except asyncio.CancelledError:
            logger.info("Voucher Poller: shutting down")
            break
        except Exception as e:
            logger.error(f"Voucher Poller: unexpected error: {e}", exc_info=True)
            await asyncio.sleep(10)
