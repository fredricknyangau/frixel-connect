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

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    site_name: str
    status: str
    last_heartbeat_at: Optional[datetime] = None
    created_at: datetime
    wireguard_public_key: Optional[str] = None
    wireguard_assigned_ip: Optional[str] = None
    wireguard_peer_public_key: Optional[str] = None

    @field_validator("wireguard_assigned_ip", mode="before")
    @classmethod
    def serialize_ip(cls, v):
        if v is not None:
            return str(v)
        return v


class OnboardingInitRequest(BaseModel):
    name: str
    site_name: str


class OnboardingInitResponse(BaseModel):
    router_id: UUID
    zealsync_server_endpoint: str
    zealsync_public_key: str
    assigned_ip: str
    server_wg_ip: str


class RegisterPeerRequest(BaseModel):
    router_id: UUID
    peer_public_key: str


class SaveCredentialsRequest(BaseModel):
    router_id: UUID
    username: str
    password: str
    port: int


class SetupProfileItem(BaseModel):
    name: str
    rate_limit: str


class SetupProfilesRequest(BaseModel):
    router_id: UUID
    profiles: list[SetupProfileItem]


class RouterOnboardingRequest(BaseModel):
    router_id: UUID


