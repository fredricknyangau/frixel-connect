"""
app/modules/vouchers/router.py
================================
Router exposing HTTP endpoints for managing hotspot vouchers.
"""

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
)

router = APIRouter()


# IMPORTANT: /vouchers/me must come before /vouchers/{voucher_id}
# FastAPI matches routes top-to-bottom. If {voucher_id} is first,
# a request to /vouchers/me will match it with voucher_id="me".
@router.get(
    "/vouchers/me",
    response_model=list[VoucherResponse],
    summary="Get own vouchers (customer only)",
)
async def get_my_vouchers(
    current_user: dict = Depends(require_role("customer")),
):
    """
    Returns the list of vouchers purchased by the authenticated customer.
    """
    async with get_db() as conn:
        vouchers = await get_customer_vouchers(conn, current_user["user_id"])
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
    Returns details of a specific voucher.
    Enforces customer isolation (customers can only look up vouchers they own).
    """
    async with get_db() as conn:
        voucher = await get_voucher_by_id(conn, voucher_id)

    # 404 if the voucher does not exist
    if not voucher:
        raise NotFoundException("Voucher", voucher_id)

    # Prevent customer from accessing another customer's voucher
    if str(voucher["customer_id"]) != str(current_user["user_id"]):
        raise NotFoundException("Voucher", voucher_id)

    return voucher


@router.post(
    "/vouchers/{voucher_id}/revoke",
    summary="Revoke a voucher and remove from MikroTik (admin only)",
)
async def revoke_voucher(
    voucher_id: str,
    _user: dict = Depends(require_role("admin")),
):
    """
    Revokes an active voucher.
    Updates the voucher state to 'revoked' in PostgreSQL and deletes the user
    from the RouterOS Hotspot instance synchronously. Restricted to admins.
    """
    async with get_db() as conn:
        result = await admin_revoke_voucher(conn, voucher_id)
    return {"message": "Voucher revoked successfully", "voucher": result}


@router.get(
    "/reseller/vouchers",
    response_model=list[VoucherResponse],
    summary="List vouchers for reseller's customers",
)
async def list_reseller_vouchers(
    current_user: dict = Depends(require_role("admin", "reseller")),
):
    """
    Returns voucher records for customers belonging to the reseller.
    Admins are permitted to call this, in which case they see all vouchers.
    """
    async with get_db() as conn:
        if current_user["role"] == "admin":
            vouchers = await get_all_vouchers(conn)
        else:
            vouchers = await get_reseller_vouchers(conn, current_user["user_id"])
    return vouchers
