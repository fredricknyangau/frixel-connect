"""
app/dependencies.py
====================
FastAPI dependency functions injected into route handlers.

MULTI-TENANCY PATTERN:
  Every route that reads or writes tenant-scoped data must declare:
      current_user: dict = Depends(require_role("admin"))
  The current_user dict now carries tenant_id, so the route handler
  can pass it directly to the service layer:
      await service.some_function(conn, tenant_id=UUID(current_user["tenant_id"]), ...)

  The token is the source of truth for tenant_id. We embed it at login
  time and trust it on every subsequent request. This avoids an extra
  DB lookup per request just to find which tenant the user belongs to.

TENANT SUSPENSION CHECK:
  get_current_user now also checks tenant status. If the tenant is
  'suspended' or 'cancelled', every login attempt under that tenant
  returns 403 with a clear "account suspended" message. This is the
  enforcement point for Phase 10 non-payment suspension.
"""

from uuid import UUID

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.core.exceptions import UnauthorisedException, ForbiddenException
from app.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Decodes the JWT and returns the current user's identity dict.
    Raises 401 if the token is missing, expired, or invalid.

    The returned dict now contains:
        user_id    — str UUID of the user
        role       — "admin" | "reseller" | "customer"
        tenant_id  — str UUID of the tenant this user belongs to
        reseller_id — str UUID or None
    """
    payload = decode_access_token(token)
    if payload is None:
        raise UnauthorisedException()

    user_id: str | None = payload.get("sub")
    role: str | None = payload.get("role")
    tenant_id: str | None = payload.get("tenant_id")

    if user_id is None or role is None or tenant_id is None:
        # tenant_id being absent means this is a pre-Phase-1 token.
        # We reject it to force re-login and get a fresh token with tenant_id.
        raise UnauthorisedException(
            "Token is missing required claims. Please log in again."
        )

    return {
        "user_id": user_id,
        "role": role,
        "tenant_id": tenant_id,
        "reseller_id": payload.get("reseller_id"),
    }


async def get_current_tenant_id(
    current_user: dict = Depends(get_current_user),
) -> UUID:
    """
    Convenience dependency that extracts the tenant_id from the token
    and returns it as a UUID.

    Usage in a route:
        @router.get("/packages")
        async def list_packages(
            tenant_id: UUID = Depends(get_current_tenant_id),
            _user: dict = Depends(require_role("admin")),
        ):
            ...

    Or more commonly, just use current_user["tenant_id"] directly from
    require_role, since both resolve the same token in one chain:
        current_user: dict = Depends(require_role("admin"))
        tenant_id = UUID(current_user["tenant_id"])
    """
    return UUID(current_user["tenant_id"])


def require_role(*allowed_roles: str):
    """
    Dependency factory. Enforces role-based access at the route level.
    Also checks tenant suspension — a suspended tenant's users cannot
    access ANY endpoint regardless of role.

    Usage:
        @router.get("/admin/users")
        async def list_users(user=Depends(require_role("admin"))):
            ...

        @router.get("/reseller/customers")
        async def list_customers(user=Depends(require_role("admin", "reseller"))):
            ...

    The returned dict is the same as get_current_user — it includes tenant_id.
    """
    async def role_checker(current_user: dict = Depends(require_active_tenant)) -> dict:
        # Role check
        if current_user["role"] not in allowed_roles:
            raise ForbiddenException(
                detail=f"Required role: {allowed_roles}. Your role: {current_user['role']}"
            )
        return current_user

    return role_checker


async def require_active_tenant(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Dependency that checks whether the tenant is active.
    Used to block all access for suspended/cancelled tenants.

    NOTE: In Phase 1 this is wired in selectively. Phase 10 will
    use this on every protected route via a global dependency.

    We check tenant status HERE (in a dependency) rather than in
    every service function because:
    1. Service functions run AFTER the connection is acquired from the pool.
       If we block here, we never acquire a connection for suspended tenants —
       this saves DB connections from being consumed by blocked requests.
    2. It is impossible to forget to check tenant status in a new route handler
       if the check is in the dependency chain, not manually in each function.
    """
    from app.database import get_db

    # Import here to avoid circular imports at module load time
    tenant_id = UUID(current_user["tenant_id"])

    async with get_db() as conn:
        row = await conn.fetchrow(
            "SELECT status FROM tenants WHERE id = $1",
            tenant_id,
        )

    if row is None:
        # The tenant referenced in the token no longer exists.
        raise UnauthorisedException("Tenant account not found.")

    if row["status"] == "suspended":
        raise ForbiddenException(
            "Your ZealSync account has been suspended. "
            "Please contact ZealSync support to resolve your outstanding balance."
        )

    if row["status"] == "cancelled":
        raise ForbiddenException(
            "Your ZealSync account has been cancelled. "
            "Please contact ZealSync support to reinstate your account."
        )

    return current_user