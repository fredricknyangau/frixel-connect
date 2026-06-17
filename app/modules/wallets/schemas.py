"""
app/modules/wallets/schemas.py
===============================
Pydantic schemas for the reseller wallets and transactions ledger.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field


class WalletTransactionResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    reseller_id: UUID
    type: Literal["topup", "debit", "adjustment"]
    amount_kes: Decimal = Field(..., max_digits=10, decimal_places=2)
    balance_after: Decimal = Field(..., max_digits=10, decimal_places=2)
    reference: str
    created_at: datetime

    class Config:
        from_attributes = True


class WalletResponse(BaseModel):
    balance: Decimal = Field(..., max_digits=10, decimal_places=2)
    transactions: list[WalletTransactionResponse]
