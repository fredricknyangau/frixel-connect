"""
app/modules/hotspot/router.py
================================
Public HTTP endpoints for the hotspot captive portal.
These endpoints are intentionally unauthenticated to allow guests
to browse packages and initiate payments.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from app.database import get_db
from app.core.rate_limit import RateLimiter, get_client_ip
from app.modules.packages.schemas import PackageResponse
from app.modules.packages.service import get_all_packages
from app.modules.payments.schemas import PaymentResponse, PaymentStatusResponse
from app.modules.hotspot.schemas import PortalSTKPushRequest, PortalFreeTrialRequest, PortalFreeTrialResponse
from app.modules.hotspot import service as hotspot_service


router = APIRouter()

hotspot_stk_rate_limiter = RateLimiter(requests=3, window=60, endpoint="hotspot.payments.stk")
hotspot_trial_rate_limiter = RateLimiter(requests=2, window=60, endpoint="hotspot.trial")


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
)
async def create_hotspot_stk_push(request: Request, data: PortalSTKPushRequest):
    """
    Public STK push endpoint for the captive portal flow.
    No JWT required — rate limit scoped by tenant_id from request body.
    """
    await hotspot_stk_rate_limiter.check(
        "hotspot.payments.stk",
        str(data.tenant_id),
        get_client_ip(request),
    )
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


@router.post(
    "/trial",
    response_model=PortalFreeTrialResponse,
    summary="Request a 10-minute free trial voucher (public)",
)
async def request_free_trial(request: Request, data: PortalFreeTrialRequest):
    """
    Public rate-limited free trial activation.
    Provisions a 10-minute trial voucher if user hasn't claimed one in 24 hours.
    """
    await hotspot_trial_rate_limiter.check(
        "hotspot.trial",
        str(data.tenant_id),
        get_client_ip(request),
    )
    async with get_db() as conn:
        voucher_code = await hotspot_service.provision_free_trial(conn, data)
    return {"voucher_code": voucher_code}


@router.get(
    "/login.html",
    summary="Get login redirect HTML for a specific tenant (public)",
)
async def get_login_html(tenant_id: UUID, frontend_url: str):
    """
    Returns the captive portal redirect HTML content.
    The router fetches this file during provisioning to use as its hotspot login page.
    """
    from fastapi.responses import HTMLResponse
    html_content = (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head><title>Redirecting...</title></head>\n"
        "<body>\n"
        "<script>\n"
        f'var params = "?tenant_id={tenant_id}" +\n'
        '             "&mac=$(mac-esc)" +\n'
        '             "&ip=$(ip)" +\n'
        '             "&link-login=$(link-login-esc)" +\n'
        '             "&link-orig=$(link-orig-esc)";\n'
        f'window.location.replace("{frontend_url}/hotspot/login" + params);\n'
        "</script>\n"
        "<noscript>\n"
        f'<meta http-equiv="refresh" content="0;url={frontend_url}/hotspot/login?tenant_id={tenant_id}&mac=$(mac-esc)&ip=$(ip)&link-login=$(link-login-esc)&link-orig=$(link-orig-esc)">\n'
        "</noscript>\n"
        "</body>\n"
        "</html>"
    )
    return HTMLResponse(content=html_content)


