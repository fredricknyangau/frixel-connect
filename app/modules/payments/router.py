"""
app/modules/payments/router.py
================================
Stub router for the payments module — role guards wired, handlers not yet
implemented (Phase 7 completes them).

This router is mounted at /api/v1 (no sub-prefix) in main.py so that
routes spanning /payments/... AND /reseller/... AND /admin/... all resolve
at the correct top-level paths. Each route below defines its full path
relative to /api/v1.

Route-to-role mapping:
  POST /payments/stk          → customer only (initiates M-Pesa payment)
  GET  /payments/me           → customer only (own payment history)
  GET  /payments/{id}/status  → customer only (poll for confirmation)
  GET  /reseller/payments     → admin, reseller (see their customers' payments)
  GET  /admin/payments        → admin only (see all payments)

Why is STK push customer-only?
Resellers and admins don't buy packages for themselves — they manage the
system. A reseller creating a payment on behalf of a customer is a v2 feature
(agent-initiated STK, different Daraja API flow). For v1, the customer
initiates their own payment directly.
"""

from fastapi import APIRouter, Depends

from app.dependencies import require_role

router = APIRouter()


@router.post(
    "/payments/stk",
    status_code=202,
    summary="Initiate M-Pesa STK push payment (customer only)",
)
async def initiate_stk_push(
    _user: dict = Depends(require_role("customer")),
):
    # 202 Accepted: the request was received and we're working on it,
    # but the work (waiting for M-Pesa callback) isn't done yet.
    return {"message": "not yet implemented — Phase 7"}


@router.get(
    "/payments/me",
    summary="Get own payment history (customer only)",
)
async def get_my_payments(
    _user: dict = Depends(require_role("customer")),
):
    return {"message": "not yet implemented — Phase 7"}


@router.get(
    "/payments/{payment_id}/status",
    summary="Poll payment status (customer only)",
)
async def get_payment_status(
    payment_id: str,
    _user: dict = Depends(require_role("customer")),
):
    return {"message": "not yet implemented — Phase 7"}


@router.get(
    "/reseller/payments",
    summary="List payments for reseller's customers",
)
async def list_reseller_payments(
    _user: dict = Depends(require_role("admin", "reseller")),
):
    return {"message": "not yet implemented — Phase 7"}


@router.get(
    "/admin/payments",
    summary="List all payments (admin only)",
)
async def list_all_payments(
    _user: dict = Depends(require_role("admin")),
):
    return {"message": "not yet implemented — Phase 7"}
