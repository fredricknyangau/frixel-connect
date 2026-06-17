"""
app/modules/webhooks/service.py
================================
Service layer handling Safaricom Daraja STK Push callback webhooks.
Enforces the reliability contract and strict idempotency.
"""

import logging
from fastapi import BackgroundTasks
import asyncpg

from app.modules.vouchers.service import generate_voucher_task

logger = logging.getLogger(__name__)


async def process_daraja_webhook(
    conn: asyncpg.Connection,
    body: dict,
    background_tasks: BackgroundTasks,
) -> dict:
    """
    Processes the raw Daraja webhook callback.

    THE IDEMPOTENCY AND RELIABILITY PIPELINE:
      1. Parse Safaricom's body to retrieve CheckoutRequestID and ResultCode.
      2. Query payments table by `mpesa_checkout_id` to find the record.
         - If payment is not found: return 200 OK immediately (ignore old/stale requests).
      3. Check status: is it "pending"?
         - If it is already "confirmed" or "failed", return 200 OK immediately.
           This handles Daraja webhook retry loops (in case they retry after we've finished).
      4. If ResultCode == 0 (Payment Successful):
         - Extract transaction details (Amount, MpesaReceiptNumber, PhoneNumber) from CallbackMetadata.
         - Start a database TRANSACTION:
           - Try to UPDATE payment with status="confirmed", and set the UNIQUE `mpesa_receipt_number`.
           - If another concurrent thread is processing the same receipt number, the database
             UNIQUE constraint will trigger an asyncpg UniqueViolationError.
           - We catch the UniqueViolationError, ROLLBACK, and return 200 OK (idempotent success).
         - If the UPDATE succeeds, we append the voucher generation background task:
           - `generate_voucher_task(payment_id)`
           - The HTTP response is returned to Safaricom IMMEDIATELY, and the voucher is provisioned.
      5. If ResultCode != 0 (Payment Failed / Cancelled):
         - Update payment status to "failed" and save the failure reason.

    Why this function ALWAYS returns {"ResultCode": 0, "ResultDesc": "Accepted"}:
      If our server returns a 4xx/5xx or a generic validation failure, Safaricom's servers
      will repeatedly retry the webhook, exhausting local server resources and clogging the
      transaction queue. To acknowledge receipt and terminate the retry loop, we must return
      a 200 OK with the exact schema Safaricom expects, regardless of whether the transaction
      was successful or rejected.
    """
    logger.info(f"Webhooks: received Safaricom Daraja webhook body: {body}")

    # ── 1. Parse body and extract CheckoutRequestID ───────────────────────────
    stk_callback = body.get("Body", {}).get("stkCallback", {})
    checkout_id = stk_callback.get("CheckoutRequestID")
    result_code = stk_callback.get("ResultCode")
    result_desc = stk_callback.get("ResultDesc", "No description provided.")

    if not checkout_id:
        logger.error("Webhooks: received callback missing CheckoutRequestID. Rejecting processing.")
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    # ── 2. Retrieve the corresponding payment ─────────────────────────────────
    query = "SELECT id, status FROM payments WHERE mpesa_checkout_id = $1"
    payment = await conn.fetchrow(query, checkout_id)

    if not payment:
        logger.warning(f"Webhooks: no payment record found matching CheckoutRequestID '{checkout_id}'. Skipping.")
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    payment_id = payment["id"]
    current_status = payment["status"]

    # ── 3. Check if already processed ─────────────────────────────────────────
    if current_status != "pending":
        logger.info(
            f"Webhooks: payment {payment_id} already processed with status '{current_status}'. "
            f"CheckoutRequestID '{checkout_id}' is idempotent. Skipping."
        )
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    # ── 4. Handle Successful payment ──────────────────────────────────────────
    if result_code == 0:
        # Extract metadata items
        metadata_items = stk_callback.get("CallbackMetadata", {}).get("Item", [])
        metadata = {item.get("Name"): item.get("Value") for item in metadata_items}

        receipt_number = metadata.get("MpesaReceiptNumber")
        phone_number = metadata.get("PhoneNumber")

        if not receipt_number:
            logger.error(f"Webhooks: checkout '{checkout_id}' marked success but receipt number is missing.")
            return {"ResultCode": 0, "ResultDesc": "Accepted"}

        logger.info(
            f"Webhooks: payment {payment_id} confirmed. "
            f"Receipt={receipt_number}, Phone={phone_number}, Amount={metadata.get('Amount')}"
        )

        # Start a database transaction to update the status and record the receipt.
        # This protects against race conditions where the webhook is delivered twice in rapid succession.
        try:
            async with conn.transaction():
                update_query = """
                    UPDATE payments
                    SET status = 'confirmed',
                        mpesa_receipt_number = $1,
                        updated_at = NOW()
                    WHERE id = $2
                """
                await conn.execute(update_query, receipt_number, payment_id)

        except asyncpg.exceptions.UniqueViolationError:
            # The receipt number already exists in the payments table.
            # This confirms a duplicate webhook hit, which we absorb gracefully.
            logger.warning(
                f"Webhooks: UniqueViolation caught for receipt '{receipt_number}' (payment {payment_id}). "
                f"Idempotency guard successfully absorbed duplicate request."
            )
            return {"ResultCode": 0, "ResultDesc": "Accepted"}

        # Register the voucher generation task to run asynchronously AFTER the HTTP response is sent.
        # This is critical for returning 200 OK under the 200ms window.
        background_tasks.add_task(generate_voucher_task, str(payment_id))
        logger.info(f"Webhooks: voucher generation task scheduled for payment {payment_id}")

    # ── 5. Handle Failed / Cancelled payment ──────────────────────────────────
    else:
        logger.warning(
            f"Webhooks: STK Push failed for payment {payment_id}. "
            f"ResultCode={result_code}, Reason={result_desc}"
        )
        update_query = """
            UPDATE payments
            SET status = 'failed',
                failure_reason = $1,
                updated_at = NOW()
            WHERE id = $2
        """
        await conn.execute(update_query, result_desc, payment_id)

    return {"ResultCode": 0, "ResultDesc": "Accepted"}
