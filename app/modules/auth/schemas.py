"""
app/modules/auth/schemas.py
===========================
Pydantic models for the auth module.

A schema in this project is the contract between the HTTP boundary and the
service layer. It does THREE things:
  1. Parses the incoming JSON body into typed Python objects.
  2. Validates the data (email format, password strength, allowed roles).
  3. Documents the API surface (FastAPI reads these for /docs).

We use Pydantic v2 (already in requirements.txt). The key v2 changes you need
to know vs v1:
  - @validator is gone, replaced by @field_validator
  - class Config is mostly gone, replaced by model_config = ConfigDict(...)
  - field_validator mode="before" runs before type coercion
  - field_validator mode="after" runs after type coercion (value is already the right type)
"""

from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator, ConfigDict


# ── Register ──────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    """
    Body for POST /auth/register.

    Role validation: only 'admin', 'reseller', 'customer' are accepted.
    In a real production system you'd probably remove 'admin' from self-
    registration and only allow it via a superadmin invite flow. For this
    build, we keep it open so you can test all three roles without hacking
    the database directly.
    """
    email:    EmailStr   # Pydantic validates email format automatically
    phone:    str
    password: str
    role:     str = "customer"  # defaults to customer if not provided

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, v: str) -> str:
        # Normalise to lowercase first so "Admin" and "ADMIN" are accepted.
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
        # Minimum viable password policy. Not production-grade, but enough to
        # prevent empty or trivial passwords during development.
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
    """Body for POST /auth/login."""
    email:    EmailStr
    password: str


# ── Token response ────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    """
    Returned by both /auth/register and /auth/login.

    Why auto-login on register?
    The customer journey is: buy WiFi → log in → pay → connect.
    Making them register and THEN log in as two separate steps adds friction
    at the worst possible moment (they're standing somewhere trying to get
    internet). Auto-login removes one round trip.

    model_config = ConfigDict(from_attributes=True) allows Pydantic to build
    this model directly from an asyncpg Record object (which behaves like a
    dict/object with attribute access). Without this, you'd have to manually
    convert every Record to a dict before returning it.
    """
    model_config = ConfigDict(from_attributes=True)

    access_token: str
    token_type:   str = "bearer"
    role:         str
    user_id:      UUID
