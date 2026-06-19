"""
app/modules/subscriptions/router.py
===================================
FastAPI router for PPPoE subscriptions.
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies import require_role
from app.database import get_db
from app.modules.subscriptions import schemas, service

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("/me", response_model=schemas.SubscriptionResponse)
async def get_my_subscription(
    current_user: dict = Depends(require_role("customer")),
):
    """Gets the authenticated customer's current subscription."""
    async with get_db() as conn:
        sub = await service.get_customer_subscription(
            conn,
            UUID(current_user["tenant_id"]),
            UUID(current_user["user_id"]),
        )
        return schemas.SubscriptionResponse.model_validate(sub)


@router.put("/me", response_model=schemas.SubscriptionResponse)
async def update_my_subscription(
    data: schemas.MySubscriptionUpdate,
    current_user: dict = Depends(require_role("customer")),
):
    """Updates the authenticated customer's auto-renew preference."""
    async with get_db() as conn:
        sub = await service.update_customer_auto_renew(
            conn,
            UUID(current_user["tenant_id"]),
            UUID(current_user["user_id"]),
            data.auto_renew,
        )
        return schemas.SubscriptionResponse.model_validate(sub)

@router.get("/{subscription_id}/proration", response_model=schemas.ProrationResponse)
async def get_proration(
    subscription_id: UUID,
    new_package_id: UUID,
    current_user: dict = Depends(require_role("admin", "reseller"))
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
    current_user: dict = Depends(require_role("admin", "reseller"))
):
    """
    Gets a specific subscription.
    """
    async with get_db() as conn:
        sub = await service.get_subscription(conn, current_user["tenant_id"], subscription_id)
        return schemas.SubscriptionResponse.model_validate(sub)

admin_router = APIRouter(prefix="/admin/subscriptions", tags=["Admin Subscriptions"])

@admin_router.get("")
async def list_subscriptions_admin(
    status: str = None,
    current_user: dict = Depends(require_role("admin", "reseller"))
):
    """List all subscriptions for the tenant, optionally filtered by status."""
    async with get_db() as conn:
        subs = await service.list_subscriptions_admin(conn, current_user["tenant_id"], status)
        return subs

@admin_router.post("/{subscription_id}/suspend")
async def suspend_subscription(
    subscription_id: UUID,
    current_user: dict = Depends(require_role("admin"))
):
    """Suspend a subscription. Admin-only -resellers cannot trigger suspensions."""
    async with get_db() as conn:
        await service.update_subscription_status(conn, current_user["tenant_id"], subscription_id, "suspended")
        return {"status": "success", "message": "Subscription suspended."}

@admin_router.post("/{subscription_id}/reactivate")
async def reactivate_subscription(
    subscription_id: UUID,
    current_user: dict = Depends(require_role("admin"))
):
    """Reactivate a suspended subscription. Admin-only -resellers cannot trigger reactivations."""
    async with get_db() as conn:
        await service.update_subscription_status(conn, current_user["tenant_id"], subscription_id, "active")
        return {"status": "success", "message": "Subscription reactivated."}
