"""
app/modules/subscriptions/schemas.py
====================================
Pydantic schemas for the subscriptions module.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SubscriptionCreate(BaseModel):
    customer_id: UUID
    package_id: UUID
    auto_renew: bool = True

class SubscriptionUpdate(BaseModel):
    package_id: Optional[UUID] = None
    auto_renew: Optional[bool] = None

class MySubscriptionUpdate(BaseModel):
    auto_renew: bool

class SubscriptionResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    customer_id: UUID
    package_id: UUID
    package_name: Optional[str] = None
    status: str
    current_period_end: datetime
    auto_renew: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ProrationResponse(BaseModel):
    old_package_id: UUID
    new_package_id: UUID
    days_remaining: int
    prorated_charge_kes: float
    description: str
