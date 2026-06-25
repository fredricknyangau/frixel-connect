"""
app/modules/super_admin/schemas.py
====================================
Pydantic v2 request/response models for the super admin portal.

All models use strict typing (no Any). Field-level validators document
the constraints enforced at the HTTP boundary-these are the FIRST layer
of defence, before the service functions touch the database.
"""

from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Auth Request Models ───────────────────────────────────────────────────────

class SuperAdminLoginRequest(BaseModel):
    """Step 1 of two-step login: email + password → pre-auth token."""
    email: EmailStr
    password: str = Field(min_length=1)


class SuperAdminTOTPSetupRequest(BaseModel):
    """
    Request to generate the TOTP QR code (first login only).
    The pre_auth_token proves the caller completed step 1 (password check).
    This is NOT a JWT-it is an opaque token tied to the pre_auth_tokens table.
    """
    pre_auth_token: str = Field(min_length=32)


class SuperAdminTOTPVerifyRequest(BaseModel):
    """
    Step 2 of two-step login: pre_auth_token + TOTP code → full JWT.
    The totp_code must be exactly 6 decimal digits (no spaces, no dashes).
    """
    pre_auth_token: str = Field(min_length=32)
    totp_code: str = Field(min_length=6, max_length=6)

    @field_validator("totp_code")
    @classmethod
    def must_be_digits(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("TOTP code must be exactly 6 digits.")
        return v


# ── Auth Response Models ──────────────────────────────────────────────────────

class SuperAdminPreAuthResponse(BaseModel):
    """
    Returned after a successful password check.
    The pre_auth_token is short-lived (5 min) and single-use.
    It must be presented to either /totp/setup or /totp/verify.
    It cannot be used to call any protected super admin endpoint.
    """
    pre_auth_token: str
    # Always True in production. Present for frontend conditional rendering.
    totp_required: bool = True
    # True if this account has never completed TOTP setup (totp_verified_at IS NULL).
    # Frontend shows the "scan QR code" screen instead of the "enter code" screen.
    totp_setup_required: bool


class SuperAdminTOTPSetupResponse(BaseModel):
    """
    Returned by /totp/setup-contains the QR code the super admin scans.
    This response is issued ONCE per account setup. After totp_verified_at
    is set, this endpoint returns 409 Conflict.

    qr_code_base64: A data URI ("data:image/png;base64,...") ready for <img src=...>
    secret_preview: First 4 characters of the raw Base32 secret.
                    Used ONLY for manual entry if QR scanning is impossible.
                    NOT the full secret-revealing more would be a security risk.
    """
    qr_code_base64: str
    secret_preview: str


class SuperAdminTokenResponse(BaseModel):
    """
    Full access token returned after successful TOTP verification.
    expires_in is always 900 (15 minutes). Refresh tokens are NOT issued
    for super admin-re-authentication is required after expiry.
    """
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 900  # 15 minutes in seconds-hardcoded, not configurable
    super_admin_id: str
    full_name: str


class SuperAdminProfile(BaseModel):
    """Returned by GET /super-admin/auth/me."""
    id: str
    email: str
    full_name: str
    totp_verified_at: Optional[str]
    last_login_at: Optional[str]
    is_active: bool
    created_at: str


# ── Tenant Management Request Models ─────────────────────────────────────────

class TenantSuspendRequest(BaseModel):
    """
    Body for POST /super-admin/tenants/{id}/suspend.
    The reason is mandatory-it becomes part of the audit log metadata
    and provides an audit trail for why the tenant was suspended.
    """
    reason: str = Field(min_length=5, max_length=500)


class CreateImpersonationRequest(BaseModel):
    """
    Body for POST /super-admin/tenants/{id}/impersonate.
    duration_minutes controls the impersonation token lifetime.
    Default: 30 minutes. Max enforced in the service: 480 minutes (8 hours).
    """
    duration_minutes: int = Field(default=30, ge=5, le=480)


# ── Super Admin Account Management ────────────────────────────────────────────

class CreateSuperAdminRequest(BaseModel):
    """
    Body for POST /super-admin/accounts.
    Only an authenticated super admin can create another super admin.
    The new account starts with totp_secret=NULL, totp_verified_at=NULL —
    the new super admin must complete TOTP setup on their first login.
    """
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=100)
    password: str = Field(
        min_length=12,
        description="Minimum 12 characters. The new admin will set up TOTP on first login.",
    )
