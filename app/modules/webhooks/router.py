"""
app/modules/webhooks/router.py
================================
Router for public webhook callbacks.
No authentication is required since Safaricom's servers do not possess a user JWT.
"""

from fastapi import APIRouter, status

from app.database import get_db
from app.core.metrics import webhook_events_total
from app.modules.webhooks.service import process_daraja_webhook, process_daraja_c2b_webhook

router = APIRouter()


@router.post(
    "/daraja",
    status_code=status.HTTP_200_OK,
    summary="Daraja M-Pesa callback — NO authentication required",
)
async def daraja_webhook(
    body: dict,
):
    """
    Public callback receiver endpoint invoked by Safaricom Daraja STK Push processing servers.
    Accepts raw JSON request, enqueues the voucher generation task to the arq queue,
    and returns a success response.
    """
    webhook_events_total.labels(provider="daraja_stk", status="received").inc()
    try:
        async with get_db() as conn:
            response = await process_daraja_webhook(conn, body)
        webhook_events_total.labels(provider="daraja_stk", status="success").inc()
        return response
    except Exception as e:
        webhook_events_total.labels(provider="daraja_stk", status="error").inc()
        raise e


@router.post(
    "/daraja/c2b",
    status_code=status.HTTP_200_OK,
    summary="Daraja M-Pesa C2B callback (Validation & Confirmation) — NO authentication required",
)
async def daraja_c2b_webhook(
    body: dict,
):
    """
    Public C2B callback receiver endpoint invoked by Safaricom Daraja.
    Handles transaction validation and confirmation.
    """
    webhook_events_total.labels(provider="daraja_c2b", status="received").inc()
    try:
        async with get_db() as conn:
            response = await process_daraja_c2b_webhook(conn, body)
        webhook_events_total.labels(provider="daraja_c2b", status="success").inc()
        return response
    except Exception as e:
        webhook_events_total.labels(provider="daraja_c2b", status="error").inc()
        raise e
