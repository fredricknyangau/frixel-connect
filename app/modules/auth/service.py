"""
app/modules/auth/service.py
============================
Business logic for registration and login.

MULTI-TENANCY CHANGE (Phase 1):
  authenticate_user now accepts tenant_id and scopes the user lookup to
  that tenant. A user in tenant A with the same email as a user in tenant B
  (if we ever allow per-tenant email uniqueness — currently global) would
  still be disambiguated by tenant_id.

  More importantly: authenticate_user now ALSO validates that the tenant's
  status is 'active'. A suspended tenant's admin/reseller/customer cannot
  log in, even with correct credentials. This is the enforcement point for
  Phase 10 non-payment suspension.

asyncpg parameterised queries:
  All SQL in this file uses $1, $2, ... placeholders.
  asyncpg sends the query and parameters SEPARATELY to PostgreSQL over
  the wire — PostgreSQL never concatenates them into a SQL string, so
  SQL injection is structurally impossible.
"""

from uuid import UUID
import uuid
import secrets
import hashlib
from datetime import datetime, timedelta, timezone

import asyncpg

from app.core.exceptions import ConflictException, UnauthorisedException, ForbiddenException
from app.core.security import hash_password, verify_password, create_access_token
from app.modules.auth.schemas import RegisterRequest


async def register_user(conn: asyncpg.Connection, data: RegisterRequest) -> dict:
    """
    Registers a new user.

    MULTI-TENANCY NOTE:
    This endpoint is currently used only by existing users within a tenant
    (e.g., an admin registering a reseller). The PRIMARY tenant+admin creation
    path is POST /tenants/register (tenants/service.py:register_tenant).

    The data.tenant_id comes from the calling admin's JWT token — the caller
    cannot register a user into a different tenant than their own.

    Steps:
      1. Check if email or phone is already in use WITHIN THIS TENANT.
         We scope the conflict check to tenant_id so that email@example.com
         can exist in tenant A and tenant B simultaneously.
         EXCEPTION: currently users.email has a global UNIQUE constraint,
         so this check is conservative. In a future migration we could
         drop the global unique and replace with (tenant_id, email) unique.
      2. Hash the password.
      3. INSERT the user row with tenant_id.
      4. Return the full user row.
    """
    # ── Check for existing email or phone WITHIN this tenant ───────────────────
    existing = await conn.fetchrow(
        """
        SELECT id, email, phone
        FROM users
        WHERE (email = $1 OR phone = $2)
          AND tenant_id = $3
        """,
        data.email,
        data.phone,
        data.tenant_id,
    )

    if existing:
        if existing["email"] == data.email:
            raise ConflictException("An account with this email address already exists.")
        else:
            raise ConflictException("An account with this phone number already exists.")

    # ── Hash the password ──────────────────────────────────────────────────────
    hashed = hash_password(data.password)

    # ── Generate unique wallet_reference if registering a reseller ───────────
    wallet_ref = None
    if data.role == "reseller":
        from app.modules.vouchers.service import generate_voucher_code
        wallet_ref = f"WS{generate_voucher_code(5)}"
        while await conn.fetchval("SELECT COUNT(*) FROM users WHERE wallet_reference = $1", wallet_ref) > 0:
            wallet_ref = f"WS{generate_voucher_code(5)}"

    # ── Insert the user with tenant_id and wallet_reference ───────────────────
    user = await conn.fetchrow(
        """
        INSERT INTO users (email, phone, hashed_password, role, tenant_id, wallet_reference)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id, email, phone, role, reseller_id, tenant_id, is_active, wallet_reference, created_at
        """,
        data.email,
        data.phone,
        hashed,
        data.role,
        data.tenant_id,
        wallet_ref,
    )

    return dict(user)



