"""
app/modules/wallets/router.py
==============================
Router exposing reseller wallet operations.
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.database import get_db
from app.dependencies import require_role
from app.config import settings
from app.modules.wallets.schemas import WalletResponse
from app.modules.wallets.service import get_wallet_balance, get_wallet_transactions

router = APIRouter()


@router.get(
    "/reseller/wallet",
    response_model=WalletResponse,
    summary="Get current balance, paybill details and last 20 transactions (reseller only)",
)
async def get_my_wallet(
    current_user: dict = Depends(require_role("reseller")),
):
    reseller_id = UUID(current_user["user_id"])
    async with get_db() as conn:
        balance = await get_wallet_balance(conn, reseller_id)
        transactions = await get_wallet_transactions(conn, reseller_id, limit=20)
        wallet_ref = await conn.fetchval(
            "SELECT wallet_reference FROM users WHERE id = $1", reseller_id
        )
    return {
        "balance": balance,
        "transactions": transactions,
        "paybill_number": settings.DARAJA_SHORTCODE,
        "wallet_reference": wallet_ref or "WS00000",
    }
