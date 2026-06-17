"""
app/modules/vouchers/router.py
================================
Router for voucher management — fully tenant-scoped.

CROSS-TENANT ISOLATION (WHY 404 NOT 403):
  When a customer requests GET /vouchers/{voucher_id} with a real UUID
  that belongs to tenant B, the service returns None (because the query
  scopes to the caller's tenant_id and finds nothing). The router raises
  NotFoundException → 404.

  A 403 Forbidden would say "I found this voucher but you can't have it."
  That leaks that the UUID exists somewhere in the system, potentially
  revealing that tenant B has a voucher with that specific ID. A 404
  reveals nothing — the caller cannot distinguish "doesn't exist" from
  "exists in another tenant."

  This is the correct behavior for any multi-tenant resource endpoint.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.database import get_db
from app.dependencies import require_role
from app.core.exceptions import NotFoundException
from app.modules.vouchers.schemas import VoucherResponse
from app.modules.vouchers.service import (
    get_customer_vouchers,
    get_voucher_by_id,
    get_reseller_vouchers,
    get_all_vouchers,
    admin_revoke_voucher,
    admin_retry_voucher,
)

router = APIRouter()


# IMPORTANT: /vouchers/me must come before /vouchers/{voucher_id}
@router.get(
    "/vouchers/me",
    response_model=list[VoucherResponse],
    summary="Get own vouchers (customer only)",
)
async def get_my_vouchers(
    current_user: dict = Depends(require_role("customer")),
):
    async with get_db() as conn:
        vouchers = await get_customer_vouchers(
            conn,
            tenant_id=UUID(current_user["tenant_id"]),
            customer_id=current_user["user_id"],
        )
    return vouchers


@router.get(
    "/vouchers/{voucher_id}",
    response_model=VoucherResponse,
    summary="Get a specific voucher (customer only, own vouchers)",
)
async def get_voucher(
    voucher_id: str,
    current_user: dict = Depends(require_role("customer")),
):
    """
    Returns 404 for:
      - Vouchers that don't exist.
      - Vouchers that exist but belong to a different tenant.
      - Vouchers that belong to the same tenant but a different customer.

    WHY ALL THREE CASES RETURN 404 (not 403):
      See module docstring. Confirming existence but denying access (403)
      leaks information about other tenants' data. 404 reveals nothing.
    """
    async with get_db() as conn:
        voucher = await get_voucher_by_id(
            conn,
            tenant_id=UUID(current_user["tenant_id"]),
            voucher_id=voucher_id,
        )

    if not voucher:
        raise NotFoundException("Voucher", voucher_id)

    # Customer isolation within the tenant
    if str(voucher["customer_id"]) != str(current_user["user_id"]):
        # Also 404 — same reason. A customer calling with another customer's
        # voucher ID within the same tenant should not learn that the voucher exists.
        raise NotFoundException("Voucher", voucher_id)

    return voucher


@router.post(
    "/vouchers/{voucher_id}/revoke",
    summary="Revoke a voucher and remove from MikroTik (admin only)",
)
async def revoke_voucher(
    voucher_id: str,
    current_user: dict = Depends(require_role("admin")),
):
    async with get_db() as conn:
        result = await admin_revoke_voucher(
            conn,
            tenant_id=UUID(current_user["tenant_id"]),
            voucher_id=voucher_id,
        )
    return {"message": "Voucher revoked successfully", "voucher": result}


@router.post(
    "/vouchers/{voucher_id}/retry",
    summary="Retry provisioning a pending voucher (admin only)",
)
async def retry_voucher(
    voucher_id: str,
    current_user: dict = Depends(require_role("admin")),
):
    async with get_db() as conn:
        result = await admin_retry_voucher(
            conn,
            tenant_id=UUID(current_user["tenant_id"]),
            voucher_id=voucher_id,
        )
    return {"message": "Voucher provisioned successfully", "voucher": result}


@router.get(
    "/reseller/vouchers",
    response_model=list[VoucherResponse],
    summary="List vouchers for reseller's customers",
)
async def list_reseller_vouchers(
    current_user: dict = Depends(require_role("admin", "reseller")),
):
    async with get_db() as conn:
        if current_user["role"] == "admin":
            vouchers = await get_all_vouchers(
                conn,
                tenant_id=UUID(current_user["tenant_id"]),
            )
        else:
            vouchers = await get_reseller_vouchers(
                conn,
                tenant_id=UUID(current_user["tenant_id"]),
                reseller_id=current_user["user_id"],
            )
    return vouchers
