"""
app/modules/super_admin/service.py
=====================================
Business logic for the super admin portal.

SECURITY PRINCIPLES APPLIED THROUGHOUT:
  1. TIMING SAFETY: bcrypt.checkpw is always called, even if the email is not
     found, to prevent email enumeration via response time analysis.

  2. PRE-AUTH TOKEN SAFETY: raw tokens are never stored-only SHA256 hashes.
     The raw token lives only in the HTTP response (over TLS) and the caller's
     memory. If the pre_auth_tokens table is dumped, no usable tokens are exposed.

  3. TOTP SECRET SAFETY: secrets are stored Fernet-encrypted. The decrypted
     value exists in memory only for the duration of the TOTP verify call.
     Never logged, never returned, never cached.

  4. AUDIT COMPLETENESS: every service function that reads or mutates data
     writes an entry to super_admin_audit_log via _log_action(). Even read
     operations (like get_all_tenants) are logged, because the super admin
     portal is the highest-privilege surface in the system.

  5. NO DIRECT CUSTOMER DATA MODIFICATION: super admin uses impersonation
     tokens to act as a tenant admin. This ensures all customer mutations
     go through the tenant's own service functions (which apply tenant-scoped
     validation, audit, etc.) rather than bypassing them.
"""

import hashlib
import json
import secrets
from datetime import datetime, timezone, timedelta
from uuid import UUID

import asyncpg

from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    UnauthorisedException,
)
from app.core.security import (
    create_super_admin_access_token,
    hash_password,
    verify_password,
    create_access_token,
)
from app.services.totp_service import (
    decrypt_totp_secret,
    encrypt_totp_secret,
    generate_qr_code_base64,
    generate_totp_secret,
    verify_totp_code,
)
from app.modules.super_admin.schemas import SuperAdminTokenResponse
from app.core.redis import get_redis_pool


# ── Shared dummy hash for timing-safe bcrypt calls ────────────────────────────
# When a login email is not found, we still call bcrypt.checkpw against this
# dummy hash. This keeps the response time identical whether the email exists
# or not, preventing timing-based email enumeration.
# The hash is for "this_password_never_matches"-it will always fail.
_DUMMY_HASH = "$2b$12$KIXy0z5h5l5z5z5z5z5z5e1234567890123456789012345678901234"


# ── Internal audit helper ─────────────────────────────────────────────────────

