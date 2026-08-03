"""
app/modules/super_admin/router.py
===================================
HTTP route handlers for the super admin portal.

ROUTING DESIGN:
  All routes are under /super-admin/* (no /api/v1 prefix).
  This makes the super admin portal completely separate from the tenant API
  at the URL level-you can't stumble onto it by exploring the tenant API docs.

  The routes are registered in main.py with prefix="" so the /super-admin/
  path prefix comes from the router itself (see below), not from include_router().
  This is intentional: it makes the prefix explicit in this file rather than
  invisible in main.py.

AUTH FLOW:
  Public:           POST /super-admin/auth/login
  Pre-auth only:    POST /super-admin/auth/totp/setup
                    POST /super-admin/auth/totp/verify
  Super admin JWT:  Everything else (uses get_current_super_admin dependency)

RATE LIMITING:
  Login endpoint: 5 attempts per IP per 15 minutes.
  Other endpoints inherit FastAPI's standard dependency error handling.

IP EXTRACTION:
  All auth endpoints extract the client IP and pass it to the service layer
  for audit logging and pre-auth token storage. Uses X-Real-IP if set by
  Nginx (production), falls back to request.client.host (direct connections).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from app.core.rate_limit import RateLimiter
from app.database import get_db
from app.dependencies import get_current_super_admin
from app.modules.super_admin import service
from app.modules.super_admin.schemas import (
    CreateImpersonationRequest,
    CreateSuperAdminRequest,
    SuperAdminLoginRequest,
    SuperAdminPreAuthResponse,
    SuperAdminProfile,
    SuperAdminTOTPSetupRequest,
    SuperAdminTOTPSetupResponse,
    SuperAdminTOTPVerifyRequest,
    SuperAdminTokenResponse,
    TenantSuspendRequest,
)

router = APIRouter()


def _get_client_ip(request: Request) -> str:
    """
    Extracts the real client IP address for audit logging.

    In production, Nginx sets X-Real-IP to the original client IP before
    forwarding. Without this, request.client.host would be Nginx's own IP.
    Falls back to request.client.host for direct connections (dev environment).
    """
    x_real_ip = request.headers.get("X-Real-IP")
    if x_real_ip:
        return x_real_ip
    return request.client.host if request.client else "0.0.0.0"


# ── Authentication ─────────────────────────────────────────────────────────────

@router.post(
    "/super-admin/auth/login",
    response_model=SuperAdminPreAuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Super admin login-step 1 (email + password)",
    description=(
        "Validates email and password. Returns a short-lived pre-auth token (5 min). "
        "This is NOT a full access token-it cannot call any protected endpoint. "
        "Present it to /super-admin/auth/totp/setup or /super-admin/auth/totp/verify. "
        "Rate limited to 5 attempts per IP per 15 minutes."
    ),
    # Rate limiter: 5 attempts per IP per 15 minutes (900 seconds).
    # This is the primary brute-force protection for the super admin login.
    # The rate limit is per-IP because we can't use per-account limiting here
    # without revealing whether an email address exists.
    dependencies=[Depends(RateLimiter(requests=5, window=900))],
)
async def super_admin_login(
    data: SuperAdminLoginRequest,
    request: Request,
) -> SuperAdminPreAuthResponse:
    ip = _get_client_ip(request)
    async with get_db() as conn:
        result = await service.authenticate_password(
            conn,
            email=str(data.email),
            password=data.password,
            ip_address=ip,
        )
    return SuperAdminPreAuthResponse(
        pre_auth_token=result["pre_auth_token"],
        totp_required=True,
        totp_setup_required=result["totp_setup_required"],
    )


@router.post(
    "/super-admin/auth/totp/setup",
    response_model=SuperAdminTOTPSetupResponse,
    status_code=status.HTTP_200_OK,
    summary="Super admin TOTP setup-generate QR code (first login only)",
    description=(
        "Generates a TOTP secret and returns a QR code for the super admin to scan "
        "with Google Authenticator or Authy. Only available when totp_verified_at IS NULL "
        "(first login or after a forced TOTP reset). Returns 409 if TOTP is already set up."
    ),
)
async def super_admin_totp_setup(
    data: SuperAdminTOTPSetupRequest,
) -> SuperAdminTOTPSetupResponse:
    async with get_db() as conn:
        result = await service.setup_totp(conn, pre_auth_token=data.pre_auth_token)
    return SuperAdminTOTPSetupResponse(
        qr_code_base64=result["qr_code_base64"],
        secret_preview=result["secret_preview"],
    )


@router.post(
    "/super-admin/auth/totp/verify",
    response_model=SuperAdminTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Super admin TOTP verify-step 2 (TOTP code → full JWT)",
    description=(
        "Validates the pre-auth token and the 6-digit TOTP code from the authenticator app. "
        "Returns a full access token (15-minute expiry). "
        "Refresh tokens are NOT issued-re-authentication is required after expiry. "
        "The pre-auth token is consumed (single-use) on success."
    ),
)
async def super_admin_totp_verify(
    data: SuperAdminTOTPVerifyRequest,
    request: Request,
) -> SuperAdminTokenResponse:
    ip = _get_client_ip(request)
    async with get_db() as conn:
        return await service.verify_totp(
            conn,
            pre_auth_token=data.pre_auth_token,
            totp_code=data.totp_code,
            ip_address=ip,
        )


@router.get(
    "/super-admin/auth/me",
    response_model=SuperAdminProfile,
    status_code=status.HTTP_200_OK,
    summary="Super admin profile",
    description="Returns the authenticated super admin's own profile data.",
)
async def get_me(
    current_sa: dict = Depends(get_current_super_admin),
) -> SuperAdminProfile:
    async with get_db() as conn:
        data = await service.get_super_admin_profile(
            conn,
            super_admin_id=UUID(current_sa["super_admin_id"]),
        )
    return SuperAdminProfile(**data)


# ── Tenant Management ──────────────────────────────────────────────────────────

@router.get(
    "/super-admin/tenants",
    status_code=status.HTTP_200_OK,
    summary="List all tenants (super admin)",
    description=(
        "Returns all ISP tenants with pagination, optional status/tier filters, "
        "and a search parameter (business_name or owner_email). "
        "Every call is audit-logged."
    ),
)
async def list_tenants(
    request: Request,
    page: int = 1,
    limit: int = 20,
    status_filter: str | None = None,
    tier: str | None = None,
    search: str | None = None,
    current_sa: dict = Depends(get_current_super_admin),
) -> dict:
    async with get_db() as conn:
        return await service.get_all_tenants(
            conn,
            super_admin_id=UUID(current_sa["super_admin_id"]),
            page=page,
            limit=limit,
            status_filter=status_filter,
            tier_filter=tier,
            search=search,
        )


@router.get(
    "/super-admin/tenants/{tenant_id}",
    status_code=status.HTTP_200_OK,
    summary="Get full tenant detail (super admin)",
    description=(
        "Returns complete tenant info plus aggregate stats: "
        "total revenue, customer count, active routers, active vouchers, last payment date."
    ),
)
async def get_tenant(
    tenant_id: UUID,
    current_sa: dict = Depends(get_current_super_admin),
) -> dict:
    async with get_db() as conn:
        return await service.get_tenant_detail(
            conn,
            super_admin_id=UUID(current_sa["super_admin_id"]),
            tenant_id=tenant_id,
        )


@router.post(
    "/super-admin/tenants/{tenant_id}/suspend",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Suspend a tenant (super admin)",
    description=(
        "Sets tenant status to 'suspended'. All login attempts by users under this "
        "tenant will return 403 immediately after. A mandatory reason is required "
        "and stored in the audit log."
    ),
)
async def suspend_tenant(
    tenant_id: UUID,
    data: TenantSuspendRequest,
    current_sa: dict = Depends(get_current_super_admin),
) -> None:
    async with get_db() as conn:
        await service.suspend_tenant(
            conn,
            super_admin_id=UUID(current_sa["super_admin_id"]),
            tenant_id=tenant_id,
            reason=data.reason,
        )


@router.post(
    "/super-admin/tenants/{tenant_id}/reactivate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reactivate a suspended tenant (super admin)",
    description="Sets tenant status back to 'active'. Users can log in again immediately.",
)
async def reactivate_tenant(
    tenant_id: UUID,
    current_sa: dict = Depends(get_current_super_admin),
) -> None:
    async with get_db() as conn:
        await service.reactivate_tenant(
            conn,
            super_admin_id=UUID(current_sa["super_admin_id"]),
            tenant_id=tenant_id,
        )


@router.post(
    "/super-admin/tenants/{tenant_id}/impersonate",
    status_code=status.HTTP_200_OK,
    summary="Generate an impersonation token for a tenant (super admin)",
    description=(
        "Issues a time-limited admin-scoped JWT for the specified tenant. "
        "The frontend uses this token to open a 'view as tenant' session. "
        "Every API call made with this token is logged against the super admin's ID. "
        "The token cannot be used on /super-admin/ endpoints."
    ),
)
async def impersonate_tenant(
    tenant_id: UUID,
    data: CreateImpersonationRequest,
    current_sa: dict = Depends(get_current_super_admin),
) -> dict:
    async with get_db() as conn:
        return await service.create_impersonation_token(
            conn,
            super_admin_id=UUID(current_sa["super_admin_id"]),
            tenant_id=tenant_id,
            duration_minutes=data.duration_minutes,
        )


@router.post(
    "/super-admin/tenants/{tenant_id}/billing/trigger",
    status_code=status.HTTP_200_OK,
    summary="Manually trigger platform billing STK push for a tenant (super admin)",
    description=(
        "Sends an M-Pesa STK push to the tenant owner's phone for their monthly "
        "Frixel Connect platform fee. Uses the same Daraja integration as the automated "
        "billing job. Returns the platform_payments row."
    ),
)
async def trigger_billing(
    tenant_id: UUID,
    current_sa: dict = Depends(get_current_super_admin),
) -> dict:
    async with get_db() as conn:
        return await service.trigger_tenant_billing(
            conn,
            super_admin_id=UUID(current_sa["super_admin_id"]),
            tenant_id=tenant_id,
        )


# ── Platform Statistics ────────────────────────────────────────────────────────

@router.get(
    "/super-admin/stats",
    status_code=status.HTTP_200_OK,
    summary="Platform-wide statistics (super admin dashboard)",
    description=(
        "Returns system-wide aggregates: total tenants, revenue today/this-month, "
        "active sessions, active vouchers, and tenant distribution by tier."
    ),
)
async def platform_stats(
    current_sa: dict = Depends(get_current_super_admin),
) -> dict:
    async with get_db() as conn:
        return await service.get_platform_stats(
            conn,
            super_admin_id=UUID(current_sa["super_admin_id"]),
        )


# ── Audit Log ─────────────────────────────────────────────────────────────────

@router.get(
    "/super-admin/audit-log",
    status_code=status.HTTP_200_OK,
    summary="Super admin audit log",
    description=(
        "Returns paginated super_admin_audit_log entries, newest first. "
        "Use the ?action= filter to narrow to specific event types "
        "(e.g. ?action=tenant.suspend, ?action=impersonation)."
    ),
)
async def audit_log(
    page: int = 1,
    limit: int = 50,
    action: str | None = None,
    current_sa: dict = Depends(get_current_super_admin),
) -> dict:
    async with get_db() as conn:
        return await service.get_audit_log(
            conn,
            super_admin_id=UUID(current_sa["super_admin_id"]),
            page=page,
            limit=limit,
            action_filter=action,
        )


# ── Super Admin Account Management ─────────────────────────────────────────────

@router.post(
    "/super-admin/accounts",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new super admin account",
    description=(
        "Only an authenticated super admin can create another super admin account. "
        "The new account starts without TOTP configured-they must complete TOTP "
        "setup on their first login. The creation is audit-logged."
    ),
)
async def create_account(
    data: CreateSuperAdminRequest,
    current_sa: dict = Depends(get_current_super_admin),
) -> dict:
    async with get_db() as conn:
        return await service.create_super_admin(
            conn,
            actor_super_admin_id=UUID(current_sa["super_admin_id"]),
            email=str(data.email),
            full_name=data.full_name,
            password=data.password,
        )


@router.get(
    "/super-admin/accounts",
    response_model=list[SuperAdminProfile],
    status_code=status.HTTP_200_OK,
    summary="List all super admin accounts",
    description="Returns all super admin accounts. Only callable by an authenticated super admin.",
)
async def list_super_admins(
    current_sa: dict = Depends(get_current_super_admin),
) -> list[dict]:
    async with get_db() as conn:
        return await service.get_all_super_admins(
            conn,
            super_admin_id=UUID(current_sa["super_admin_id"]),
        )
