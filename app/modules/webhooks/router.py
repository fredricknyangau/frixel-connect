"""
app/modules/webhooks/router.py
================================
Stub router for the webhooks module.

CRITICAL: This route is intentionally PUBLIC (no authentication).
Safaricom's Daraja servers POST to this endpoint — they don't carry a JWT.
Security is handled by:
  1. Signature verification (HMAC) in Phase 7 — the body is signed with
     your passkey. A forged webhook won't have a valid signature.
  2. Idempotency (UNIQUE constraint on mpesa_receipt_number) — even if
     someone sends a fake webhook, it can't create a duplicate confirmed
     payment if the receipt number doesn't match a real M-Pesa transaction.

This is why the webhook endpoint ALWAYS returns 200 with
{"ResultCode": 0, "ResultDesc": "Accepted"} — even on errors.
If we return a non-200, Daraja will RETRY the webhook indefinitely.
Retries with invalid data are harmless (idempotency handles them), but
retries that timeout eat into Daraja's retry budget and can cause
legitimate webhooks to be dropped. Always return 200. Always.
"""

from fastapi import APIRouter

router = APIRouter()


@router.post(
    "/daraja",
    summary="Daraja M-Pesa callback — NO authentication required",
    # No Depends(require_role(...)) — intentionally public
)
async def daraja_webhook():
    # Phase 7 will replace this with the full idempotency pipeline.
    # The response shape is what Daraja expects even from a stub.
    return {"ResultCode": 0, "ResultDesc": "Accepted"}
