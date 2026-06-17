"""
app/modules/vouchers/schemas.py
================================
Pydantic schemas for the vouchers module.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VoucherResponse(BaseModel):
    """
    Response schema representing a generated WiFi voucher.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    status: str
    expires_at: Optional[datetime] = None
    package_name: str = Field(..., description="Name of the package this voucher is for")
    customer_id: UUID
    activated_at: Optional[datetime] = None
    created_at: datetime


class ResellerVoucherGenerateRequest(BaseModel):
    """
    Request schema for a reseller generating a voucher directly.
    """
    customer_id: UUID
    package_id: UUID

