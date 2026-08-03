"""
app/dependencies.py
====================
FastAPI dependency functions — the enforcement gate for multi-tenancy.

DEPENDENCY GRAPH
----------------
  request
    ↓
  oauth2_scheme (extracts Bearer token)
    ↓
  _decode_token(token) → payload dict
    ↓
  get_current_user(payload) → {user_id, role, tenant_id, impersonated_by, ...}
    ↓
  get_current_tenant_id(user) → str UUID          ← enforcement gate
    ↓
  require_role(*roles)(user, tenant_id) → user dict
    ↓
  route handler receives user dict with validated tenant_id

SUPER ADMIN SEPARATION
  Super admin tokens carry role="super_admin" and NO tenant_id.
  get_current_user returns them unchanged; get_current_tenant_id rejects
  them with 403 on any tenant-scoped endpoint. Super admins must use an
  impersonation token (role="admin" + tenant_id) to access tenant data.

IMPERSONATION TRANSPARENCY
  Impersonation tokens (impersonation=True) trigger audit logging in
  get_current_user without affecting route handlers or service functions.
"""

import json
import logging
from uuid import UUID

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import ExpiredSignatureError, JWTError, jwt

from app.config import settings
from app.core.exceptions import UnauthorisedException, ForbiddenException

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def _decode_token(token: str) -> dict:
    """
    Decodes and validates a JWT access token.

    Raises UnauthorisedException on:
      - Expired token (ExpiredSignatureError)
      - Invalid signature or malformed token (JWTError)
      - Missing 'sub' claim
      - Missing 'role' claim

    Returns the raw payload dict.
    Does NOT raise on missing tenant_id — super_admin tokens legitimately
    have no tenant_id claim.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except ExpiredSignatureError:
        raise UnauthorisedException("Token has expired. Please log in again.")
    except JWTError:
        raise UnauthorisedException("Could not validate credentials.")

    if payload.get("sub") is None:
        raise UnauthorisedException("Token is missing subject claim.")

    if payload.get("role") is None:
        raise UnauthorisedException("Token is missing role claim.")

    return payload


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Decodes the JWT and returns the current user's identity dict.

    Returns:
        user_id         - str UUID from JWT 'sub'
        role            - admin | reseller | customer | super_admin
        tenant_id       - str UUID or None (None for super_admin)
        impersonated_by - str UUID or None (set for impersonation tokens)
        reseller_id     - str UUID or None

    Does NOT enforce tenant_id presence — that is get_current_tenant_id's job.
    Super admin tokens are returned as-is so get_current_super_admin can use
    _decode_token independently on /super-admin/* routes.
    """
    payload = _decode_token(token)

    user_dict = {
        "user_id": payload["sub"],
        "role": payload["role"],
        "tenant_id": payload.get("tenant_id"),
        "impersonated_by": payload.get("impersonated_by"),
        "reseller_id": payload.get("reseller_id"),
    }

    if payload.get("impersonation") is True:
        impersonated_by_str: str | None = payload.get("impersonated_by")
        tenant_id_str: str | None = payload.get("tenant_id")
        if impersonated_by_str and tenant_id_str:
            try:
                await _log_impersonation_call(
                    super_admin_id=UUID(impersonated_by_str),
                    tenant_id=UUID(tenant_id_str),
                )
            except Exception:
                logger.error(
                    "Failed to write impersonation audit log",
                    exc_info=True,
                )

    return user_dict


async def get_current_tenant_id(
    current_user: dict = Depends(get_current_user),
) -> str:
    """
    Extracts and validates tenant_id from the authenticated user dict.

    This is the enforcement gate for all tenant-scoped endpoints.

    Raises ForbiddenException if role == 'super_admin' and tenant_id is None.
    WHY: A super admin using their own token on a tenant endpoint would have
    unrestricted cross-tenant access. The impersonation path is the only
    allowed route for super admins to access tenant data (T1 prevention).

    Raises UnauthorisedException if tenant_id is None for any other role.

    Validates tenant_id is a well-formed UUID before returning to prevent
    UUID injection via crafted JWT tokens.
    """
    role = current_user["role"]
    tenant_id: str | None = current_user.get("tenant_id")

    if role == "super_admin" and tenant_id is None:
        raise ForbiddenException(
            "Super admin tokens cannot access tenant endpoints directly. "
            "Use an impersonation token scoped to a specific tenant."
        )

    if tenant_id is None:
        raise UnauthorisedException("Token missing tenant context.")

    try:
        UUID(tenant_id)
    except ValueError:
        raise UnauthorisedException("Token contains an invalid tenant identifier.")

    return tenant_id


