"""
app/modules/routers/schemas.py
==============================
Pydantic validation schemas for the routers module.

SECURITY NOTE:
  The password and password_encrypted fields must NEVER be returned in any
  response schema (e.g., RouterResponse) to prevent credential leakage.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RouterCreate(BaseModel):
    """Payload to register a new MikroTik router."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="A unique friendly name for the router, e.g., 'Main Office'"
    )
    host: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="IP address or domain of the router"
    )
    port: int = Field(
        80,
        ge=1,
        le=65535,
        description="HTTP REST API port of the router"
    )
    username: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Admin username for the router"
    )
    password: str = Field(
        ...,
        min_length=1,
        description="Plaintext password (will be encrypted on save)"
    )
    site_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Physical site name associated with this router"
    )


class RouterUpdate(BaseModel):
    """Payload to update router configuration. All fields are optional."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    host: Optional[str] = Field(None, min_length=1, max_length=255)
    port: Optional[int] = Field(None, ge=1, le=65535)
    username: Optional[str] = Field(None, min_length=1, max_length=100)
    password: Optional[str] = Field(None, min_length=1)
    site_name: Optional[str] = Field(None, min_length=1, max_length=100)


class RouterResponse(BaseModel):
    """
    Response schema returning details of a router.
    
    CRITICAL: This schema NEVER includes the password or password_encrypted
    field in any response to prevent exposing credentials via the API.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    host: str
    port: int
    username: str
    site_name: str
    status: str
    last_heartbeat_at: Optional[datetime] = None
    created_at: datetime
