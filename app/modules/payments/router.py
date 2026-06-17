"""
app/modules/payments/router.py
================================
Router exposing HTTP endpoints for payment processing and billing records.
Wired with RBAC role guards to secure access.
"""

from fastapi import APIRouter, Depends, status

from app.database import get_db
from app.dependencies import require_role
from app.modules.payments.schemas import STKPushRequest, PaymentResponse, PaymentStatusResponse
from app.modules.payments.service import (
    initiate_stk_push,
    get_payment_status,
    get_customer_payments,
    get_reseller_payments,
    get_all_payments,
)

router = APIRouter()


@router.post(
    "/payments/stk",
    response_model=PaymentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Initiate M-Pesa STK push payment (customer only)",
)
async def create_stk_push(
    data: STKPushRequest,
    current_user: dict = Depends(require_role("customer")),
):
    """
    Initiates an STK Push payment to Safaricom Daraja.
    Returns 202 Accepted, indicating the payment request is queued and waiting for
    the customer to input their M-Pesa PIN and for Daraja to invoke our webhook.
    """
    async with get_db() as conn:
        payment = await initiate_stk_push(conn, current_user["user_id"], data)
    return payment


@router.get(
    "/payments/me",
    response_model=list[PaymentResponse],
    summary="Get own payment history (customer only)",
)
async def get_my_payments(
    current_user: dict = Depends(require_role("customer")),
):
    """
    Returns the billing history of the authenticated customer.
    """
    async with get_db() as conn:
        payments = await get_customer_payments(conn, current_user["user_id"])
    return payments


@router.get(
    "/payments/{payment_id}/status",
    response_model=PaymentStatusResponse,
    summary="Poll payment status (customer only)",
)
async def check_payment_status(
    payment_id: str,
    current_user: dict = Depends(require_role("customer")),
):
    """
    Endpoint for polling the state of a payment.
    Customers poll this endpoint every ~3 seconds until status is 'confirmed'
    and a 'voucher_code' is populated.
    """
    async with get_db() as conn:
        status_info = await get_payment_status(conn, payment_id, current_user["user_id"])
    return status_info


@router.get(
    "/reseller/payments",
    response_model=list[PaymentResponse],
    summary="List payments for reseller's customers",
)
async def list_reseller_payments(
    current_user: dict = Depends(require_role("admin", "reseller")),
):
    """
    Returns payment records for customers registered under the reseller.
    Admins are permitted to call this, in which case they see all payments.
    """
    async with get_db() as conn:
        if current_user["role"] == "admin":
            payments = await get_all_payments(conn)
        else:
            payments = await get_reseller_payments(conn, current_user["user_id"])
    return payments


@router.get(
    "/admin/payments",
    response_model=list[PaymentResponse],
    summary="List all payments (admin only)",
)
async def list_all_payments_admin(
    current_user: dict = Depends(require_role("admin")),
):
    """
    Returns all payments in the system. Restricted to administrators.
    """
    async with get_db() as conn:
        payments = await get_all_payments(conn)
    return payments
