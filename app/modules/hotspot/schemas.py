"""
app/modules/hotspot/schemas.py
================================
Pydantic schemas for the public hotspot captive portal flow.
"""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.security import normalise_phone


class PortalSTKPushRequest(BaseModel):
    """
    Request payload from an unauthenticated phone on the captive portal
    to trigger an M-Pesa STK push.
    """
    phone: str = Field(
        ...,
        description="Customer phone number (e.g. 0712345678)"
    )
    package_id: UUID = Field(
        ...,
        description="The package ID customer is purchasing."
    )
    tenant_id: UUID = Field(
        ...,
        description="The tenant ID, passed from the MikroTik redirect URL to the React app."
    )
    mac_address: Optional[str] = Field(
        None,
        description="Client MAC address from MikroTik"
    )
    client_ip: Optional[str] = Field(
        None,
        description="Client IP address from MikroTik"
    )

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        try:
            return normalise_phone(v)
        except ValueError as e:
            raise ValueError(str(e))


class PortalFreeTrialRequest(BaseModel):
    """
    Request payload from an unauthenticated phone on the captive portal
    to request a free trial voucher.
    """
    phone: str = Field(
        ...,
        description="Customer phone number (e.g. 0712345678)"
    )
    tenant_id: UUID = Field(
        ...,
        description="The tenant ID, passed from the MikroTik redirect URL to the React app."
    )
    mac_address: Optional[str] = Field(
        None,
        description="Client MAC address from MikroTik"
    )

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        try:
            return normalise_phone(v)
        except ValueError as e:
            raise ValueError(str(e))


class PortalFreeTrialResponse(BaseModel):
    """
    Response returned when requesting a free trial voucher.
    """
    voucher_code: str