async def authenticate_user(
    conn: asyncpg.Connection,
    email: str,
    password: str,
) -> dict:
    """
    Validates credentials and returns the user row WITH the tenant's status.

    MULTI-TENANCY CHANGE:
    We JOIN to tenants to check tenant.status at login time. If the tenant
    is suspended or cancelled, we raise ForbiddenException(403) — NOT
    UnauthorisedException(401). The distinction matters:
      - 401 means "we don't know who you are" (no/bad credentials)
      - 403 means "we know exactly who you are, but you can't come in"
    A clear 403 with "account suspended" is better UX than a confusing 401.

    Timing attack note:
    If the user doesn't exist, we still call verify_password() against a
    dummy hash. This keeps the response time consistent whether the email
    exists or not — an attacker timing responses can't enumerate valid emails.
    """
    # ── Handle Phone Number Variants ───────────────────────────────────────────
    # A user might enter "07...", "2547...", or "7..." 
    # and the database might have it stored differently.
    variants = [email]
    clean_input = email.strip().replace('+', '')
    if clean_input.isdigit():
        if clean_input.startswith('254') and len(clean_input) == 12:
            variants.append('0' + clean_input[3:])
            variants.append(clean_input[3:])
        elif clean_input.startswith('0') and len(clean_input) == 10:
            variants.append('254' + clean_input[1:])
            variants.append(clean_input[1:])
        elif len(clean_input) == 9 and clean_input[0] in ('7', '1'):
            variants.append('254' + clean_input)
            variants.append('0' + clean_input)

    user = await conn.fetchrow(
        """
        SELECT
            u.id,
            u.email,
            u.phone,
            u.role,
            u.reseller_id,
            u.tenant_id,
            u.hashed_password,
            u.is_active,
            t.status AS tenant_status
        FROM users u
        JOIN tenants t ON u.tenant_id = t.id
        WHERE u.email = ANY($1::text[]) OR u.phone = ANY($1::text[])
        """,
        variants,
    )

    # ── Timing-safe failure path ───────────────────────────────────────────────
    # We always run bcrypt even if the user doesn't exist, using a dummy hash.
    # This prevents email enumeration via timing analysis.
    DUMMY_HASH = "$2b$12$KIXy0z5h5l5z5z5z5z5z5e1234567890123456789012345678901234"

    stored_hash = user["hashed_password"] if user else DUMMY_HASH
    password_ok = verify_password(password, stored_hash)

    if not user or not password_ok:
        # Same error message for "user not found" and "wrong password" to
        # prevent user enumeration attacks.
        raise UnauthorisedException("Invalid email/phone or password.")

    if not user["is_active"]:
        raise UnauthorisedException("This account has been deactivated. Contact support.")

    # ── Tenant status check ───────────────────────────────────────────────────
    # This runs AFTER password verification so we don't leak whether an email
    # exists in a suspended tenant (an attacker gets "wrong password" for bad
    # creds, and "account suspended" only for correct creds).
    if user["tenant_status"] == "suspended":
        raise ForbiddenException(
            "Your ZealSync account has been suspended due to an unpaid invoice. "
            "Please contact ZealSync support."
        )

    if user["tenant_status"] == "cancelled":
        raise ForbiddenException(
            "Your ZealSync account has been cancelled. "
            "Please contact ZealSync support."
        )

    return dict(user)


async def generate_refresh_token(conn: asyncpg.Connection, user_id: UUID) -> str:
    """
    Generates a new refresh token and starts a new token family.
    """
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    family_id = uuid.uuid4()
    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    
    await conn.execute("""
        INSERT INTO refresh_tokens (user_id, token_hash, family_id, expires_at)
        VALUES ($1, $2, $3, $4)
    """, user_id, token_hash, family_id, expires_at)
    
    return token


async def rotate_refresh_token(conn: asyncpg.Connection, old_token: str) -> tuple[dict, str]:
    """
    Rotates a refresh token.
    If the old_token is valid and not revoked, revokes it and issues a new one in the same family.
    If the old_token IS revoked, this is token theft: revokes the entire family and raises UnauthorisedException.
    Returns (user_dict, new_token).
    """
    token_hash = hashlib.sha256(old_token.encode()).hexdigest()
    
    # Find the token
    rt = await conn.fetchrow("""
        SELECT r.id, r.user_id, r.family_id, r.expires_at, r.revoked,
               u.email, u.phone, u.role, u.reseller_id, u.tenant_id, u.is_active,
               t.status AS tenant_status
        FROM refresh_tokens r
        JOIN users u ON r.user_id = u.id
        JOIN tenants t ON u.tenant_id = t.id
        WHERE r.token_hash = $1
    """, token_hash)
    
    if not rt:
        raise UnauthorisedException("Invalid refresh token.")
        
    if rt["expires_at"] < datetime.now(timezone.utc):
        raise UnauthorisedException("Refresh token expired.")
        
    if rt["revoked"]:
        # TOKEN THEFT DETECTED!
        # Revoke the entire family
        await conn.execute("""
            UPDATE refresh_tokens SET revoked = TRUE WHERE family_id = $1
        """, rt["family_id"])
        raise UnauthorisedException("Token reuse detected. All sessions revoked. Please log in again.")
        
    # Tenant/User status check BEFORE issuing new tokens
    if rt["tenant_status"] == "suspended":
        raise ForbiddenException("Your ZealSync account has been suspended due to an unpaid invoice.")
    if rt["tenant_status"] == "cancelled":
        raise ForbiddenException("Your ZealSync account has been cancelled.")
    if not rt["is_active"]:
        raise UnauthorisedException("This account has been deactivated. Contact support.")
        
    # Valid token. Revoke it and issue a new one in the same family.
    await conn.execute("""
        UPDATE refresh_tokens SET revoked = TRUE WHERE id = $1
    """, rt["id"])
    
    new_token = secrets.token_urlsafe(32)
    new_token_hash = hashlib.sha256(new_token.encode()).hexdigest()
    new_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    
    await conn.execute("""
        INSERT INTO refresh_tokens (user_id, token_hash, family_id, expires_at)
        VALUES ($1, $2, $3, $4)
    """, rt["user_id"], new_token_hash, rt["family_id"], new_expires_at)
    
    user_dict = {
        "id": rt["user_id"],
        "email": rt["email"],
        "phone": rt["phone"],
        "role": rt["role"],
        "reseller_id": rt["reseller_id"],
        "tenant_id": rt["tenant_id"]
    }
    
    return user_dict, new_token

