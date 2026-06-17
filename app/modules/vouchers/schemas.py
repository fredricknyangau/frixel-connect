"""
app/modules/vouchers/schemas.py
================================
Pydantic schemas for the vouchers module.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class VoucherResponse(BaseModel):
    """
    Response schema representing a generated WiFi voucher.
    """
    id: UUID
    code: str
    status: str
    expires_at: Optional[datetime] = None
    package_name: str = Field(..., description="Name of the package this voucher is for")
    customer_id: UUID
    activated_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
