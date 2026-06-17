"""
app/modules/payments/service.py
================================
Service layer handling the business logic of payment processing,
Daraja STK push integration, and payment history queries.
"""

import logging
from typing import Optional

import asyncpg

from app.core.exceptions import NotFoundException, ConflictException, PaymentException
from app.integrations.daraja import daraja_client, DarajaError
from app.modules.payments.schemas import STKPushRequest

logger = logging.getLogger(__name__)


async def initiate_stk_push(
    conn: asyncpg.Connection,
    customer_id: str,
    data: STKPushRequest,
) -> dict:
    """
    Handles payment initialization:
      1. Validates that the package exists and is active.
      2. Creates a payment record in PostgreSQL with status="pending".
      3. Triggers Lipa Na M-Pesa STK push via DarajaClient.
      4. Updates the payment record with the CheckoutRequestID returned.
      5. Returns the created payment record.

    If Daraja rejects the request (e.g. whitelist failure or bad credentials),
    we update the database record status to "failed" with the reason and
    raise a PaymentException.
    """
    # ── 1. Fetch and validate the package ─────────────────────────────────────
    pkg_query = """
        SELECT id, name, price_kes, is_active
        FROM packages
        WHERE id = $1
    """
    package = await conn.fetchrow(pkg_query, data.package_id)
    if not package:
        raise NotFoundException("Package", str(data.package_id))

    if not package["is_active"]:
        raise ConflictException("Package is inactive and cannot be purchased.")

    # ── 2. Create the payment record with status="pending" ────────────────────
    insert_query = """
        INSERT INTO payments (customer_id, package_id, amount_kes, status, phone_number)
        VALUES ($1, $2, $3, 'pending', $4)
        RETURNING id, customer_id, package_id, amount_kes, status, phone_number, created_at
    """
    payment = await conn.fetchrow(
        insert_query,
        customer_id,
        data.package_id,
        package["price_kes"],
        data.phone,
    )
    payment_id = payment["id"]

    # Generate Lipa Na M-Pesa reference and description (truncating to Daraja limits)
    # AccountReference: max 12 chars. e.g. "WIFI-" + first 7 chars of payment_id UUID
    account_reference = f"WIFI-{str(payment_id)[:7]}"
    description = "WiFi Payment"

    # ── 3. Call Daraja STK Push ───────────────────────────────────────────────
    logger.info(
        f"Payment: initiating STK Push for customer {customer_id}, "
        f"payment_id {payment_id}, amount KES {package['price_kes']} to {data.phone}"
    )

    try:
        response = await daraja_client.stk_push(
            phone=data.phone,
            # Daraja expects an integer KES amount
            amount=int(package["price_kes"]),
            account_reference=account_reference,
            description=description,
        )

        checkout_id = response.get("CheckoutRequestID")

        # ── 4. Update the payment with CheckoutRequestID ─────────────────────
        update_query = """
            UPDATE payments
            SET mpesa_checkout_id = $1, updated_at = NOW()
            WHERE id = $2
            RETURNING id, customer_id, package_id, amount_kes, status, phone_number, created_at
        """
        updated_payment = await conn.fetchrow(update_query, checkout_id, payment_id)
        logger.info(f"Payment: STK push initiated successfully. CheckoutRequestID={checkout_id}")
        return dict(updated_payment)

    except (DarajaError, Exception) as e:
        # If the API call fails, we do NOT lose the payment log. We mark it as failed.
        # This keeps the ledger complete for auditor purposes.
        failure_msg = str(e)
        logger.error(f"Payment: Daraja STK Push initiation failed for payment {payment_id}: {failure_msg}")

        fail_update_query = """
            UPDATE payments
            SET status = 'failed', failure_reason = $1, updated_at = NOW()
            WHERE id = $2
        """
        await conn.execute(fail_update_query, failure_msg, payment_id)
        raise PaymentException(f"M-Pesa payment initiation failed: {failure_msg}")


async def get_payment_status(
    conn: asyncpg.Connection,
    payment_id: str,
    customer_id: str,
) -> dict:
    """
    Fetches the status of a specific payment.
    Ensures the customer requesting is the owner of the payment.
    Includes the voucher code if the payment is confirmed and a voucher has been generated.
    """
    query = """
        SELECT
            p.id AS payment_id,
            p.status,
            p.customer_id,
            v.code AS voucher_code
        FROM payments p
        LEFT JOIN vouchers v ON p.id = v.payment_id
        WHERE p.id = $1
    """
    row = await conn.fetchrow(query, payment_id)

    # 404 if the payment does not exist
    if not row:
        raise NotFoundException("Payment", payment_id)

    # Enforce customer isolation
    if str(row["customer_id"]) != str(customer_id):
        raise NotFoundException("Payment", payment_id)

    return {
        "payment_id": row["payment_id"],
        "status": row["status"],
        "voucher_code": row["voucher_code"],
    }


async def get_customer_payments(conn: asyncpg.Connection, customer_id: str) -> list[dict]:
    """Retrieves payment history for a specific customer."""
    query = """
        SELECT id, customer_id, package_id, amount_kes, status, phone_number, created_at
        FROM payments
        WHERE customer_id = $1
        ORDER BY created_at DESC
    """
    rows = await conn.fetch(query, customer_id)
    return [dict(r) for r in rows]


async def get_reseller_payments(conn: asyncpg.Connection, reseller_id: str) -> list[dict]:
    """Retrieves payments for all customers belonging to a specific reseller."""
    query = """
        SELECT p.id, p.customer_id, p.package_id, p.amount_kes, p.status, p.phone_number, p.created_at
        FROM payments p
        JOIN users u ON p.customer_id = u.id
        WHERE u.reseller_id = $1
        ORDER BY p.created_at DESC
    """
    rows = await conn.fetch(query, reseller_id)
    return [dict(r) for r in rows]


async def get_all_payments(conn: asyncpg.Connection) -> list[dict]:
    """Retrieves all payments in the system (admin view)."""
    query = """
        SELECT id, customer_id, package_id, amount_kes, status, phone_number, created_at
        FROM payments
        ORDER BY created_at DESC
    """
    rows = await conn.fetch(query)
    return [dict(r) for r in rows]
