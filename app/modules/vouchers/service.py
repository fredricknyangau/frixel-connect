"""
app/modules/vouchers/service.py
================================
Service logic for voucher code generation, MikroTik hotspot user creation,
and database persistence.

WHY WE USE secrets.choice INSTEAD OF random.choice:
  Standard library `random` module uses the Mersenne Twister algorithm, which
  is a deterministic pseudo-random number generator. If an attacker observes a
  sufficient number of generated voucher codes, they can reconstruct the state of
  the generator and predict future codes, enabling voucher theft.
  In contrast, the `secrets` module uses the operating system's cryptographically
  secure pseudo-random number generator (CSPRNG), which leverages environmental
  entropy. It is designed specifically for cryptography and security tokens,
  rendering the voucher codes mathematically unpredictable.
"""

import asyncio
import logging
import secrets
from typing import Optional

import asyncpg

from app.database import get_db
from app.integrations.mikrotik import mikrotik_client, MikroTikError

logger = logging.getLogger(__name__)

# Alphabet excluding easily confused characters:
# - Numbers 0 and 1
# - Letters O, I, l (lowercase L)
VOUCHER_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_voucher_code(length: int = 10) -> str:
    """
    Generates a cryptographically secure random voucher code.
    Uses secrets.choice to avoid predictability.
    """
    return "".join(secrets.choice(VOUCHER_ALPHABET) for _ in range(length))


async def generate_voucher(conn: asyncpg.Connection, payment_id: str) -> str:
    """
    Core voucher generation pipeline:
      1. Fetch payment and package details in a single JOIN query.
      2. Generate a secure voucher code.
      3. Call MikroTik to provision the hotspot user.
      4. If MikroTik is unreachable/fails, retry with exponential backoff (5s, 15s, 45s).
      5. Insert voucher record into DB. If MikroTik fails completely, save as 'pending_provision'.
      6. Return the voucher code.

    CRITICAL ARCHITECTURAL DECISION:
      We intentionally do NOT run this function inside a PostgreSQL transaction block.
      Why? Holding a database connection and keeping a transaction open while making
      slow external HTTP requests (which can take up to 65+ seconds due to backoff retries)
      is a critical resource-exhaustion anti-pattern. Under load, it would consume all
      available pool connections, causing the API to hang.
      Instead, we fetch data, release/use standard connection queries, perform the HTTP
      calls without a transaction, and execute a final INSERT query.
    """
    # ── Step 1: Fetch payment & package details ──────────────────────────────
    query = """
        SELECT
            p.customer_id,
            p.package_id,
            p.amount_kes,
            p.status AS payment_status,
            pkg.duration_days,
            pkg.speed_mbps
        FROM payments p
        JOIN packages pkg ON p.package_id = pkg.id
        WHERE p.id = $1
    """
    row = await conn.fetchrow(query, payment_id)
    if not row:
        raise ValueError(f"Payment {payment_id} not found when generating voucher")

    customer_id = row["customer_id"]
    package_id = row["package_id"]
    duration_days = row["duration_days"]
    speed_mbps = row["speed_mbps"]

    # ── Step 2: Generate voucher code ────────────────────────────────────────
    # We must ensure the code is unique in our database. We try to generate it,
    # and if it exists we generate another. Normally a 10-char alphabet of size 31
    # has 31^10 = 819 trillion combinations, so collisions are practically impossible.
    # But we perform a quick check to be fully robust.
    code = generate_voucher_code()
    collision_check = await conn.fetchval("SELECT COUNT(*) FROM vouchers WHERE code = $1", code)
    if collision_check > 0:
        code = generate_voucher_code()  # retry once

    # ── Step 3: Call MikroTik with Exponential Backoff ────────────────────────
    # Attempt count is 4 (Initial attempt + 3 retries)
    # Delays: 5s, 15s, 45s
    attempts = 4
    delays = [5, 15, 45]
    success = False

    profile = f"{speed_mbps}Mbps"
    time_limit = f"{duration_days}d"

    logger.info(f"Voucher: provisioning voucher '{code}' on MikroTik for payment {payment_id}")

    for attempt in range(1, attempts + 1):
        try:
            # Call MikroTikClient singleton.
            # Username and password are set to the same voucher code value.
            await mikrotik_client.generate_hotspot_user(
                username=code,
                password=code,
                profile=profile,
                time_limit=time_limit,
            )
            success = True
            logger.info(f"Voucher: successfully provisioned '{code}' on MikroTik on attempt {attempt}")
            break
        except (MikroTikError, Exception) as e:
            logger.warning(
                f"Voucher: MikroTik provisioning attempt {attempt} failed for code '{code}': {e}"
            )
            if attempt < attempts:
                delay = delays[attempt - 1]
                logger.info(f"Voucher: retrying in {delay} seconds...")
                await asyncio.sleep(delay)

    # ── Step 4: Record Voucher in Database ───────────────────────────────────
    # If provisioning was successful, status is 'active'.
    # If provisioning failed completely, status is 'pending_provision'.
    # This prevents money/vouchers from being lost if the router goes offline:
    # the customer payment is stored, and an admin can manually retry from a dashboard.
    status = "active" if success else "pending_provision"

    insert_query = """
        INSERT INTO vouchers (payment_id, customer_id, package_id, code, status)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
    """
    try:
        await conn.execute(insert_query, payment_id, customer_id, package_id, code, status)
        logger.info(f"Voucher: recorded '{code}' in database with status '{status}'")
    except Exception as e:
        logger.error(f"Voucher: failed to insert voucher '{code}' into DB: {e}")
        raise e

    return code