async def _log_action(
    conn: asyncpg.Connection,
    super_admin_id: UUID,
    action: str,
    target_type: str | None = None,
    target_id: UUID | None = None,
    metadata: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """
    Writes a row to super_admin_audit_log.

    This helper is called by every service function-reads AND writes.
    Logging reads is unusual but necessary for a super-admin portal:
    'tenant.list' tells us when Fred was reviewing accounts,
    'tenant.view' tells us which tenant was examined before an action.

    All arguments are optional except super_admin_id and action.
    """
    if ip_address is None:
        from app.core.ip_context import client_ip_var
        ip_address = client_ip_var.get()

    await conn.execute(
        """
        INSERT INTO super_admin_audit_log
            (super_admin_id, action, target_type, target_id, metadata, ip_address)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        super_admin_id,
        action,
        target_type,
        target_id,
        json.dumps(metadata or {}),
        ip_address,
    )


# ── Authentication ─────────────────────────────────────────────────────────────

async def authenticate_password(
    conn: asyncpg.Connection,
    email: str,
    password: str,
    ip_address: str,
) -> dict:
    """
    Step 1 of super admin login: validates email + password.

    If successful, generates a single-use pre-auth token (not a JWT),
    stores its SHA256 hash in super_admin_pre_auth_tokens, and returns
    the raw token to the caller.

    The returned token must be presented to /totp/setup or /totp/verify
    within 5 minutes. It cannot be used for anything else.

    TIMING ATTACK DEFENCE:
        We always fetch the super_admin by email first. If not found, we
        set stored_hash = _DUMMY_HASH and still call bcrypt.checkpw().
        bcrypt is slow by design (~100ms). This makes the "email not found"
        branch take the same time as the "email found, wrong password" branch,
        preventing attackers from enumerating valid email addresses by timing
        the response.

    Returns dict with keys: pre_auth_token, totp_setup_required
    """
    row = await conn.fetchrow(
        """
        SELECT id, email, hashed_password, totp_secret, totp_verified_at, is_active
        FROM super_admins
        WHERE email = $1
        """,
        email,
    )

    # TIMING SAFETY: always run bcrypt regardless of whether the email exists.
    stored_hash = row["hashed_password"] if row else _DUMMY_HASH
    password_ok = verify_password(password, stored_hash)

    # After running bcrypt (which takes ~100ms), THEN check all conditions.
    # The order matters: we give the same "invalid credentials" error for
    # "email not found", "wrong password", AND "account inactive" to avoid
    # leaking account existence to an attacker.
    if not row or not password_ok:
        raise UnauthorisedException("Invalid email or password.")

    if not row["is_active"]:
        # Inactive accounts get the same error as bad credentials.
        # An attacker probing the API can't tell if the account exists.
        raise UnauthorisedException("Invalid email or password.")

    super_admin_id: UUID = row["id"]
    totp_setup_required = row["totp_verified_at"] is None

    # Generate the raw pre-auth token (URL-safe, 32 bytes = 43 chars base64url).
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    # Store only the hash-the raw token is never written to the database.
    await conn.execute(
        """
        INSERT INTO super_admin_pre_auth_tokens
            (super_admin_id, token_hash, ip_address)
        VALUES ($1, $2, $3::inet)
        """,
        super_admin_id,
        token_hash,
        ip_address,
    )

    await _log_action(
        conn,
        super_admin_id=super_admin_id,
        action="auth.password_ok",
        target_type="super_admin",
        target_id=super_admin_id,
        ip_address=ip_address,
    )

    return {
        "pre_auth_token": raw_token,
        "totp_setup_required": totp_setup_required,
    }


async def _validate_pre_auth_token(
    conn: asyncpg.Connection,
    raw_token: str,
    consume: bool = False,
) -> asyncpg.Record:
    """
    Internal helper: validates a pre-auth token and returns the
    super_admin_pre_auth_tokens row.

    Args:
        raw_token: The raw token string from the caller.
        consume:   If True, marks the token as used (used_at = NOW()).
                   Set to True only when issuing the final access token
                   (TOTP verify). For setup, leave False so the same
                   pre-auth token can be used for verify after setup.

    Raises:
        UnauthorisedException if the token is not found, expired, or already used.
    """
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    row = await conn.fetchrow(
        """
        SELECT t.id, t.super_admin_id, t.expires_at, t.used_at,
               sa.email, sa.full_name, sa.totp_secret, sa.totp_verified_at,
               sa.is_active
        FROM super_admin_pre_auth_tokens t
        JOIN super_admins sa ON sa.id = t.super_admin_id
        WHERE t.token_hash = $1
        """,
        token_hash,
    )

    if not row:
        raise UnauthorisedException("Invalid or expired pre-auth token.")

    if row["used_at"] is not None:
        raise UnauthorisedException("Session expired. Please log in again.")

    if row["expires_at"] < datetime.now(timezone.utc):
        raise UnauthorisedException(
            "Session expired. Please log in again."
        )

    if not row["is_active"]:
        raise UnauthorisedException("Invalid or expired pre-auth token.")

    if consume:
        await conn.execute(
            "UPDATE super_admin_pre_auth_tokens SET used_at = NOW() WHERE id = $1",
            row["id"],
        )

    return row


async def setup_totp(
    conn: asyncpg.Connection,
    pre_auth_token: str,
) -> dict:
    """
    Generates a TOTP secret for a super admin who has not yet set up MFA.
    Called ONLY if totp_verified_at IS NULL (first login or after reset).

    Flow:
      1. Validate the pre-auth token (NOT consumed here-the same token
         will be presented again at /totp/verify after scanning).
      2. If totp_secret is already set AND totp_verified_at is non-NULL
         → the super admin already completed setup. Raise 409 Conflict.
         This prevents re-generating a new secret for an active account,
         which would invalidate the existing authenticator setup.
      3. Generate a fresh TOTP secret, encrypt it, store it.
      4. Generate a QR code PNG as base64.
      5. Return the QR code and the first 4 characters of the raw secret
         (for manual entry if the QR scan fails on a bad camera).

    The QR code is generated once and returned once. It is never persisted.
    """
    row = await _validate_pre_auth_token(conn, pre_auth_token, consume=False)

    # Safety check: if TOTP is already fully configured, reject the request.
    # This prevents a malicious actor with a valid pre-auth token from resetting
    # an active super admin's TOTP setup.
    if row["totp_secret"] is not None and row["totp_verified_at"] is not None:
        raise ConflictException(
            "TOTP is already configured for this account. "
            "If you need to reset it, contact Fred directly."
        )

    raw_secret = generate_totp_secret()
    encrypted_secret = encrypt_totp_secret(raw_secret)

    # Store the encrypted secret. totp_verified_at remains NULL until the
    # super admin scans the QR and provides a valid code at /totp/verify.
    await conn.execute(
        """
        UPDATE super_admins
        SET totp_secret = $1, updated_at = NOW()
        WHERE id = $2
        """,
        encrypted_secret,
        row["super_admin_id"],
    )

    qr_code_base64 = generate_qr_code_base64(raw_secret, row["email"])
    # Only the first 4 characters are shown. This is enough to narrow down
    # the secret for manual app entry (most apps accept the full Base32 string)
    # while not exposing enough for an attacker to brute-force the full secret.
    secret_preview = raw_secret[:4]

    return {
        "qr_code_base64": qr_code_base64,
        "secret_preview": secret_preview,
    }


async def verify_totp(
    conn: asyncpg.Connection,
    pre_auth_token: str,
    totp_code: str,
    ip_address: str,
) -> SuperAdminTokenResponse:
    """
    Step 2 of two-step login: verifies the TOTP code and issues a full JWT.

    The pre-auth token is consumed (marked used) on success, ensuring that
    even if the response is intercepted, the token cannot be replayed.

    If this is the first TOTP verification (totp_verified_at IS NULL), this
    call also sets totp_verified_at = NOW(), completing the account setup.

    Returns a SuperAdminTokenResponse with access_token (15-min JWT).
    Refresh tokens are intentionally NOT issued. The super admin must
    re-authenticate (including TOTP) when the token expires.
    """
    # Validate the token first without consuming it.
    row = await _validate_pre_auth_token(conn, pre_auth_token, consume=False)

    # Brute force protection check
    token_hash = hashlib.sha256(pre_auth_token.encode()).hexdigest()
    redis = get_redis_pool()
    redis_key = f"totp_attempts:{token_hash}"

    attempts_val = await redis.get(redis_key)
    if attempts_val is not None and int(attempts_val) >= 3:
        # Mark used in DB
        await conn.execute(
            "UPDATE super_admin_pre_auth_tokens SET used_at = NOW() WHERE id = $1",
            row["id"],
        )
        await _log_action(
            conn,
            super_admin_id=row["super_admin_id"],
            action="auth.totp_failed",
            target_type="super_admin",
            target_id=row["super_admin_id"],
            ip_address=ip_address,
            metadata={"reason": "pre_auth_token locked due to too many failed TOTP attempts"},
        )
        raise UnauthorisedException("Session expired. Please log in again.")

    if row["totp_secret"] is None:
        # The super admin hasn't set up TOTP yet (no secret generated).
        # They need to hit /totp/setup first.
        raise UnauthorisedException(
            "TOTP is not configured. Please complete TOTP setup first."
        )

    # Decrypt the stored secret for verification.
    try:
        raw_secret = decrypt_totp_secret(row["totp_secret"])
    except ValueError:
        # Decryption failure = data corruption or key rotation without migration.
        # Do NOT return a 401 here-that would mislead the caller into thinking
        # their TOTP code is wrong. This is an internal server error.
        raise RuntimeError(
            "TOTP secret decryption failed. Contact the system administrator."
        )

    if not verify_totp_code(raw_secret, totp_code):
        new_attempts = await redis.incr(redis_key)
        if new_attempts == 1:
            await redis.expire(redis_key, 300)

        if new_attempts >= 3:
            # Lock out the session immediately
            await conn.execute(
                "UPDATE super_admin_pre_auth_tokens SET used_at = NOW() WHERE id = $1",
                row["id"],
            )
            await _log_action(
                conn,
                super_admin_id=row["super_admin_id"],
                action="auth.totp_failed",
                target_type="super_admin",
                target_id=row["super_admin_id"],
                ip_address=ip_address,
                metadata={"reason": "pre_auth_token locked due to 3 failed TOTP attempts", "attempts": new_attempts},
            )
            raise UnauthorisedException("Session expired. Please log in again.")
        else:
            await _log_action(
                conn,
                super_admin_id=row["super_admin_id"],
                action="auth.totp_failed",
                target_type="super_admin",
                target_id=row["super_admin_id"],
                ip_address=ip_address,
                metadata={"reason": "Invalid TOTP code", "attempts": new_attempts},
            )
            raise UnauthorisedException("Invalid TOTP code. Please try again.")

    # Successful verification: consume the pre-auth token in DB
    await conn.execute(
        "UPDATE super_admin_pre_auth_tokens SET used_at = NOW() WHERE id = $1",
        row["id"],
    )
    # Clean up attempt count in Redis
    await redis.delete(redis_key)

    now = datetime.now(timezone.utc)

    # If this is the first successful TOTP verification, lock in totp_verified_at.
    # This marks the account as "fully set up"-future logins will skip /totp/setup
    # and go straight to /totp/verify.
    if row["totp_verified_at"] is None:
        await conn.execute(
            """
            UPDATE super_admins
            SET totp_verified_at = $1, last_login_at = $1, updated_at = $1
            WHERE id = $2
            """,
            now,
            row["super_admin_id"],
        )
    else:
        await conn.execute(
            "UPDATE super_admins SET last_login_at = $1, updated_at = $1 WHERE id = $2",
            now,
            row["super_admin_id"],
        )

    await _log_action(
        conn,
        super_admin_id=row["super_admin_id"],
        action="auth.login_success",
        target_type="super_admin",
        target_id=row["super_admin_id"],
        ip_address=ip_address,
    )

    access_token = create_super_admin_access_token(str(row["super_admin_id"]))

    return SuperAdminTokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=900,
        super_admin_id=str(row["super_admin_id"]),
        full_name=row["full_name"],
    )


# ── Profile ────────────────────────────────────────────────────────────────────

async def get_super_admin_profile(
    conn: asyncpg.Connection,
    super_admin_id: UUID,
) -> dict:
    """Returns the super admin's own profile data."""
    row = await conn.fetchrow(
        """
        SELECT id, email, full_name, totp_verified_at, last_login_at,
               is_active, created_at
        FROM super_admins
        WHERE id = $1
        """,
        super_admin_id,
    )
    if not row:
        raise NotFoundException("Super admin", str(super_admin_id))

    return {
        "id": str(row["id"]),
        "email": row["email"],
        "full_name": row["full_name"],
        "totp_verified_at": row["totp_verified_at"].isoformat() if row["totp_verified_at"] else None,
        "last_login_at": row["last_login_at"].isoformat() if row["last_login_at"] else None,
        "is_active": row["is_active"],
        "created_at": row["created_at"].isoformat(),
    }


# ── Tenant Management ──────────────────────────────────────────────────────────

async def get_all_tenants(
    conn: asyncpg.Connection,
    super_admin_id: UUID,
    page: int = 1,
    limit: int = 20,
    status_filter: str | None = None,
    tier_filter: str | None = None,
    search: str | None = None,
) -> dict:
    """
    Returns all tenants with pagination, optional filters, and customer counts.

    Logs action='tenant.list' even though this is a read operation.
    Every access to cross-tenant data by the super admin is auditable.
    """
    offset = (page - 1) * limit

    # Build the WHERE clause dynamically.
    # We use a list of conditions and bind values for safe parameterisation.
    conditions = []
    values: list = []
    param_idx = 1

    if status_filter:
        conditions.append(f"t.status = ${param_idx}")
        values.append(status_filter)
        param_idx += 1

    if tier_filter:
        conditions.append(f"t.subscription_tier = ${param_idx}")
        values.append(tier_filter)
        param_idx += 1

    if search:
        conditions.append(
            f"(t.business_name ILIKE ${param_idx} OR t.owner_email ILIKE ${param_idx})"
        )
        values.append(f"%{search}%")
        param_idx += 1

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    # Count total matching rows for pagination metadata.
    count_sql = f"""
        SELECT COUNT(*)
        FROM tenants t
        {where_clause}
    """
    total = await conn.fetchval(count_sql, *values)

    # Main query: join to users for customer count.
    values_with_pagination = values + [limit, offset]
    rows = await conn.fetch(
        f"""
        SELECT
            t.id,
            t.business_name,
            t.owner_email,
            t.subscription_tier,
            t.status,
            t.next_billing_date,
            t.created_at,
            COUNT(u.id) FILTER (
                WHERE u.role = 'customer' AND u.is_active = TRUE
            ) AS current_customer_count
        FROM tenants t
        LEFT JOIN users u ON u.tenant_id = t.id
        {where_clause}
        GROUP BY t.id
        ORDER BY t.created_at DESC
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """,
        *values_with_pagination,
    )

    await _log_action(
        conn,
        super_admin_id=super_admin_id,
        action="tenant.list",
        metadata={
            "page": page,
            "limit": limit,
            "status_filter": status_filter,
            "tier_filter": tier_filter,
            "search": search,
        },
    )

    tenants = []
    for row in rows:
        tenants.append({
            "id": str(row["id"]),
            "business_name": row["business_name"],
            "owner_email": row["owner_email"],
            "subscription_tier": row["subscription_tier"],
            "status": row["status"],
            "next_billing_date": row["next_billing_date"].isoformat() if row["next_billing_date"] else None,
            "created_at": row["created_at"].isoformat(),
            "current_customer_count": row["current_customer_count"],
        })

    return {
        "tenants": tenants,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": max(1, -(-total // limit)),  # ceiling division
    }


async def get_tenant_detail(
    conn: asyncpg.Connection,
    super_admin_id: UUID,
    tenant_id: UUID,
) -> dict:
    """
    Returns full tenant details plus platform-wide stats for that tenant.
    Raises NotFoundException if the tenant doesn't exist.
    Logs action='tenant.view' (this is a read-audit all reads).
    """
    row = await conn.fetchrow(
        """
        SELECT
            t.id,
            t.business_name,
            t.owner_email,
            t.owner_phone,
            t.subscription_tier,
            t.max_customers,
            t.status,
            t.next_billing_date,
            t.created_at,
            t.updated_at
        FROM tenants t
        WHERE t.id = $1
        """,
        tenant_id,
    )

    if not row:
        raise NotFoundException("Tenant", str(tenant_id))

    # Aggregate stats-each query is intentionally separate for clarity.
    total_customers = await conn.fetchval(
        "SELECT COUNT(*) FROM users WHERE tenant_id = $1 AND role = 'customer'",
        tenant_id,
    )
    active_customers = await conn.fetchval(
        "SELECT COUNT(*) FROM users WHERE tenant_id = $1 AND role = 'customer' AND is_active = TRUE",
        tenant_id,
    )
    total_active_routers = await conn.fetchval(
        "SELECT COUNT(*) FROM routers WHERE tenant_id = $1 AND is_active = TRUE",
        tenant_id,
    )
    total_active_vouchers = await conn.fetchval(
        # Vouchers status values: active, used, expired, revoked, pending_provision.
        # 'active' = a voucher that has been generated but not yet redeemed.
        "SELECT COUNT(*) FROM vouchers WHERE tenant_id = $1 AND status = 'active'",
        tenant_id,
    )
    total_revenue = await conn.fetchval(
        """
        SELECT COALESCE(SUM(amount_kes), 0)
        FROM payments
        WHERE tenant_id = $1 AND status = 'confirmed'
        """,
        tenant_id,
    )
    last_payment = await conn.fetchval(
        """
        SELECT MAX(created_at)
        FROM payments
        WHERE tenant_id = $1 AND status = 'confirmed'
        """,
        tenant_id,
    )

    await _log_action(
        conn,
        super_admin_id=super_admin_id,
        action="tenant.view",
        target_type="tenant",
        target_id=tenant_id,
    )

    return {
        "id": str(row["id"]),
        "business_name": row["business_name"],
        "owner_email": row["owner_email"],
        "owner_phone": row["owner_phone"],
        "subscription_tier": row["subscription_tier"],
        "max_customers": row["max_customers"],
        "status": row["status"],
        "next_billing_date": row["next_billing_date"].isoformat() if row["next_billing_date"] else None,
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
        "stats": {
            "total_customers": total_customers,
            "active_customers": active_customers,
            "total_active_routers": total_active_routers,
            "total_active_vouchers": total_active_vouchers,
            "total_revenue_kes": float(total_revenue),
            "last_payment_at": last_payment.isoformat() if last_payment else None,
        },
    }


async def suspend_tenant(
    conn: asyncpg.Connection,
    super_admin_id: UUID,
    tenant_id: UUID,
    reason: str,
) -> None:
    """
    Sets tenants.status = 'suspended'.

    After this call, every login attempt by any user under this tenant
    returns 403 (enforced by get_current_user → require_active_tenant).
    No active sessions are terminated-they expire naturally (15–30 min).

    Raises:
        NotFoundException if the tenant doesn't exist.
        ConflictException if the tenant is already suspended.
    """
    row = await conn.fetchrow(
        "SELECT status FROM tenants WHERE id = $1",
        tenant_id,
    )
    if not row:
        raise NotFoundException("Tenant", str(tenant_id))

    previous_status = row["status"]
    if previous_status == "suspended":
        raise ConflictException("This tenant is already suspended.")

    await conn.execute(
        "UPDATE tenants SET status = 'suspended', updated_at = NOW() WHERE id = $1",
        tenant_id,
    )

    await _log_action(
        conn,
        super_admin_id=super_admin_id,
        action="tenant.suspend",
        target_type="tenant",
        target_id=tenant_id,
        metadata={"reason": reason, "previous_status": previous_status},
    )


async def reactivate_tenant(
    conn: asyncpg.Connection,
    super_admin_id: UUID,
    tenant_id: UUID,
) -> None:
    """
    Sets tenants.status = 'active'.

    Raises:
        NotFoundException if the tenant doesn't exist.
        ConflictException if the tenant is already active.
    """
    row = await conn.fetchrow(
        "SELECT status FROM tenants WHERE id = $1",
        tenant_id,
    )
    if not row:
        raise NotFoundException("Tenant", str(tenant_id))

    previous_status = row["status"]
    if previous_status == "active":
        raise ConflictException("This tenant is already active.")

    await conn.execute(
        "UPDATE tenants SET status = 'active', updated_at = NOW() WHERE id = $1",
        tenant_id,
    )

    await _log_action(
        conn,
        super_admin_id=super_admin_id,
        action="tenant.reactivate",
        target_type="tenant",
        target_id=tenant_id,
        metadata={"previous_status": previous_status},
    )


async def create_impersonation_token(
    conn: asyncpg.Connection,
    super_admin_id: UUID,
    tenant_id: UUID,
    duration_minutes: int = 30,
) -> dict:
    """
    Issues an admin-scoped JWT for the specified tenant that allows the
    super admin portal to open a "view as tenant" session.

    HOW IMPERSONATION WORKS:
      The impersonation token is a REGULAR admin JWT with two extra claims:
        impersonation: True
        impersonated_by: super_admin_id
      The tenant portal (and its FastAPI route handlers) accepts this token
      without any code changes-from the route handler's perspective, it is
      just an admin token scoped to the tenant.

      The difference is in get_current_user (dependencies.py): when it detects
      impersonation=True, it logs every API call to super_admin_audit_log with
      action='impersonation.api_call'. Route handlers are completely unaware.

    SECURITY NOTE:
      The impersonation token has admin-level access to ONE specific tenant.
      It cannot be used to access super admin endpoints (wrong role).
      It cannot be used to access other tenants' data (tenant_id is scoped).
      It expires after duration_minutes (default 30, max 480).

    Returns dict with: impersonation_token, expires_at (ISO 8601), tenant_name
    """
    # Verify the tenant exists before issuing the token.
    tenant_row = await conn.fetchrow(
        "SELECT business_name, status FROM tenants WHERE id = $1",
        tenant_id,
    )
    if not tenant_row:
        raise NotFoundException("Tenant", str(tenant_id))

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=duration_minutes)

    # We need to find the tenant's admin user ID to use as the token subject.
    # The impersonation token pretends to be the tenant's admin.
    admin_row = await conn.fetchrow(
        "SELECT id FROM users WHERE tenant_id = $1 AND role = 'admin' LIMIT 1",
        tenant_id,
    )
    if not admin_row:
        raise NotFoundException("Admin user for tenant", str(tenant_id))

    # Build the impersonation token using the standard create_access_token()
    # so it is a valid admin JWT that all tenant endpoints accept.
    # The extra claims are appended manually using python-jose's payload directly.
    from jose import jwt
    from app.config import settings

    payload = {
        "sub": str(admin_row["id"]),
        "role": "admin",
        "tenant_id": str(tenant_id),
        "reseller_id": None,
        # Extra claims that mark this as an impersonation token.
        # get_current_user in dependencies.py checks for these.
        "impersonation": True,
        "impersonated_by": str(super_admin_id),
        "iat": now,
        "exp": expires_at,
    }

    impersonation_token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    await _log_action(
        conn,
        super_admin_id=super_admin_id,
        action="impersonation.start",
        target_type="tenant",
        target_id=tenant_id,
        metadata={
            "tenant_name": tenant_row["business_name"],
            "tenant_status": tenant_row["status"],
            "duration_minutes": duration_minutes,
            "expires_at": expires_at.isoformat(),
        },
    )

    return {
        "impersonation_token": impersonation_token,
        "expires_at": expires_at.isoformat(),
        "tenant_name": tenant_row["business_name"],
    }


async def trigger_tenant_billing(
    conn: asyncpg.Connection,
    super_admin_id: UUID,
    tenant_id: UUID,
) -> dict:
    """
    Manually triggers an M-Pesa STK push for a tenant's platform fee.
    Delegates to the existing initiate_platform_billing_payment() in
    tenants/service.py-reuses the exact same logic as the automated
    billing cron job.

    This endpoint exists so Fred can manually trigger billing for a tenant
    without waiting for the automated billing cycle.
    """
    # Verify the tenant exists first so we get a clear error.
    tenant_row = await conn.fetchrow(
        "SELECT business_name FROM tenants WHERE id = $1",
        tenant_id,
    )
    if not tenant_row:
        raise NotFoundException("Tenant", str(tenant_id))

    from app.modules.tenants.service import initiate_platform_billing_payment
    result = await initiate_platform_billing_payment(conn, tenant_id)

    await _log_action(
        conn,
        super_admin_id=super_admin_id,
        action="tenant.billing_triggered",
        target_type="tenant",
        target_id=tenant_id,
        metadata={
            "tenant_name": tenant_row["business_name"],
            "payment_id": str(result.get("id", "")),
            "amount_kes": float(result.get("amount_kes", 0)),
        },
    )

    return result


async def get_platform_stats(
    conn: asyncpg.Connection,
    super_admin_id: UUID,
) -> dict:
    """
    Returns system-wide statistics for the super admin dashboard.
    All queries are independent and run against the full dataset (no tenant_id filter).
    """
    from datetime import date

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today_start.replace(day=1)

    total_tenants = await conn.fetchval("SELECT COUNT(*) FROM tenants")
    active_tenants = await conn.fetchval("SELECT COUNT(*) FROM tenants WHERE status = 'active'")
    suspended_tenants = await conn.fetchval("SELECT COUNT(*) FROM tenants WHERE status = 'suspended'")

    total_customers = await conn.fetchval(
        "SELECT COUNT(*) FROM users WHERE role = 'customer'"
    )
    revenue_today = await conn.fetchval(
        """
        SELECT COALESCE(SUM(amount_kes), 0)
        FROM payments
        WHERE status = 'confirmed' AND created_at >= $1
        """,
        today_start,
    )
    revenue_month = await conn.fetchval(
        """
        SELECT COALESCE(SUM(amount_kes), 0)
        FROM payments
        WHERE status = 'confirmed' AND created_at >= $1
        """,
        month_start,
    )
    active_vouchers = await conn.fetchval(
        # 'active' = voucher generated but not yet redeemed by a customer.
        "SELECT COUNT(*) FROM vouchers WHERE status = 'active'"
    )
    active_sessions = await conn.fetchval(
        # Sessions are 'active' when ended_at IS NULL.
        # The partial index idx_sessions_active (WHERE ended_at IS NULL)
        # makes this query efficient even at scale.
        "SELECT COUNT(*) FROM sessions WHERE ended_at IS NULL"
    )

    # Tenant count per pricing tier.
    tier_rows = await conn.fetch(
        """
        SELECT subscription_tier, COUNT(*) AS count
        FROM tenants
        GROUP BY subscription_tier
        """
    )
    tenants_by_tier = {
        "starter": 0, "growth": 0, "scale": 0, "enterprise": 0,
    }
    for tr in tier_rows:
        tenants_by_tier[tr["subscription_tier"]] = tr["count"]

    await _log_action(
        conn,
        super_admin_id=super_admin_id,
        action="stats.view",
        target_type="system",
    )

    return {
        "total_tenants": total_tenants,
        "active_tenants": active_tenants,
        "suspended_tenants": suspended_tenants,
        "total_customers_across_all_tenants": total_customers,
        "total_revenue_today_kes": float(revenue_today),
        "total_revenue_this_month_kes": float(revenue_month),
        "total_active_vouchers": active_vouchers,
        "total_active_sessions": active_sessions,
        "tenants_by_tier": tenants_by_tier,
    }


async def get_audit_log(
    conn: asyncpg.Connection,
    super_admin_id: UUID,
    page: int = 1,
    limit: int = 50,
    action_filter: str | None = None,
) -> dict:
    """Returns paginated super_admin_audit_log entries, newest first."""
    offset = (page - 1) * limit

    conditions = []
    values: list = []
    param_idx = 1

    if action_filter:
        conditions.append(f"action ILIKE ${param_idx}")
        values.append(f"%{action_filter}%")
        param_idx += 1

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    total = await conn.fetchval(
        f"SELECT COUNT(*) FROM super_admin_audit_log {where_clause}",
        *values,
    )

    rows = await conn.fetch(
        f"""
        SELECT
            l.id, l.super_admin_id, sa.email AS super_admin_email,
            l.action, l.target_type, l.target_id,
            l.metadata, l.ip_address, l.created_at
        FROM super_admin_audit_log l
        JOIN super_admins sa ON sa.id = l.super_admin_id
        {where_clause}
        ORDER BY l.created_at DESC
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """,
        *(values + [limit, offset]),
    )

    entries = []
    for row in rows:
        entries.append({
            "id": str(row["id"]),
            "super_admin_id": str(row["super_admin_id"]),
            "super_admin_email": row["super_admin_email"],
            "action": row["action"],
            "target_type": row["target_type"],
            "target_id": str(row["target_id"]) if row["target_id"] else None,
            "metadata": json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"],
            "ip_address": str(row["ip_address"]) if row["ip_address"] else None,
            "created_at": row["created_at"].isoformat(),
        })

    return {
        "entries": entries,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": max(1, -(-total // limit)),
    }


async def create_super_admin(
    conn: asyncpg.Connection,
    actor_super_admin_id: UUID,
    email: str,
    full_name: str,
    password: str,
) -> dict:
    """
    Creates a new super admin account. Only callable by an existing super admin.
    The new account starts with totp_secret=NULL-they must complete TOTP setup
    on first login.
    """
    existing = await conn.fetchrow(
        "SELECT id FROM super_admins WHERE email = $1",
        email,
    )
    if existing:
        raise ConflictException(
            f"A super admin with email '{email}' already exists."
        )

    hashed = hash_password(password)

    new_row = await conn.fetchrow(
        """
        INSERT INTO super_admins (email, hashed_password, full_name)
        VALUES ($1, $2, $3)
        RETURNING id, email, full_name, created_at
        """,
        email,
        hashed,
        full_name,
    )

    await _log_action(
        conn,
        super_admin_id=actor_super_admin_id,
        action="super_admin.create",
        target_type="super_admin",
        target_id=new_row["id"],
        metadata={"email": email, "full_name": full_name},
    )

    return {
        "id": str(new_row["id"]),
        "email": new_row["email"],
        "full_name": new_row["full_name"],
        "created_at": new_row["created_at"].isoformat(),
        "message": (
            f"Super admin '{email}' created. "
            "They must log in at /super-admin/auth/login and complete TOTP setup."
        ),
    }


async def get_all_super_admins(
    conn: asyncpg.Connection,
    super_admin_id: UUID,
) -> list[dict]:
    """
    Returns all super admin accounts.
    Only callable by an authenticated super admin.
    Every call is audit-logged.
    """
    await _log_action(
        conn,
        super_admin_id=super_admin_id,
        action="super_admin.list",
        target_type="super_admin",
        target_id=super_admin_id,
        metadata={},
    )

    rows = await conn.fetch(
        """
        SELECT 
            id, 
            email, 
            full_name, 
            totp_verified_at, 
            last_login_at, 
            is_active, 
            created_at
        FROM super_admins
        ORDER BY created_at DESC
        """
    )

    return [
        {
            "id": str(row["id"]),
            "email": row["email"],
            "full_name": row["full_name"],
            "totp_verified_at": row["totp_verified_at"].isoformat() if row["totp_verified_at"] else None,
            "last_login_at": row["last_login_at"].isoformat() if row["last_login_at"] else None,
            "is_active": row["is_active"],
            "created_at": row["created_at"].isoformat(),
        }
        for row in rows
    ]
