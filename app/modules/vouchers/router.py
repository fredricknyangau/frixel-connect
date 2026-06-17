"""
app/modules/vouchers/router.py
================================
Stub router for the vouchers module — role guards wired, handlers not yet
implemented (Phase 7 Step G completes them).

Mounted at /api/v1 in main.py. Full paths defined here.

Route-to-role mapping (full paths):
  GET  /api/v1/vouchers/me           → customer only
  GET  /api/v1/vouchers/{id}         → customer only (own vouchers only)
  POST /api/v1/vouchers/{id}/revoke  → admin only
  GET  /api/v1/reseller/vouchers     → admin, reseller

Path ordering matters in FastAPI:
  /vouchers/me and /vouchers/{voucher_id} could conflict if FastAPI tries
  to match "me" as a voucher_id. FastAPI resolves this by matching routes
  in the ORDER they are registered in the router. "/vouchers/me" must be
  registered BEFORE "/vouchers/{voucher_id}" — which is what we do here.
"""

from fastapi import APIRouter, Depends

from app.dependencies import require_role

router = APIRouter()


# IMPORTANT: /vouchers/me must come before /vouchers/{voucher_id}
# FastAPI matches routes top-to-bottom. If {voucher_id} is first,
# a request to /vouchers/me will match it with voucher_id="me".
@router.get(
    "/vouchers/me",
    summary="Get own vouchers (customer only)",
)
async def get_my_vouchers(
    _user: dict = Depends(require_role("customer")),
):
    return {"message": "not yet implemented — Phase 7"}


@router.get(
    "/vouchers/{voucher_id}",
    summary="Get a specific voucher (customer only, own vouchers)",
)
async def get_voucher(
    voucher_id: str,
    _user: dict = Depends(require_role("customer")),
):
    return {"message": "not yet implemented — Phase 7"}


@router.post(
    "/vouchers/{voucher_id}/revoke",
    summary="Revoke a voucher and remove from MikroTik (admin only)",
)
async def revoke_voucher(
    voucher_id: str,
    _user: dict = Depends(require_role("admin")),
):
    return {"message": "not yet implemented — Phase 7"}


@router.get(
    "/reseller/vouchers",
    summary="List vouchers for reseller's customers",
)
async def list_reseller_vouchers(
    _user: dict = Depends(require_role("admin", "reseller")),
):
    return {"message": "not yet implemented — Phase 7"}
