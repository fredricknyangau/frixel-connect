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

import structlog
import asyncpg
from structlog.contextvars import get_contextvars

from app.core.redis import get_redis_pool

logger = structlog.get_logger(__name__)


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
    logger.info("received Daraja callback", body=body)

    stk_callback = body.get("Body", {}).get("stkCallback", {})
    checkout_id  = stk_callback.get("CheckoutRequestID")
    result_code  = stk_callback.get("ResultCode")
    result_desc  = stk_callback.get("ResultDesc", "No description provided.")

    if not checkout_id:
        logger.error("callback missing CheckoutRequestID")
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    # Look up payment by checkout_id (no tenant filter — we find the record
    # globally and use its embedded tenant_id for subsequent operations)
    payment = await conn.fetchrow(
        "SELECT id, status, tenant_id FROM payments WHERE mpesa_checkout_id = $1",
        checkout_id,
    )

    if not payment:
        logger.warning("no payment found for CheckoutRequestID", checkout_id=checkout_id)
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    payment_id    = payment["id"]
    current_status = payment["status"]

    # Already processed — idempotent skip
    if current_status != "pending":
        logger.info(
            "payment already processed, skipping",
            payment_id=payment_id,
            current_status=current_status
        )
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    # ── Successful payment ────────────────────────────────────────────────────
    if result_code == 0:
        metadata_items = stk_callback.get("CallbackMetadata", {}).get("Item", [])
        metadata       = {item.get("Name"): item.get("Value") for item in metadata_items}

        receipt_number = metadata.get("MpesaReceiptNumber")
        phone_number   = metadata.get("PhoneNumber")

        if not receipt_number:
            logger.error("checkout success but no receipt number", checkout_id=checkout_id)
            return {"ResultCode": 0, "ResultDesc": "Accepted"}

        logger.info(
            "payment confirmed",
            payment_id=payment_id,
            receipt_number=receipt_number,
            phone_number=phone_number,
            amount=metadata.get('Amount')
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
                "UniqueViolation for receipt, duplicate webhook absorbed",
                receipt_number=receipt_number,
                payment_id=payment_id
            )
            return {"ResultCode": 0, "ResultDesc": "Accepted"}

        # Enqueue voucher generation task to the durable arq/Redis queue
        redis = get_redis_pool()
        request_id = get_contextvars().get("request_id")
        await redis.enqueue_job("generate_voucher_task", str(payment_id), _request_id=request_id)
        logger.info("voucher generation job enqueued to Redis", payment_id=payment_id)

    # ── Failed / cancelled payment ────────────────────────────────────────────
    else:
        logger.warning(
            "STK push failed",
            payment_id=payment_id,
            result_code=result_code,
            reason=result_desc
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


async def process_daraja_c2b_webhook(
    conn: asyncpg.Connection,
    body: dict,
) -> dict:
    """
    Processes the Safaricom Daraja C2B webhook (Validation and Confirmation).

    1. Validation: Checks if BillRefNumber matches a valid reseller. Returns
       ResultCode 0 to accept, 1 to reject.
    2. Confirmation: Topups the matched reseller's wallet, using TransID as
       the unique reference for idempotency.
    """
    logger.info("received Daraja C2B payload", body=body)

    trans_type = body.get("TransactionType")
    bill_ref = body.get("BillRefNumber")
    trans_id = body.get("TransID")
    trans_amount = body.get("TransAmount")

    if not bill_ref:
        logger.warning("C2B webhook missing BillRefNumber")
        return {"ResultCode": 1, "ResultDesc": "Missing BillRefNumber"}

    # Clean the wallet reference (strip whitespaces, uppercase)
    bill_ref = bill_ref.strip().upper()

    # Look up reseller globally by wallet reference
    reseller = await conn.fetchrow(
        "SELECT id, tenant_id FROM users WHERE wallet_reference = $1 AND role = 'reseller'",
        bill_ref,
    )

    if not reseller:
        logger.warning("C2B validation failed: no reseller found", bill_ref=bill_ref)
        return {"ResultCode": 1, "ResultDesc": "Invalid wallet reference"}

    # Handle Validation request
    if trans_type == "Pay Bill Validation":
        logger.info("C2B validation succeeded", bill_ref=bill_ref)
        return {"ResultCode": 0, "ResultDesc": "Service completed successfully"}

    # Handle Confirmation request
    if not trans_id or not trans_amount:
        logger.warning("C2B confirmation payload missing TransID or TransAmount")
        return {"ResultCode": 0, "ResultDesc": "Service completed successfully"}

    from decimal import Decimal
    from app.modules.wallets.service import topup_wallet

    amount = Decimal(str(trans_amount))
    reseller_id = reseller["id"]
    tenant_id = reseller["tenant_id"]

    try:
        async with conn.transaction():
            await topup_wallet(conn, tenant_id, reseller_id, amount, trans_id)
        logger.info("successfully topped up reseller", reseller_id=reseller_id, amount=str(amount), reference=trans_id)
    except asyncpg.exceptions.UniqueViolationError:
        # A duplicate webhook confirmation delivery — absorb idempotently
        logger.warning("C2B duplicate transaction detected", trans_id=trans_id)
    except Exception as e:
        logger.error("failed to process C2B confirmation", trans_id=trans_id, error=str(e), exc_info=True)
        # We still return ResultCode 0 to satisfy Safaricom's webhook acknowledgment
        return {"ResultCode": 0, "ResultDesc": "Service completed successfully"}

    return {"ResultCode": 0, "ResultDesc": "Service completed successfully"}

