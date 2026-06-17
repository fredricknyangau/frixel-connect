"""
app/modules/sessions/schemas.py
================================
Pydantic schemas for the sessions module.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SessionResponse(BaseModel):
    """
    Response schema representing a hotspot user session.
    """
    id: UUID
    voucher_id: UUID
    customer_id: UUID
    mac_address: Optional[str] = Field(None, description="MAC address of the connected client device")
    ip_address: Optional[str] = Field(None, description="IP address assigned to the client device")
    bytes_uploaded: int = Field(0, description="Total bytes uploaded during session")
    bytes_downloaded: int = Field(0, description="Total bytes downloaded during session")
    started_at: datetime
    ended_at: Optional[datetime] = Field(None, description="Timestamp when the session was closed")
    created_at: datetime

    class Config:
        from_attributes = True
        # Ensure that postgres INET type is serialised cleanly to string (e.g. IPv4/IPv6 address)
        json_encoders = {
            # In Pydantic v2, encoders are usually handled via model serializers,
            # but standard ipaddress/asyncpg types serialise to str automatically.
        }
