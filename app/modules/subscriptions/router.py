"""
app/modules/subscriptions/router.py
===================================
FastAPI router for PPPoE subscriptions.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user, require_role
from app.database import get_db
from app.modules.subscriptions import schemas, service

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

@router.get("/{subscription_id}/proration", response_model=schemas.ProrationResponse)
async def get_proration(
    subscription_id: UUID,
    new_package_id: UUID,
    current_user: dict = Depends(require_role(["admin", "reseller"]))
):
    """
    Calculates proration if a customer upgrades/downgrades their package mid-period.
    """
    async with get_db() as conn:
        return await service.calculate_proration(
            conn,
            current_user["tenant_id"],
            subscription_id,
            new_package_id
        )

@router.get("/{subscription_id}", response_model=schemas.SubscriptionResponse)
async def get_subscription(
    subscription_id: UUID,
    current_user: dict = Depends(require_role(["admin", "reseller"]))
):
    """
    Gets a specific subscription.
    """
    async with get_db() as conn:
        sub = await service.get_subscription(conn, current_user["tenant_id"], subscription_id)
        return schemas.SubscriptionResponse.model_validate(sub)
