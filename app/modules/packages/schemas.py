"""
app/modules/packages/schemas.py
================================
Pydantic schemas for the packages module.

Three schemas, three purposes:
  PackageCreate  -validates the body for POST /packages (all fields required)
  PackageUpdate  -validates the body for PUT /packages/{id} (all fields optional)
  PackageResponse -shapes what we return to the client (no internal fields)

Why three separate schemas instead of one?
  PackageCreate: every field is required. Missing a field → 422 immediately.
  PackageUpdate: every field is Optional because PATCH-style updates ("only
    update the fields I send") are friendlier than forcing the client to
    resend unchanged data. We call this a "partial update" pattern.
  PackageResponse: we control exactly what the client sees. The DB row has
    a 'created_by' UUID -we choose not to expose that. If we serialise the
    raw DB row, the client sees everything, including fields that may leak
    internal structure or change without warning.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID
from typing import Optional

from pydantic import BaseModel, field_validator, ConfigDict


class PackageCreate(BaseModel):
    """
    Body for POST /packages.
    Validation rules mirror the CHECK constraints in 002_create_packages.sql —
    we want to reject bad data at the API layer before it touches the DB.
    """
    name:          str
    description:   Optional[str] = None
    price_kes:     Decimal
    duration_minutes: int
    speed_mbps:    int
    data_quota_mb: Optional[int] = None

    @field_validator("data_quota_mb")
    @classmethod
    def data_quota_must_be_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("data_quota_mb must be greater than 0.")
        return v

    @field_validator("price_kes")
    @classmethod
    def price_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("price_kes must be greater than 0.")
        # Round to 2 decimal places to prevent floating point weirdness
        # when comparing against DB NUMERIC(10,2) values.
        return round(v, 2)

    @field_validator("duration_minutes")
    @classmethod
    def duration_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("duration_minutes must be greater than 0.")
        return v

    @field_validator("speed_mbps")
    @classmethod
    def speed_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("speed_mbps must be greater than 0.")
        return v

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Package name cannot be empty.")
        if len(v) > 100:
            raise ValueError("Package name cannot exceed 100 characters.")
        return v


class PackageUpdate(BaseModel):
    """
    Body for PUT /packages/{id}.

    ALL fields are Optional -the client only sends the fields they want to
    change. The service layer builds a dynamic UPDATE query that only touches
    non-None fields. This means:
      PUT /packages/123 {"price_kes": 75}
    Only updates price_kes and sets updated_at -name, speed_mbps, etc. are
    untouched. Without Optional fields, the client would have to resend the
    entire package object just to change the price.
    """
    name:          Optional[str]     = None
    description:   Optional[str]     = None
    price_kes:     Optional[Decimal] = None
    duration_minutes: Optional[int]     = None
    speed_mbps:    Optional[int]     = None
    data_quota_mb: Optional[int]     = None

    @field_validator("data_quota_mb")
    @classmethod
    def data_quota_must_be_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("data_quota_mb must be greater than 0.")
        return v

    # We reuse the same validators from PackageCreate.
    # A value of None passes validation (Optional means it can be absent).
    # A value of 0 or -50 still fails the validator.

    @field_validator("price_kes")
    @classmethod
    def price_must_be_positive(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v <= 0:
            raise ValueError("price_kes must be greater than 0.")
        return round(v, 2) if v is not None else None

    @field_validator("duration_minutes")
    @classmethod
    def duration_must_be_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("duration_minutes must be greater than 0.")
        return v

    @field_validator("speed_mbps")
    @classmethod
    def speed_must_be_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("speed_mbps must be greater than 0.")
        return v

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Package name cannot be empty.")
            if len(v) > 100:
                raise ValueError("Package name cannot exceed 100 characters.")
        return v


class PackageResponse(BaseModel):
    """
    What the client sees when we return a package.

    from_attributes=True: lets Pydantic build this from an asyncpg Record
    object (which supports attribute access like record.id, record.name).
    Without this, you'd have to do dict(record) before returning.
    """
    model_config = ConfigDict(from_attributes=True)

    id:            UUID
    name:          str
    description:   Optional[str]
    price_kes:     Decimal
    duration_minutes: int
    speed_mbps:    int
    data_quota_mb: Optional[int]
    is_active:     bool
    created_at:    datetime
    # updated_at is included so the admin UI can show "last modified"
    updated_at:    datetime
    # created_by is intentionally excluded -internal field