async def _assert_tenant_active(tenant_id: str) -> None:
    """
    Checks whether the tenant referenced in the token is active.
    Suspended or cancelled tenants are blocked from all protected endpoints.
    """
    from app.database import get_db

    async with get_db() as conn:
        row = await conn.fetchrow(
            "SELECT status FROM tenants WHERE id = $1",
            UUID(tenant_id),
        )

    if row is None:
        raise UnauthorisedException("Tenant account not found.")

    if row["status"] == "suspended":
        raise ForbiddenException(
            "Your Frixel Connect account has been suspended. "
            "Please contact Frixel Connect support to resolve your outstanding balance."
        )

    if row["status"] == "cancelled":
        raise ForbiddenException(
            "Your Frixel Connect account has been cancelled. "
            "Please contact Frixel Connect support to reinstate your account."
        )


def require_role(*allowed_roles: str):
    """
    Dependency factory. Enforces role-based access at the route level.

    Chain:
      1. get_current_user      — decode JWT
      2. get_current_tenant_id — validate tenant_id (blocks super_admin bypass)
      3. _assert_tenant_active — block suspended/cancelled tenants
      4. role check            — ForbiddenException if role not allowed

    Every route using require_role therefore has tenant_id validated before
    any handler code runs, even when tenant_id is not listed explicitly in
    the route signature.

    Usage:
        @router.get("/admin/users")
        async def list_users(user=Depends(require_role("admin"))):
            tenant_id = UUID(user["tenant_id"])
            ...
    """

    async def role_checker(
        current_user: dict = Depends(get_current_user),
        tenant_id: str = Depends(get_current_tenant_id),
    ) -> dict:
        await _assert_tenant_active(tenant_id)

        if current_user["role"] not in allowed_roles:
            raise ForbiddenException(
                detail=(
                    f"Required role: {allowed_roles}. "
                    f"Your role: {current_user['role']}"
                )
            )

        return current_user

    return role_checker


async def _log_impersonation_call(
    super_admin_id: UUID,
    tenant_id: UUID,
) -> None:
    """
    Writes an impersonation.api_call entry to super_admin_audit_log.
    Called transparently from get_current_user when an impersonation token
    is detected. Opens a short-lived DB connection because dependencies do
    not share the route handler's connection.
    """
    from app.database import get_db
    from app.core.ip_context import client_ip_var

    ip_addr = client_ip_var.get()

    try:
        async with get_db() as conn:
            await conn.execute(
                """
                INSERT INTO super_admin_audit_log
                    (super_admin_id, action, target_type, target_id, metadata, ip_address)
                VALUES ($1, 'impersonation.api_call', 'tenant', $2, $3, $4)
                """,
                super_admin_id,
                tenant_id,
                json.dumps({"tenant_id": str(tenant_id)}),
                ip_addr,
            )
    except Exception:
        logger.error(
            "DB error writing impersonation audit log",
            exc_info=True,
        )


async def get_current_super_admin(
    token: str = Depends(oauth2_scheme),
) -> dict:
    """
    Dependency for super admin routes. Validates a super admin JWT.

    Accepts ONLY tokens with role="super_admin". Uses _decode_token for
    consistent JWT validation. Deliberately does NOT call get_current_user
    or get_current_tenant_id — super admin routes live under /super-admin/*.
    """
    payload = _decode_token(token)

    role: str = payload["role"]
    sub: str = payload["sub"]

    if role != "super_admin":
        raise ForbiddenException(
            "This endpoint requires a super admin token. "
            "Super admin tokens are issued only at /super-admin/auth/totp/verify."
        )

    return {
        "super_admin_id": sub,
        "role": "super_admin",
    }
