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
from app.modules.hotspot.schemas import PortalSTKPushRequest, PortalFreeTrialRequest
import secrets


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


async def provision_free_trial(
    conn: asyncpg.Connection,
    data: PortalFreeTrialRequest,
) -> str:
    """
    Checks trial usage limits and generates a 10-minute trial voucher.
    Bypasses M-Pesa billing using a mock payment record TRIAL-[HEX].
    """
    customer_id = await get_or_create_guest_customer(conn, data.tenant_id, data.phone)

    # 1. Check if user already claimed a free trial in the last 24 hours
    existing_trial = await conn.fetchval(
        """
        SELECT COUNT(*) FROM payments p
        JOIN vouchers v ON p.id = v.payment_id
        WHERE p.customer_id = $1 
          AND p.tenant_id = $2
          AND p.mpesa_receipt_number LIKE 'TRIAL-%'
          AND p.created_at > NOW() - INTERVAL '24 hours'
        """,
        customer_id,
        data.tenant_id,
    )
    if existing_trial > 0:
        raise ConflictException("You have already used your free trial for today. Please select a paid plan to connect.")

    # 2. Find or create a 'Free Trial' package for the tenant
    package = await conn.fetchrow(
        """
        SELECT id FROM packages
        WHERE tenant_id = $1 AND name = 'Free Trial'
        """,
        data.tenant_id,
    )
    if package:
        package_id = package["id"]
    else:
        # Create a default "Free Trial" package dynamically
        package_id = await conn.fetchval(
            """
            INSERT INTO packages (name, description, price_kes, duration_minutes, speed_mbps, is_active, tenant_id)
            VALUES ($1, $2, $3, $4, $5, true, $6)
            RETURNING id
            """,
            "Free Trial",
            "10 Minutes Free Trial Access",
            1.00,  # 1 KES to bypass CHECK constraint (amount_kes > 0)
            10,    # 10 minutes
            2,     # 2 Mbps
            data.tenant_id,
        )

    # 3. Create a mock confirmed payment record to bypass M-Pesa gateway
    trial_receipt = f"TRIAL-{secrets.token_hex(4).upper()}"
    payment = await conn.fetchrow(
        """
        INSERT INTO payments (customer_id, package_id, amount_kes, status, phone_number, tenant_id, mpesa_receipt_number)
        VALUES ($1, $2, 1.00, 'confirmed', $3, $4, $5)
        RETURNING id
        """,
        customer_id,
        package_id,
        data.phone,
        data.tenant_id,
        trial_receipt,
    )
    payment_id = payment["id"]

    # 4. Invoke voucher generation pipeline
    from app.modules.vouchers import service as vouchers_service
    voucher_code = await vouchers_service.generate_voucher(conn, str(payment_id), is_final_attempt=True)
    return voucher_code

