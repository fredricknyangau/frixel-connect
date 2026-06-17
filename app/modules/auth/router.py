"""
app/modules/auth/router.py
==========================
HTTP endpoints for authentication.

MULTI-TENANCY CHANGE (Phase 1):
  - register: caller must be an authenticated admin; their tenant_id from the
    JWT is injected into RegisterRequest before calling the service. This
    prevents self-registration of arbitrary users into arbitrary tenants.
  - login: no change to the request body — email+password still the inputs.
    The response now includes tenant_id.
"""

from fastapi import APIRouter, Depends, status

from app.database import get_db
from app.core.security import create_access_token
from app.dependencies import require_role
from app.modules.auth.schemas import RegisterRequest, LoginRequest, TokenResponse
from app.modules.auth.service import register_user, authenticate_user

router = APIRouter()


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user within a tenant (admin only)",
)
async def register(
    data: RegisterRequest,
    current_user: dict = Depends(require_role("admin")),
) -> TokenResponse:
    """
    Creates a new user account within the authenticated admin's tenant.

    WHY admin-only?
    In a multi-tenant SaaS, self-registration of admin/reseller/customer users
    is done through the admin portal, not an open endpoint. An ISP admin logs
    into their portal and creates reseller and customer accounts. The public
    tenant signup (POST /tenants/register) already creates the first admin.
    Open /auth/register would let anyone create users in any tenant if they
    knew the URL.

    The tenant_id is taken from the admin's JWT — the caller cannot inject
    a different tenant_id via the request body.
    """
    # Inject tenant_id from the admin's token before passing to the service.
    # data is a Pydantic model; we create a modified copy.
    from uuid import UUID
    data_with_tenant = data.model_copy(
        update={"tenant_id": UUID(current_user["tenant_id"])}
    )

    async with get_db() as conn:
        user = await register_user(conn, data_with_tenant)

    token = create_access_token(
        user_id=str(user["id"]),
        role=user["role"],
        tenant_id=str(user["tenant_id"]),
        reseller_id=str(user["reseller_id"]) if user["reseller_id"] else None,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user["role"],
        user_id=user["id"],
        tenant_id=user["tenant_id"],
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Login and obtain an access token",
)
async def login(data: LoginRequest) -> TokenResponse:
    """
    Validates credentials and returns an access token.

    The login endpoint is public (no JWT required). It finds the user by email,
    verifies the password, checks the tenant is active, and issues a token with
    tenant_id embedded so all subsequent requests are automatically scoped.

    If the tenant is suspended, the response is 403 "account suspended" — not
    a generic 401 — so the ISP owner knows exactly why they can't log in.
    """
    async with get_db() as conn:
        user = await authenticate_user(conn, data.email, data.password)

    token = create_access_token(
        user_id=str(user["id"]),
        role=user["role"],
        tenant_id=str(user["tenant_id"]),
        reseller_id=str(user["reseller_id"]) if user["reseller_id"] else None,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user["role"],
        user_id=user["id"],
        tenant_id=user["tenant_id"],
    )
