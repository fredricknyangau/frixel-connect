"""
app/modules/payments/router.py
================================
Router for payment processing — fully tenant-scoped.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status, HTTPException

from app.database import get_db
from app.core.rate_limit import RateLimiter
from app.dependencies import require_role
from app.core.exceptions import NotFoundException
from app.modules.payments.schemas import STKPushRequest, PaymentResponse, PaymentStatusResponse
from app.modules.payments.service import (
    initiate_stk_push,
    get_payment_status,
    get_customer_payments,
    get_reseller_payments,
    get_all_payments,
    get_stuck_payments,
)

router = APIRouter()


@router.post(
    "/payments/stk",
    response_model=PaymentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Initiate M-Pesa STK push payment (customer only)",
    dependencies=[Depends(RateLimiter(requests=3, window=60))],
)
async def create_stk_push(
    data: STKPushRequest,
    current_user: dict = Depends(require_role("customer")),
):
    async with get_db() as conn:
        payment = await initiate_stk_push(
            conn,
            tenant_id=UUID(current_user["tenant_id"]),
            customer_id=current_user["user_id"],
            data=data,
        )
    return payment


@router.get(
    "/payments/me",
    response_model=list[PaymentResponse],
    summary="Get own payment history (customer only)",
)
async def get_my_payments(
    current_user: dict = Depends(require_role("customer")),
):
    async with get_db() as conn:
        payments = await get_customer_payments(
            conn,
            tenant_id=UUID(current_user["tenant_id"]),
            customer_id=current_user["user_id"],
        )
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
    async with get_db() as conn:
        status_info = await get_payment_status(
            conn,
            tenant_id=UUID(current_user["tenant_id"]),
            payment_id=payment_id,
            customer_id=current_user["user_id"],
        )
    return status_info


@router.get(
    "/reseller/payments",
    response_model=list[PaymentResponse],
    summary="List payments for reseller's customers",
)
async def list_reseller_payments(
    current_user: dict = Depends(require_role("admin", "reseller")),
):
    async with get_db() as conn:
        if current_user["role"] == "admin":
            payments = await get_all_payments(
                conn,
                tenant_id=UUID(current_user["tenant_id"]),
            )
        else:
            payments = await get_reseller_payments(
                conn,
                tenant_id=UUID(current_user["tenant_id"]),
                reseller_id=current_user["user_id"],
            )
    return payments


@router.get(
    "/admin/payments",
    response_model=list[PaymentResponse],
    summary="List all payments in this tenant (admin only)",
)
async def list_all_payments_admin(
    current_user: dict = Depends(require_role("admin")),
):
    async with get_db() as conn:
        payments = await get_all_payments(
            conn,
            tenant_id=UUID(current_user["tenant_id"]),
        )
    return payments


@router.get(
    "/admin/payments/stuck",
    response_model=list[PaymentResponse],
    summary="List all stuck confirmed payments with no vouchers (admin only)",
)
async def list_stuck_payments(
    current_user: dict = Depends(require_role("admin")),
):
    async with get_db() as conn:
        payments = await get_stuck_payments(
            conn,
            tenant_id=UUID(current_user["tenant_id"]),
        )
    return payments


@router.post(
    "/admin/payments/{payment_id}/retry-provision",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Manually trigger provisioning for a stuck confirmed payment (admin only)",
)
async def retry_provision_payment(
    payment_id: str,
    current_user: dict = Depends(require_role("admin")),
):
    from app.core.redis import get_redis_pool

    tenant_id = UUID(current_user["tenant_id"])
    try:
        payment_uuid = UUID(payment_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid payment UUID: '{payment_id}'",
        )

    async with get_db() as conn:
        # Verify payment exists, belongs to caller's tenant, and is confirmed
        payment = await conn.fetchrow(
            "SELECT id, status FROM payments WHERE id = $1 AND tenant_id = $2",
            payment_uuid,
            tenant_id,
        )
        if not payment:
            raise NotFoundException("Payment", payment_id)

        if payment["status"] != "confirmed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only confirmed payments can be provisioned.",
            )

        # Check if voucher already exists
        voucher_exists = await conn.fetchval(
            "SELECT COUNT(*) FROM vouchers WHERE payment_id = $1",
            payment_uuid,
        )
        if voucher_exists > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Voucher already exists for this payment.",
            )

    # Enqueue to task queue
    redis = get_redis_pool()
    await redis.enqueue_job("generate_voucher_task", payment_id)

    return {"message": "Provisioning task enqueued."}
