"""
app/modules/payments/schemas.py
================================
Pydantic schemas for the payments module.
Handles validation of customer inputs and serialization of database payloads.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.security import normalise_phone


class STKPushRequest(BaseModel):
    """
    Request payload from customer to trigger Lipa Na M-Pesa STK push.
    """
    phone: str = Field(
        ...,
        description="Customer phone number (e.g. 0712345678, +254712345678, 254712345678)"
    )
    package_id: UUID = Field(
        ...,
        description="The package ID customer is purchasing."
    )

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """
        Validates and normalises the phone number at the schema layer.
        If invalid, raises a ValueError which FastAPI translates to a 422 Unprocessable Entity.
        """
        try:
            return normalise_phone(v)
        except ValueError as e:
            raise ValueError(str(e))


class PaymentResponse(BaseModel):
    """
    Serialization representation of a payment record.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    package_id: UUID
    amount_kes: Decimal
    status: str
    phone_number: str
    created_at: datetime


class PaymentStatusResponse(BaseModel):
    """
    Response returned when polling a payment status.
    Includes the voucher code if the payment has been confirmed.
    """
    model_config = ConfigDict(from_attributes=True)

    payment_id: UUID
    status: str
    voucher_code: Optional[str] = None
