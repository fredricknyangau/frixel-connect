"""
app/modules/webhooks/router.py
================================
Router for public webhook callbacks.
No authentication is required since Safaricom's servers do not possess a user JWT.
"""

from fastapi import APIRouter, status

from app.database import get_db
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
    async with get_db() as conn:
        response = await process_daraja_webhook(conn, body)
    return response


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
    async with get_db() as conn:
        response = await process_daraja_c2b_webhook(conn, body)
    return response
