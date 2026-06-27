"""
app/modules/payments/service.py
================================
Service layer for payment processing -fully tenant-scoped.

MULTI-TENANCY CHANGE (Phase 1):
  - initiate_stk_push: validates package belongs to caller's tenant before
    charging; stores tenant_id on the payment row.
  - All list/get functions scope their WHERE clauses to tenant_id.
  - get_payment_status: returns 404 for cross-tenant payment UUIDs (same
    principle as users -404 reveals nothing, 403 confirms existence).
"""

import logging
from uuid import UUID

import asyncpg

from app.core.exceptions import NotFoundException, ConflictException, PaymentException
from app.integrations.daraja import daraja_client, DarajaError
from app.modules.payments.schemas import STKPushRequest

logger = logging.getLogger(__name__)


async def initiate_stk_push(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    customer_id: str,
    data: STKPushRequest,
) -> dict:
    """
    Initiates an M-Pesa STK push payment.

    MULTI-TENANCY CHANGE: validates the package belongs to the caller's
    tenant before proceeding. A customer cannot pay for a package from
    a different ISP's tenant (which would be meaningless anyway, but we
    enforce it defensively).
    """
    # ── 1. Fetch and validate the package within this tenant ──────────────────
    package = await conn.fetchrow(
        """
        SELECT id, name, price_kes, is_active
        FROM packages
        WHERE id = $1
          AND tenant_id = $2
        """,
        data.package_id,
        tenant_id,
    )
    if not package:
        raise NotFoundException("Package", str(data.package_id))

    if not package["is_active"]:
        raise ConflictException("Package is inactive and cannot be purchased.")

    # ── 2. Create the payment record with tenant_id ───────────────────────────
    payment = await conn.fetchrow(
        """
        INSERT INTO payments
            (customer_id, package_id, amount_kes, status, phone_number, tenant_id)
        VALUES ($1, $2, $3, 'pending', $4, $5)
        RETURNING id, customer_id, package_id, amount_kes, status, phone_number, mpesa_receipt_number, created_at
        """,
        customer_id,
        data.package_id,
        package["price_kes"],
        data.phone,
        tenant_id,
    )
    payment_id = payment["id"]

    account_reference = f"WIFI-{str(payment_id)[:7]}"
    description = "WiFi Payment"

    logger.info(
        f"Payment: initiating STK Push for customer {customer_id}, "
        f"payment_id {payment_id}, amount KES {package['price_kes']} to {data.phone}, "
        f"tenant {tenant_id}"
    )

    # ── 3. Call Daraja STK Push ───────────────────────────────────────────────
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
              AND tenant_id = $3
            RETURNING id, customer_id, package_id, amount_kes, status, phone_number, mpesa_receipt_number, created_at
            """,
            checkout_id,
            payment_id,
            tenant_id,
        )
        logger.info(f"Payment: STK push initiated. CheckoutRequestID={checkout_id}")
        return dict(updated_payment)

    except (DarajaError, Exception) as e:
        failure_msg = str(e)
        logger.error(f"Payment: Daraja STK Push failed for payment {payment_id}: {failure_msg}")

        await conn.execute(
            """
            UPDATE payments
            SET status = 'failed', failure_reason = $1, updated_at = NOW()
            WHERE id = $2
              AND tenant_id = $3
            """,
            failure_msg,
            payment_id,
            tenant_id,
        )
        raise PaymentException(f"M-Pesa payment initiation failed: {failure_msg}")


async def get_payment_status(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    payment_id: str,
    customer_id: str,
) -> dict:
    """
    Fetches the status of a specific payment.

    Scoped to tenant_id AND customer_id. Returns 404 for:
      - Payment doesn't exist.
      - Payment belongs to a different tenant (not 403 -see module docstring).
      - Payment belongs to a different customer within the same tenant.
    """
    row = await conn.fetchrow(
        """
        SELECT
            p.id AS payment_id,
            p.status,
            p.customer_id,
            v.code AS voucher_code
        FROM payments p
        LEFT JOIN vouchers v ON p.id = v.payment_id AND v.tenant_id = p.tenant_id
        WHERE p.id = $1
          AND p.tenant_id = $2
        """,
        payment_id,
        tenant_id,
    )

    if not row:
        raise NotFoundException("Payment", payment_id)

    # Customer isolation within the tenant
    if str(row["customer_id"]) != str(customer_id):
        raise NotFoundException("Payment", payment_id)

    return {
        "payment_id": row["payment_id"],
        "status": row["status"],
        "voucher_code": row["voucher_code"],
    }


async def get_customer_payments(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    customer_id: str,
) -> list[dict]:
    """Retrieves payment history for a customer within a tenant."""
    rows = await conn.fetch(
        """
        SELECT p.id, p.customer_id, p.package_id, p.amount_kes, p.status, p.phone_number, p.mpesa_receipt_number, p.created_at,
               pkg.name AS package_name
        FROM payments p
        JOIN packages pkg ON p.package_id = pkg.id AND pkg.tenant_id = p.tenant_id
        WHERE p.customer_id = $1
          AND p.tenant_id = $2
        ORDER BY p.created_at DESC
        """,
        customer_id,
        tenant_id,
    )
    return [dict(r) for r in rows]


async def get_reseller_payments(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    reseller_id: str,
) -> list[dict]:
    """Retrieves payments for a reseller's customers within a tenant."""
    rows = await conn.fetch(
        """
        SELECT p.id, p.customer_id, p.package_id, p.amount_kes,
               p.status, p.phone_number, p.mpesa_receipt_number, p.created_at,
               pkg.name AS package_name
        FROM payments p
        JOIN users u ON p.customer_id = u.id
        JOIN packages pkg ON p.package_id = pkg.id AND pkg.tenant_id = p.tenant_id
        WHERE u.reseller_id = $1
          AND p.tenant_id = $2
        ORDER BY p.created_at DESC
        """,
        reseller_id,
        tenant_id,
    )
    return [dict(r) for r in rows]


async def get_all_payments(
    conn: asyncpg.Connection,
    tenant_id: UUID,
) -> list[dict]:
    """Retrieves all payments in the tenant (admin view)."""
    rows = await conn.fetch(
        """
        SELECT p.id, p.customer_id, p.package_id, p.amount_kes, p.status, p.phone_number, p.mpesa_receipt_number, p.created_at,
               pkg.name AS package_name
        FROM payments p
        JOIN packages pkg ON p.package_id = pkg.id AND pkg.tenant_id = p.tenant_id
        WHERE p.tenant_id = $1
        ORDER BY p.created_at DESC
        """,
        tenant_id,
    )
    return [dict(r) for r in rows]


async def get_stuck_payments(
    conn: asyncpg.Connection,
    tenant_id: UUID,
) -> list[dict]:
    """
    Retrieves confirmed payments past the reconciliation threshold with no voucher.
    These are "stuck" payments that require background or manual retry provisioning.
    """
    rows = await conn.fetch(
        """
        SELECT id, customer_id, package_id, amount_kes, status, phone_number, mpesa_receipt_number, created_at
        FROM payments p
        WHERE tenant_id = $1
          AND status = 'confirmed'
          AND created_at < NOW() - INTERVAL '2 minutes'
          AND NOT EXISTS (
              SELECT 1 FROM vouchers v
              WHERE v.payment_id = p.id
                AND v.tenant_id = p.tenant_id
          )
        ORDER BY created_at DESC
        """,
        tenant_id,
    )
    return [dict(r) for r in rows]
