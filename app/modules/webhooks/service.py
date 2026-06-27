"""
app/modules/webhooks/service.py
================================
Service layer handling Safaricom Daraja STK Push callback webhooks.

MULTI-TENANCY NOTE (T2):
  The Daraja webhook is public — Safaricom's servers call it with no JWT.
  Tenant identification comes from the mpesa_checkout_id lookup: every payment
  row is created with tenant_id at STK initiation time. ALL downstream
  operations (payment update, voucher enqueue, audit) use payment.tenant_id.
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

    Tenant flow (closes T2):
      1. Look up payment by mpesa_checkout_id (globally unique from Safaricom).
      2. Read payment.tenant_id from the matched row.
      3. All UPDATEs include AND tenant_id = payment.tenant_id.
      4. Voucher enqueue passes payment.tenant_id explicitly.
    """
    logger.info("received Daraja callback", body=body)

    stk_callback = body.get("Body", {}).get("stkCallback", {})
    checkout_id = stk_callback.get("CheckoutRequestID")
    result_code = stk_callback.get("ResultCode")
    result_desc = stk_callback.get("ResultDesc", "No description provided.")

    if not checkout_id:
        logger.error("callback missing CheckoutRequestID")
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    payment = await conn.fetchrow(
        "SELECT id, status, tenant_id FROM payments WHERE mpesa_checkout_id = $1",
        checkout_id,
    )
    is_platform_payment = False

    if not payment:
        payment = await conn.fetchrow(
            "SELECT id, status, tenant_id FROM platform_payments WHERE mpesa_checkout_id = $1",
            checkout_id,
        )
        if payment:
            is_platform_payment = True
        else:
            logger.warning("no payment found for CheckoutRequestID", checkout_id=checkout_id)
            return {"ResultCode": 0, "ResultDesc": "Accepted"}

    payment_id = payment["id"]
    tenant_id = payment["tenant_id"]
    current_status = payment["status"]

    if current_status != "pending":
        logger.info(
            "payment already processed, skipping",
            payment_id=str(payment_id),
            current_status=current_status,
            tenant_id=str(tenant_id),
        )
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    if result_code == 0:
        metadata_items = stk_callback.get("CallbackMetadata", {}).get("Item", [])
        metadata = {item.get("Name"): item.get("Value") for item in metadata_items}

        receipt_number = metadata.get("MpesaReceiptNumber")
        phone_number = metadata.get("PhoneNumber")

        if not receipt_number:
            logger.error("checkout success but no receipt number", checkout_id=checkout_id)
            return {"ResultCode": 0, "ResultDesc": "Accepted"}

        logger.info(
            "payment confirmed",
            payment_id=str(payment_id),
            tenant_id=str(tenant_id),
            receipt_number=receipt_number,
            phone_number=phone_number,
            amount=metadata.get("Amount"),
        )

        try:
            async with conn.transaction():
                if is_platform_payment:
                    await conn.execute(
                        """
                        UPDATE platform_payments
                        SET status = 'confirmed',
                            mpesa_receipt_number = $1,
                            updated_at = NOW()
                        WHERE id = $2
                          AND tenant_id = $3
                        """,
                        receipt_number,
                        payment_id,
                        tenant_id,
                    )
                    await conn.execute(
                        """
                        UPDATE tenants
                        SET next_billing_date = next_billing_date + INTERVAL '1 month',
                            status = 'active',
                            updated_at = NOW()
                        WHERE id = $1
                        """,
                        tenant_id,
                    )
                    logger.info(
                        "platform fee confirmed, tenant reinstated/extended",
                        tenant_id=str(tenant_id),
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE payments
                        SET status = 'confirmed',
                            mpesa_receipt_number = $1,
                            updated_at = NOW()
                        WHERE id = $2
                          AND tenant_id = $3
                        """,
                        receipt_number,
                        payment_id,
                        tenant_id,
                    )

        except asyncpg.exceptions.UniqueViolationError:
            logger.warning(
                "UniqueViolation for receipt, duplicate webhook absorbed",
                receipt_number=receipt_number,
                payment_id=str(payment_id),
                tenant_id=str(tenant_id),
            )
            return {"ResultCode": 0, "ResultDesc": "Accepted"}

        if not is_platform_payment:
            redis = get_redis_pool()
            request_id = get_contextvars().get("request_id")
            await redis.enqueue_job(
                "generate_voucher_task",
                str(payment_id),
                str(tenant_id),
                _request_id=request_id,
            )
            logger.info(
                "voucher generation job enqueued to Redis",
                payment_id=str(payment_id),
                tenant_id=str(tenant_id),
            )

    else:
        logger.warning(
            "STK push failed",
            payment_id=str(payment_id),
            tenant_id=str(tenant_id),
            result_code=result_code,
            reason=result_desc,
        )
        if is_platform_payment:
            await conn.execute(
                """
                UPDATE platform_payments
                SET status = 'failed',
                    failure_reason = $1,
                    updated_at = NOW()
                WHERE id = $2
                  AND tenant_id = $3
                """,
                result_desc,
                payment_id,
                tenant_id,
            )
        else:
            await conn.execute(
                """
                UPDATE payments
                SET status = 'failed',
                    failure_reason = $1,
                    updated_at = NOW()
                WHERE id = $2
                  AND tenant_id = $3
                """,
                result_desc,
                payment_id,
                tenant_id,
            )

    return {"ResultCode": 0, "ResultDesc": "Accepted"}


async def process_daraja_c2b_webhook(
    conn: asyncpg.Connection,
    body: dict,
) -> dict:
    """
    Processes the Safaricom Daraja C2B webhook (Validation and Confirmation).
    Reseller lookup returns tenant_id; wallet topup is scoped to that tenant.
    """
    logger.info("received Daraja C2B payload", body=body)

    trans_type = body.get("TransactionType")
    bill_ref = body.get("BillRefNumber")
    trans_id = body.get("TransID")
    trans_amount = body.get("TransAmount")

    if not bill_ref:
        logger.warning("C2B webhook missing BillRefNumber")
        return {"ResultCode": 1, "ResultDesc": "Missing BillRefNumber"}

    bill_ref = bill_ref.strip().upper()

    reseller = await conn.fetchrow(
        "SELECT id, tenant_id FROM users WHERE wallet_reference = $1 AND role = 'reseller'",
        bill_ref,
    )

    if not reseller:
        logger.warning("C2B validation failed: no reseller found", bill_ref=bill_ref)
        return {"ResultCode": 1, "ResultDesc": "Invalid wallet reference"}

    if trans_type == "Pay Bill Validation":
        logger.info("C2B validation succeeded", bill_ref=bill_ref)
        return {"ResultCode": 0, "ResultDesc": "Service completed successfully"}

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
        logger.info(
            "successfully topped up reseller",
            reseller_id=str(reseller_id),
            tenant_id=str(tenant_id),
            amount=str(amount),
            reference=trans_id,
        )
    except asyncpg.exceptions.UniqueViolationError:
        logger.warning("C2B duplicate transaction detected", trans_id=trans_id)
    except Exception as e:
        logger.error(
            "failed to process C2B confirmation",
            trans_id=trans_id,
            tenant_id=str(tenant_id),
            error=str(e),
            exc_info=True,
        )
        return {"ResultCode": 0, "ResultDesc": "Service completed successfully"}

    return {"ResultCode": 0, "ResultDesc": "Service completed successfully"}
