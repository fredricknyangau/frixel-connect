"""
app/modules/hotspot/service.py
================================
Service layer for the public captive portal hotspot flow.
"""

import logging
import uuid
from uuid import UUID

import asyncpg

from app.core.security import hash_password
from app.core.exceptions import NotFoundException, ConflictException, PaymentException
from app.integrations.daraja import daraja_client, DarajaError
from app.modules.hotspot.schemas import PortalSTKPushRequest

logger = logging.getLogger(__name__)


async def get_or_create_guest_customer(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    phone: str,
) -> UUID:
    """
    Finds an existing customer by phone within the tenant, or creates a new guest account.
    """
    user = await conn.fetchrow(
        "SELECT id FROM users WHERE phone = $1 AND tenant_id = $2",
        phone,
        tenant_id,
    )
    if user:
        return user["id"]

    # Create new guest user
    email = f"guest-{phone}-{uuid.uuid4().hex[:6]}@guest.example.com"
    random_pass = uuid.uuid4().hex
    hashed_pass = hash_password(random_pass)
    
    new_user = await conn.fetchrow(
        """
        INSERT INTO users (email, phone, hashed_password, role, tenant_id, is_active)
        VALUES ($1, $2, $3, 'customer', $4, true)
        RETURNING id
        """,
        email,
        phone,
        hashed_pass,
        tenant_id,
    )
    logger.info(f"Portal: Created guest user {new_user['id']} for phone {phone} in tenant {tenant_id}")
    return new_user["id"]


async def initiate_hotspot_payment(
    conn: asyncpg.Connection,
    data: PortalSTKPushRequest,
) -> dict:
    """
    Initiates an STK push for a guest on the captive portal.
    """
    customer_id = await get_or_create_guest_customer(conn, data.tenant_id, data.phone)

    package = await conn.fetchrow(
        """
        SELECT id, name, price_kes, is_active
        FROM packages
        WHERE id = $1
          AND tenant_id = $2
        """,
        data.package_id,
        data.tenant_id,
    )
    if not package:
        raise NotFoundException("Package", str(data.package_id))

    if not package["is_active"]:
        raise ConflictException("Package is inactive and cannot be purchased.")

    payment = await conn.fetchrow(
        """
        INSERT INTO payments
            (customer_id, package_id, amount_kes, status, phone_number, tenant_id)
        VALUES ($1, $2, $3, 'pending', $4, $5)
        RETURNING id, customer_id, package_id, amount_kes, status, phone_number, created_at
        """,
        customer_id,
        data.package_id,
        package["price_kes"],
        data.phone,
        data.tenant_id,
    )
    payment_id = payment["id"]

    account_reference = f"WIFI-{str(payment_id)[:7]}"
    description = "Hotspot WiFi Pass"

    logger.info(
        f"Portal Payment: initiating STK Push for guest {customer_id}, "
        f"payment_id {payment_id}, MAC {data.mac_address}"
    )

    try:
        response = await daraja_client.stk_push(
            phone=data.phone,
            amount=int(package["price_kes"]),
            account_reference=account_reference,
            description=description,
        )

        checkout_id = response.get("CheckoutRequestID")

        updated_payment = await conn.fetchrow(
            """
            UPDATE payments
            SET mpesa_checkout_id = $1, updated_at = NOW()
            WHERE id = $2
            RETURNING id, customer_id, package_id, amount_kes, status, phone_number, created_at
            """,
            checkout_id,
            payment_id,
        )
        return dict(updated_payment)

    except (DarajaError, Exception) as e:
        failure_msg = str(e)
        logger.error(f"Portal Payment: Daraja STK Push failed for payment {payment_id}: {failure_msg}")

        await conn.execute(
            """
            UPDATE payments
            SET status = 'failed', failure_reason = $1, updated_at = NOW()
            WHERE id = $2
            """,
            failure_msg,
            payment_id,
        )
        raise PaymentException(f"M-Pesa payment initiation failed: {failure_msg}")


async def get_hotspot_payment_status(
    conn: asyncpg.Connection,
    payment_id: str,
) -> dict:
    """
    Public endpoint to fetch payment status without authentication.
    Only returns status and voucher code.
    """
    try:
        payment_uuid = UUID(payment_id)
    except ValueError:
        raise NotFoundException("Payment", payment_id)

    row = await conn.fetchrow(
        """
        SELECT
            p.id AS payment_id,
            p.status,
            v.code AS voucher_code
        FROM payments p
        LEFT JOIN vouchers v ON p.id = v.payment_id
        WHERE p.id = $1
        """,
        payment_uuid,
    )

    if not row:
        raise NotFoundException("Payment", payment_id)

    return {
        "payment_id": row["payment_id"],
        "status": row["status"],
        "voucher_code": row["voucher_code"],
    }
