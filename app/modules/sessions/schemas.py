"""
app/modules/sessions/schemas.py
================================
Pydantic schemas for the sessions module.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SessionResponse(BaseModel):
    """
    Response schema representing a hotspot user session.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    voucher_id: UUID
    customer_id: UUID
    mac_address: Optional[str] = Field(None, description="MAC address of the connected client device")
    ip_address: Optional[str] = Field(None, description="IP address assigned to the client device")

    @field_validator('ip_address', mode='before')
    @classmethod
    def cast_ip_address_to_str(cls, v):
        if v is not None:
            return str(v)
        return v

    bytes_uploaded: int = Field(0, description="Total bytes uploaded during session")
    bytes_downloaded: int = Field(0, description="Total bytes downloaded during session")
    started_at: datetime
    ended_at: Optional[datetime] = Field(None, description="Timestamp when the session was closed")
    created_at: datetime
