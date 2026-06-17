"""
app/modules/webhooks/service.py
================================
Service layer handling Safaricom Daraja STK Push callback webhooks.

MULTI-TENANCY NOTE:
  The Daraja webhook is public — Safaricom's servers call it with no JWT.
  We cannot know which tenant a webhook belongs to from the HTTP headers.
  Instead, we look up the payment by mpesa_checkout_id (which we store
  when the STK push is initiated). That payment row carries tenant_id,
  so the webhook implicitly operates in the correct tenant context.
"""

import logging
import asyncpg

from app.core.redis import get_redis_pool

logger = logging.getLogger(__name__)


async def process_daraja_webhook(
    conn: asyncpg.Connection,
    body: dict,
) -> dict:
    """
    Processes the raw Daraja webhook callback.

    THE IDEMPOTENCY AND RELIABILITY PIPELINE:
      1. Parse body → CheckoutRequestID + ResultCode.
      2. Look up payment by mpesa_checkout_id. Payment row carries tenant_id.
      3. If already processed (confirmed/failed), return 200 immediately.
      4. ResultCode == 0 (success):
         - Extract MpesaReceiptNumber from CallbackMetadata.
         - UPDATE payments SET status='confirmed', mpesa_receipt_number=...
           inside a transaction. UNIQUE constraint on mpesa_receipt_number
           absorbs duplicate webhook retries at the DB layer.
         - Enqueue generate_voucher_task in Redis/arq.
      5. ResultCode != 0 (failure): mark payment as failed.
      6. Always return {"ResultCode": 0, "ResultDesc": "Accepted"} so
         Safaricom stops retrying.
    """
    logger.info(f"Webhooks: received Daraja callback: {body}")

    stk_callback = body.get("Body", {}).get("stkCallback", {})
    checkout_id  = stk_callback.get("CheckoutRequestID")
    result_code  = stk_callback.get("ResultCode")
    result_desc  = stk_callback.get("ResultDesc", "No description provided.")

    if not checkout_id:
        logger.error("Webhooks: callback missing CheckoutRequestID.")
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    # Look up payment by checkout_id (no tenant filter — we find the record
    # globally and use its embedded tenant_id for subsequent operations)
    payment = await conn.fetchrow(
        "SELECT id, status, tenant_id FROM payments WHERE mpesa_checkout_id = $1",
        checkout_id,
    )

    if not payment:
        logger.warning(f"Webhooks: no payment found for CheckoutRequestID '{checkout_id}'.")
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    payment_id    = payment["id"]
    current_status = payment["status"]

    # Already processed — idempotent skip
    if current_status != "pending":
        logger.info(
            f"Webhooks: payment {payment_id} already has status '{current_status}'. "
            f"Skipping (idempotent)."
        )
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    # ── Successful payment ────────────────────────────────────────────────────
    if result_code == 0:
        metadata_items = stk_callback.get("CallbackMetadata", {}).get("Item", [])
        metadata       = {item.get("Name"): item.get("Value") for item in metadata_items}

        receipt_number = metadata.get("MpesaReceiptNumber")
        phone_number   = metadata.get("PhoneNumber")

        if not receipt_number:
            logger.error(f"Webhooks: checkout '{checkout_id}' success but no receipt number.")
            return {"ResultCode": 0, "ResultDesc": "Accepted"}

        logger.info(
            f"Webhooks: payment {payment_id} confirmed. "
            f"Receipt={receipt_number}, Phone={phone_number}, Amount={metadata.get('Amount')}"
        )

        try:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE payments
                    SET status = 'confirmed',
                        mpesa_receipt_number = $1,
                        updated_at = NOW()
                    WHERE id = $2
                    """,
                    receipt_number,
                    payment_id,
                )

        except asyncpg.exceptions.UniqueViolationError:
            # Duplicate webhook — receipt number already recorded.
            logger.warning(
                f"Webhooks: UniqueViolation for receipt '{receipt_number}' "
                f"(payment {payment_id}). Duplicate webhook absorbed."
            )
            return {"ResultCode": 0, "ResultDesc": "Accepted"}

        # Enqueue voucher generation task to the durable arq/Redis queue
        redis = get_redis_pool()
        await redis.enqueue_job("generate_voucher_task", str(payment_id))
        logger.info(f"Webhooks: voucher generation job enqueued to Redis for payment {payment_id}")

    # ── Failed / cancelled payment ────────────────────────────────────────────
    else:
        logger.warning(
            f"Webhooks: STK push failed for payment {payment_id}. "
            f"ResultCode={result_code}, Reason={result_desc}"
        )
        await conn.execute(
            """
            UPDATE payments
            SET status = 'failed',
                failure_reason = $1,
                updated_at = NOW()
            WHERE id = $2
            """,
            result_desc,
            payment_id,
        )

    return {"ResultCode": 0, "ResultDesc": "Accepted"}
