"""
app/modules/subscriptions/service.py
====================================
Business logic for PPPoE subscriptions.
Handles creation, proration math, and payment renewal logic.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import asyncpg

from app.core.exceptions import NotFoundException, ConflictException
from app.modules.subscriptions.schemas import SubscriptionCreate, SubscriptionUpdate

logger = logging.getLogger(__name__)

async def get_subscription(conn: asyncpg.Connection, tenant_id: UUID, subscription_id: UUID) -> dict:
    row = await conn.fetchrow(
        "SELECT * FROM subscriptions WHERE id = $1 AND tenant_id = $2",
        subscription_id, tenant_id
    )
    if not row:
        raise NotFoundException("Subscription", str(subscription_id))
    return dict(row)

async def calculate_proration(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    subscription_id: UUID,
    new_package_id: UUID
) -> dict:
    """
    Computes the prorated charge when switching packages mid-period.
    
    Formula: (days remaining / total days of old package) * (new price - old price)
    If downgrading (new price < old price), this might return a negative value 
    (credit) or simply 0 based on business logic. Here we just compute the raw difference.
    """
    sub = await get_subscription(conn, tenant_id, subscription_id)
    
    # Fetch old package
    old_pkg = await conn.fetchrow(
        "SELECT price_kes, duration_days FROM packages WHERE id = $1 AND tenant_id = $2",
        sub["package_id"], tenant_id
    )
    # Fetch new package
    new_pkg = await conn.fetchrow(
        "SELECT price_kes, duration_days FROM packages WHERE id = $1 AND tenant_id = $2",
        new_package_id, tenant_id
    )
    if not new_pkg:
        raise NotFoundException("Package", str(new_package_id))
        
    now = datetime.now(timezone.utc)
    current_end = sub["current_period_end"]
    
    if current_end <= now:
        # Period already ended, no proration. Just charge the full new price.
        return {
            "old_package_id": sub["package_id"],
            "new_package_id": new_package_id,
            "days_remaining": 0,
            "prorated_charge_kes": float(new_pkg["price_kes"]),
            "description": "Period expired, full charge applies."
        }
        
    days_remaining = (current_end - now).days
    # Edge case: if less than 24 hours remaining, we might consider it 0 or 1.
    if days_remaining < 0:
        days_remaining = 0
        
    old_price = float(old_pkg["price_kes"])
    new_price = float(new_pkg["price_kes"])
    old_duration = int(old_pkg["duration_days"])
    
    # Prorated difference
    if old_duration > 0:
        ratio = days_remaining / old_duration
    else:
        ratio = 0
        
    price_diff = new_price - old_price
    prorated_charge = round(ratio * price_diff, 2)
    
    # Usually we don't refund to M-Pesa automatically. If prorated_charge < 0, 
    # it becomes a wallet credit or just 0 for this transaction.
    if prorated_charge < 0:
        prorated_charge = 0.0
        
    return {
        "old_package_id": sub["package_id"],
        "new_package_id": new_package_id,
        "days_remaining": days_remaining,
        "prorated_charge_kes": prorated_charge,
        "description": f"Prorated charge for upgrading with {days_remaining} days remaining."
    }

async def process_renewal_payment(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    customer_id: UUID,
    package_id: UUID
) -> None:
    """
    Called when a payment is successful.
    If the customer has a subscription, extends the period and re-enables PPPoE if suspended.
    If no subscription exists, creates one.
    """
    pkg = await conn.fetchrow(
        "SELECT duration_days FROM packages WHERE id = $1 AND tenant_id = $2",
        package_id, tenant_id
    )
    if not pkg:
        raise NotFoundException("Package", str(package_id))
        
    duration_days = pkg["duration_days"]
    
    sub = await conn.fetchrow(
        "SELECT id, status, current_period_end FROM subscriptions WHERE customer_id = $1 AND tenant_id = $2",
        customer_id, tenant_id
    )
    
    now = datetime.now(timezone.utc)
    
    if sub:
        # Extend current_period_end
        # If it was active/grace and hasn't expired yet, add to existing end
        # If it was suspended or already expired, start from NOW
        current_end = sub["current_period_end"]
        if current_end > now and sub["status"] in ("active", "grace"):
            new_end = current_end + datetime.timedelta(days=duration_days)
        else:
            # We must import timedelta
            from datetime import timedelta
            new_end = now + timedelta(days=duration_days)
            
        await conn.execute(
            """
            UPDATE subscriptions 
            SET status = 'active', current_period_end = $1, package_id = $2, updated_at = NOW()
            WHERE id = $3
            """,
            new_end, package_id, sub["id"]
        )
        
        # If it was suspended, re-enable PPPoE secret
        if sub["status"] == "suspended":
            from app.integrations.mikrotik import get_mikrotik_client
            
            # Fetch router for customer
            user_row = await conn.fetchrow("SELECT router_id, email, phone FROM users WHERE id = $1", customer_id)
            if user_row and user_row["router_id"]:
                router_row = await conn.fetchrow(
                    "SELECT host, port, username, password_encrypted FROM routers WHERE id = $1 AND tenant_id = $2",
                    user_row["router_id"], tenant_id
                )
                if router_row:
                    client = get_mikrotik_client(dict(router_row))
                    # username in PPPoE is typically the email or phone. In this system, 
                    # let's assume it's the customer's phone or email. We'll use phone.
                    await client.enable_ppp_secret(user_row["phone"])
                    logger.info(f"Subscription: Re-enabled PPPoE secret for customer {user_row['phone']}")

    else:
        # Create new
        from datetime import timedelta
        new_end = now + timedelta(days=duration_days)
        await conn.execute(
            """
            INSERT INTO subscriptions (tenant_id, customer_id, package_id, current_period_end, status)
            VALUES ($1, $2, $3, $4, 'active')
            """,
            tenant_id, customer_id, package_id, new_end
        )
