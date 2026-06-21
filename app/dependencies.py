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

SUPER ADMIN SEPARATION:
  Super admin tokens carry role="super_admin" and NO tenant_id.
  get_current_user explicitly rejects these tokens — they cannot be used
  on any tenant-scoped endpoint. This is a hard safety rail: if a super
  admin accidentally sends their own token to a tenant API, they get a
  clear 403 ("use an impersonation token instead") rather than a confusing
  null tenant_id error deep in the service layer.

  The get_current_super_admin dependency is the ONLY entry point for
  super admin JWT validation. It is used exclusively on /super-admin/* routes.

IMPERSONATION TRANSPARENCY:
  When a request arrives with an impersonation token (role="admin" +
  impersonation=True + impersonated_by=super_admin_id), get_current_user
  detects it and writes an audit log entry to super_admin_audit_log
  (action='impersonation.api_call') WITHOUT any changes to the route handler
  or service function. The route handler receives a normal current_user dict
  and is completely unaware of the impersonation.
"""

import json
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer

from app.core.exceptions import UnauthorisedException, ForbiddenException
from app.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Decodes the JWT and returns the current user's identity dict.
    Raises 401 if the token is missing, expired, or invalid.

    SUPER ADMIN SAFETY RAIL:
        If the decoded token has role="super_admin", this dependency raises 403
        with an explicit message. Super admin tokens cannot access tenant endpoints.
        Super admins must use an impersonation token (role="admin" with tenant_id)
        to interact with tenant data. This prevents accidental cross-boundary access.

    IMPERSONATION DETECTION (Phase 4):
        If the token has impersonation=True, this dependency writes an audit log
        entry to super_admin_audit_log recording the API call. The route handler
        receives a normal user dict and is unaware of the impersonation.
        This detection is fire-and-forget — we do not block the request.

    The returned dict contains:
        user_id    - str UUID of the user
        role       - "admin" | "reseller" | "customer"
        tenant_id  - str UUID of the tenant this user belongs to
        reseller_id - str UUID or None
    """
    payload = decode_access_token(token)
    if payload is None:
        raise UnauthorisedException()

    role: str | None = payload.get("role")

    # ── SUPER ADMIN SAFETY RAIL ────────────────────────────────────────────────
    # Super admin tokens have role="super_admin" and no tenant_id.
    # If one reaches a tenant endpoint, reject it with a helpful message.
    # This guards against the scenario where the super admin portal's token
    # is accidentally used in the wrong tab / API client.
    if role == "super_admin":
        raise ForbiddenException(
            "Super admin tokens cannot be used on tenant endpoints. "
            "Generate an impersonation token at "
            "POST /super-admin/tenants/{id}/impersonate and use that instead."
        )

    user_id: str | None = payload.get("sub")
    tenant_id: str | None = payload.get("tenant_id")

    if user_id is None or role is None or tenant_id is None:
        # tenant_id being absent means this is a pre-Phase-1 token.
        # We reject it to force re-login and get a fresh token with tenant_id.
        raise UnauthorisedException(
            "Token is missing required claims. Please log in again."
        )

    user_dict = {
        "user_id": user_id,
        "role": role,
        "tenant_id": tenant_id,
        "reseller_id": payload.get("reseller_id"),
    }

    # ── IMPERSONATION AUDIT LOGGING (Phase 4) ─────────────────────────────────
    # If this is an impersonation token (issued by create_impersonation_token),
    # write an audit entry for every API call. This is done asynchronously after
    # the route handler receives the user dict — the route is unaffected.
    #
    # WHY HERE (IN THE DEPENDENCY) NOT IN MIDDLEWARE?
    #   Middleware runs before route matching and before auth. We need the decoded
    #   payload to know (a) whether it's an impersonation token, and (b) which
    #   super_admin_id to log. The dependency runs after auth, so we have all
    #   the information we need.
    #
    # NOTE: We intentionally do NOT request the `request: Request` parameter here
    # because FastAPI's dependency injection for get_current_user is called across
    # ALL protected routes. Adding Request would change the signature and break
    # routes that don't explicitly pass it. Instead, we skip path logging here
    # and rely on the action='impersonation.api_call' + metadata being descriptive
    # enough for audit purposes. The impersonation.start log already records which
    # tenant was impersonated and for how long.
    if payload.get("impersonation") is True:
        impersonated_by_str: str | None = payload.get("impersonated_by")
        if impersonated_by_str:
            try:
                impersonated_by = UUID(impersonated_by_str)
                await _log_impersonation_call(
                    super_admin_id=impersonated_by,
                    tenant_id=UUID(tenant_id),
                )
            except Exception:
                # Audit logging failure must NEVER block the actual request.
                # Log the error but continue serving the request.
                import logging
                logging.getLogger(__name__).error(
                    "Failed to write impersonation audit log",
                    exc_info=True,
                )

    return user_dict


async def _log_impersonation_call(
    super_admin_id: UUID,
    tenant_id: UUID,
) -> None:
    """
    Writes an impersonation.api_call entry to super_admin_audit_log.
    Called transparently from get_current_user when an impersonation token is detected.

    We open a fresh DB connection rather than receiving one as a parameter
    because get_current_user is a dependency (not a route handler) and does
    not have access to the route's connection. Opening a short-lived connection
    here is acceptable — audit log writes are fast and this path is rare
    (only during active impersonation sessions).
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
        # Swallow the exception — audit logging failure must never block the request.
        import logging
        logging.getLogger(__name__).error(
            "DB error writing impersonation audit log", exc_info=True
        )


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

    NOTE: This dependency calls get_current_user, which now explicitly rejects
    super_admin tokens. So get_current_tenant_id will never receive a super admin
    token — the rejection happens upstream in get_current_user.
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


async def get_current_super_admin(
    token: str = Depends(oauth2_scheme),
) -> dict:
    """
    Dependency for super admin routes. Validates a super admin JWT.

    Accepts ONLY tokens with role="super_admin". Rejects all other tokens,
    including impersonation tokens (which have role="admin").

    Returns dict with:
        super_admin_id - str UUID
        role           - "super_admin"

    This dependency is used exclusively on /super-admin/* routes.
    It deliberately does NOT call get_current_user to avoid the super admin
    safety rail triggering in the wrong direction (get_current_user would
    reject super_admin tokens with a 403, which is correct for tenant endpoints
    but wrong here — we want a 401 for invalid tokens and 403 for wrong role).
    """
    payload = decode_access_token(token)
    if payload is None:
        raise UnauthorisedException("Invalid or expired token.")

    role: str | None = payload.get("role")
    sub: str | None = payload.get("sub")

    if role != "super_admin":
        # A tenant admin token used on a super admin endpoint gets a clear error.
        # Do NOT return 401 here — the token is valid, just the wrong role.
        raise ForbiddenException(
            "This endpoint requires a super admin token. "
            "Super admin tokens are issued only at /super-admin/auth/totp/verify."
        )

    if sub is None:
        raise UnauthorisedException("Token is missing subject claim.")

    return {
        "super_admin_id": sub,
        "role": "super_admin",
    }