async def generate_voucher_task(payment_id: str) -> None:
    """
    FastAPI BackgroundTask wrapper.
    Obtains a database connection from the pool, then triggers generate_voucher.
    Exceptions are caught and logged so the background task worker doesn't crash.
    """
    try:
        async with get_db() as conn:
            await generate_voucher(conn, payment_id)
    except Exception as e:
        logger.error(f"Voucher Background Task: failed for payment {payment_id}: {e}", exc_info=True)


async def get_customer_vouchers(conn: asyncpg.Connection, customer_id: str) -> list[dict]:
    """Retrieves all vouchers belonging to a specific customer."""
    query = """
        SELECT v.id, v.code, v.status, v.expires_at, v.customer_id, v.activated_at, v.created_at,
               pkg.name AS package_name
        FROM vouchers v
        JOIN packages pkg ON v.package_id = pkg.id
        WHERE v.customer_id = $1
        ORDER BY v.created_at DESC
    """
    rows = await conn.fetch(query, customer_id)
    return [dict(r) for r in rows]


async def get_voucher_by_id(conn: asyncpg.Connection, voucher_id: str) -> Optional[dict]:
    """Retrieves a specific voucher by its UUID, including the package name."""
    query = """
        SELECT v.id, v.code, v.status, v.expires_at, v.customer_id, v.activated_at, v.created_at,
               pkg.name AS package_name
        FROM vouchers v
        JOIN packages pkg ON v.package_id = pkg.id
        WHERE v.id = $1
    """
    row = await conn.fetchrow(query, voucher_id)
    return dict(row) if row else None


async def get_reseller_vouchers(conn: asyncpg.Connection, reseller_id: str) -> list[dict]:
    """Retrieves all vouchers for customers assigned to a specific reseller."""
    query = """
        SELECT v.id, v.code, v.status, v.expires_at, v.customer_id, v.activated_at, v.created_at,
               pkg.name AS package_name
        FROM vouchers v
        JOIN packages pkg ON v.package_id = pkg.id
        JOIN users u ON v.customer_id = u.id
        WHERE u.reseller_id = $1
        ORDER BY v.created_at DESC
    """
    rows = await conn.fetch(query, reseller_id)
    return [dict(r) for r in rows]


async def get_all_vouchers(conn: asyncpg.Connection) -> list[dict]:
    """Retrieves all vouchers in the system (admin view)."""
    query = """
        SELECT v.id, v.code, v.status, v.expires_at, v.customer_id, v.activated_at, v.created_at,
               pkg.name AS package_name
        FROM vouchers v
        JOIN packages pkg ON v.package_id = pkg.id
        ORDER BY v.created_at DESC
    """
    rows = await conn.fetch(query)
    return [dict(r) for r in rows]


async def admin_revoke_voucher(conn: asyncpg.Connection, voucher_id: str) -> dict:
    """
    Revokes a voucher by UUID:
      1. Looks up the voucher. Raises NotFoundException if missing.
      2. Updates status to "revoked" in PostgreSQL.
      3. Synchronously calls MikroTik REST client to remove the hotspot user.
    """
    from app.core.exceptions import NotFoundException

    # Fetch the voucher first to get the code
    v_query = "SELECT id, code, status FROM vouchers WHERE id = $1"
    voucher = await conn.fetchrow(v_query, voucher_id)
    if not voucher:
        raise NotFoundException("Voucher", voucher_id)

    # Perform SQL status update
    update_query = """
        UPDATE vouchers
        SET status = 'revoked'
        WHERE id = $1
        RETURNING id, code, status
    """
    updated_row = await conn.fetchrow(update_query, voucher_id)

    # Remove the user profile entry from RouterOS Hotspot database
    logger.info(f"Voucher Revocation: deleting hotspot user '{voucher['code']}' from RouterOS")
    await mikrotik_client.remove_hotspot_user(voucher["code"])

    return dict(updated_row)

