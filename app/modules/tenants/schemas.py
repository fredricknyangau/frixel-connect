"""
app/modules/tenants/schemas.py
================================
Pydantic schemas for the tenants module.
"""

from uuid import UUID
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator, ConfigDict


# ── Registration ───────────────────────────────────────────────────────────────

class TenantRegisterRequest(BaseModel):
    """
    Body for POST /tenants/register — the ISP owner signup flow.

    This is a PUBLIC endpoint (no JWT required). An ISP owner visits ZealSync,
    fills in their business name and contact details, and gets back a tenant
    admin token immediately — analogous to any SaaS signup flow.

    In one transaction this creates:
      - A tenants row (the ISP business)
      - A users row for the owner with role='admin' and tenant_id set

    Why require password here and not send an email invite?
    For simplicity in Phase 1. Phase 8 (security hardening) can add an
    email verification step without changing this contract.
    """
    business_name: str
    owner_email:   EmailStr
    owner_phone:   str
    password:      str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v

    @field_validator("owner_phone")
    @classmethod
    def phone_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Phone cannot be empty.")
        return v

    @field_validator("business_name")
    @classmethod
    def business_name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Business name cannot be empty.")
        return v


# ── Response ───────────────────────────────────────────────────────────────────

class TenantResponse(BaseModel):
    """
    Returned by GET /tenants/me and embedded in register responses.
    Does NOT include any payment or billing detail — that is Phase 10.
    """
    model_config = ConfigDict(from_attributes=True)

    id:                UUID
    business_name:     str
    owner_email:       str
    owner_phone:       str
    subscription_tier: str
    max_customers:     int
    status:            str
    created_at:        datetime


class TenantRegisterResponse(BaseModel):
    """
    Returned by POST /tenants/register.
    Includes the tenant detail plus the admin's access token so the ISP owner
    is immediately authenticated — no second login step required.
    """
    tenant:       TenantResponse
    access_token: str
    token_type:   str = "bearer"
    user_id:      UUID
