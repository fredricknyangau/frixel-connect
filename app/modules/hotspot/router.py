"""
app/modules/hotspot/router.py
================================
Public HTTP endpoints for the hotspot captive portal.
These endpoints are intentionally unauthenticated to allow guests
to browse packages and initiate payments.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.database import get_db
from app.core.rate_limit import RateLimiter
from app.modules.packages.schemas import PackageResponse
from app.modules.packages.service import get_all_packages
from app.modules.payments.schemas import PaymentResponse, PaymentStatusResponse
from app.modules.hotspot.schemas import PortalSTKPushRequest
from app.modules.hotspot import service as hotspot_service

router = APIRouter()


@router.get(
    "/packages",
    response_model=list[PackageResponse],
    summary="List active packages for a tenant (public)",
)
async def list_hotspot_packages(tenant_id: UUID) -> list[PackageResponse]:
    """
    Public endpoint to fetch packages for the captive portal.
    tenant_id is passed as a query parameter because the user is unauthenticated.
    """
    async with get_db() as conn:
        packages = await get_all_packages(conn, tenant_id=tenant_id)
    return packages


@router.post(
    "/payments/stk",
    response_model=PaymentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Initiate M-Pesa STK push payment (public)",
    dependencies=[Depends(RateLimiter(requests=3, window=60))],
)
async def create_hotspot_stk_push(data: PortalSTKPushRequest):
    """
    Public STK push endpoint for the captive portal flow.
    No JWT required.
    """
    async with get_db() as conn:
        payment = await hotspot_service.initiate_hotspot_payment(conn, data)
    return payment


@router.get(
    "/payments/{payment_id}/status",
    response_model=PaymentStatusResponse,
    summary="Poll payment status (public)",
)
async def check_hotspot_payment_status(payment_id: str):
    """
    Public payment status polling endpoint.
    Returns status and voucher_code once confirmed.
    """
    async with get_db() as conn:
        status_info = await hotspot_service.get_hotspot_payment_status(conn, payment_id)
    return status_info
