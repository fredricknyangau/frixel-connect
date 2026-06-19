"""
app/modules/auth/schemas.py
===========================
Pydantic models for the auth module.

MULTI-TENANCY CHANGE (Phase 1):
  RegisterRequest now carries tenant_id (injected by the router from the
  caller's JWT, not supplied by the client body).
  TokenResponse now includes tenant_id in the response so the frontend
  can display tenant-specific UI without a separate fetch.
"""

from uuid import UUID
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator, ConfigDict


# ── Register ──────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    """
    Body for POST /auth/register.

    tenant_id is NOT in the request body — it is injected by the router
    from the authenticated admin's JWT token. This prevents a caller from
    registering a user into an arbitrary tenant by supplying a different UUID.
    """
    email:     EmailStr
    phone:     str
    password:  str
    role:      str = "customer"
    # Injected by the router — not expected from the client body.
    # Set as Optional with None default so Pydantic won't reject the model
    # when constructed without it, then the router sets it before calling
    # the service.
    tenant_id: Optional[UUID] = None

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, v: str) -> str:
        v = v.lower()
        allowed = {"admin", "reseller", "customer"}
        if v not in allowed:
            raise ValueError(
                f"Invalid role '{v}'. Must be one of: admin, reseller, customer."
            )
        return v

    @field_validator("password")
    @classmethod
    def password_must_be_strong_enough(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v

    @field_validator("phone")
    @classmethod
    def phone_must_not_be_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Phone number cannot be empty.")
        return v


# ── Login ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    """Body for POST /auth/login. 'email' can be an actual email or a phone number."""
    email:    str
    password: str


# ── Token response ────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    """
    Returned by both /auth/register and /auth/login.

    MULTI-TENANCY CHANGE: now includes tenant_id so the frontend knows
    which tenant context the user is operating in without a separate
    GET /tenants/me call on startup.
    """
    model_config = ConfigDict(from_attributes=True)

    access_token: str
    refresh_token: str
    token_type:   str = "bearer"
    role:         str
    user_id:      UUID
    tenant_id:    UUID

class RefreshTokenRequest(BaseModel):
    refresh_token: str
