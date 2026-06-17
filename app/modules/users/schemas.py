"""
app/modules/users/schemas.py
============================
Pydantic validation models for the users module.

These schemas manage inputs and outputs for user profile queries and updates.
They enforce strict data validation (such as email formats and phone/password length)
before requests hit the database, ensuring clean and consistent data.
"""

from datetime import datetime
from uuid import UUID
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator, ConfigDict


class UserResponse(BaseModel):
    """
    Safely serializes a user profile returned to API clients.

    Why exclude hashed_password?
    We must NEVER send password hashes over the wire, even if hashed.
    Excluding it prevents credential leakages during normal profile queries.

    ConfigDict(from_attributes=True) allows Pydantic to build this model
    directly from asyncpg Record objects (database rows) without manual conversion.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    phone: str
    role: str
    reseller_id: Optional[UUID] = None
    is_active: bool
    created_at: datetime


class UserUpdate(BaseModel):
    """
    Body schema for updating contact details or active status.
    Used during partial update operations (e.g. PUT /customers/me).

    Why is everything Optional?
    A partial update (PATCH/PUT) should only require the fields that are changing.
    If a field is not provided (None), we skip updating it in the database.
    """
    phone: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("phone")
    @classmethod
    def phone_must_not_be_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Phone number cannot be empty.")
        return v


class CreateCustomerRequest(BaseModel):
    """
    Body schema for resellers/admins creating a customer.
    (POST /reseller/customers)

    Resellers do not pass a 'role' parameter; it is forced to 'customer'
    in the service/database layer to prevent role escalation.
    """
    email: EmailStr
    phone: str
    password: str

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
