"""
app/modules/tenants/router.py
================================
HTTP endpoints for tenant management.

  POST /tenants/register — PUBLIC. ISP owner signs up for ZealSync.
  GET  /tenants/me       — Admin only. Returns own tenant details + stats.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.database import get_db
from app.core.security import create_access_token
from app.dependencies import require_role
from app.modules.tenants.schemas import (
    TenantRegisterRequest,
    TenantResponse,
    TenantRegisterResponse,
)
from app.modules.tenants.service import register_tenant, get_tenant_by_id

router = APIRouter()


@router.post(
    "/register",
    response_model=TenantRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new ISP tenant (public signup)",
)
async def register(data: TenantRegisterRequest) -> TenantRegisterResponse:
    """
    Public ISP owner signup. Creates the tenant + its first admin user in one
    atomic transaction. Returns the admin access token so the ISP owner is
    immediately logged in.

    This is the equivalent of clicking "Sign Up" on any SaaS platform.
    No existing auth required — this is how tenants are created.
    """
    async with get_db() as conn:
        result = await register_tenant(conn, data)

    tenant = result["tenant"]
    user = result["user"]

    # Issue the admin token immediately.
    # The token embeds tenant_id so every subsequent request is tenant-scoped.
    token = create_access_token(
        user_id=str(user["id"]),
        role=user["role"],
        tenant_id=str(tenant["id"]),
        reseller_id=None,  # admin users have no parent reseller
    )

    return TenantRegisterResponse(
        tenant=TenantResponse(**tenant),
        access_token=token,
        token_type="bearer",
        user_id=user["id"],
    )


@router.get(
    "/me",
    response_model=TenantResponse,
    summary="Get own tenant details (admin only)",
)
async def get_my_tenant(
    current_user: dict = Depends(require_role("admin")),
) -> TenantResponse:
    """
    Returns the authenticated admin's tenant record.
    Includes subscription tier, max_customers ceiling, and current status.
    """
    async with get_db() as conn:
        tenant = await get_tenant_by_id(conn, UUID(current_user["tenant_id"]))
    return TenantResponse(**tenant)
