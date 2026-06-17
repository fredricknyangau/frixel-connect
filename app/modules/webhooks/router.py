"""
app/modules/webhooks/router.py
================================
Router for public webhook callbacks.
No authentication is required since Safaricom's servers do not possess a user JWT.
"""

from fastapi import APIRouter, BackgroundTasks, status

from app.database import get_db
from app.modules.webhooks.service import process_daraja_webhook

router = APIRouter()


@router.post(
    "/daraja",
    status_code=status.HTTP_200_OK,
    summary="Daraja M-Pesa callback — NO authentication required",
)
async def daraja_webhook(
    body: dict,
    background_tasks: BackgroundTasks,
):
    """
    Public callback receiver endpoint invoked by Safaricom Daraja STK Push processing servers.
    Accepts raw JSON request, registers the voucher generation background tasks,
    and returns a success response.
    """
    async with get_db() as conn:
        response = await process_daraja_webhook(conn, body, background_tasks)
    return response
