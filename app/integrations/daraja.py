"""
app/integrations/daraja.py
===========================
HTTP client for Safaricom M-Pesa Daraja API (STK Push / Lipa Na M-Pesa Online).

HOW THE STK PUSH FLOW WORKS:
  1. Your backend calls Daraja's STK Push endpoint with the customer's phone,
     amount, and your callback URL.
  2. Daraja sends an STK Push notification to the customer's phone (a pop-up
     asking them to enter their M-Pesa PIN).
  3. If the customer enters the PIN → Daraja calls YOUR callback URL (webhook)
     with the result (success or failure).
  4. If the customer cancels or doesn't respond → Daraja calls the callback
     with a failure result code.

KEY CONCEPTS:
  - CheckoutRequestID: Daraja's handle for this specific STK push. You store
    it in payments.mpesa_checkout_id to match the incoming webhook callback.
  - MerchantRequestID: Daraja's internal tracking ID. You don't use this.
  - ResultCode: 0 = success, anything else = failure.
  - MpesaReceiptNumber: Only present when ResultCode=0. This is the M-Pesa
    transaction reference (like RCA1XXXXXXXX). Store it in the DB UNIQUE.

HOW THE ACCESS TOKEN WORKS:
  Daraja uses OAuth2 client credentials. To call any Daraja API:
    1. GET /oauth/v1/generate?grant_type=client_credentials
       with Authorization: Basic base64(key:secret)
    2. Get back {"access_token": "...", "expires_in": "3599"}
    3. Use that token as: Authorization: Bearer {token}
       on every subsequent API call.
  Tokens expire in ~1 hour. We cache the token and only refresh when it
  expires (or 60 seconds before, as a buffer).

WHY WE CACHE THE TOKEN:
  Rate limits: Safaricom limits token generation requests. Making a new
  request for every API call would exhaust your quota and add ~200ms of
  latency to every payment. Caching means token generation happens at most
  once per hour, and each API call only needs one round-trip to Daraja.
"""

import base64
import logging
from datetime import datetime, timezone, timedelta

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class DarajaError(Exception):
    """Raised when Daraja returns an error response or unexpected format."""
    pass


class DarajaClient:
    """
    Async client for the Safaricom M-Pesa Daraja API.

    Implements:
      - OAuth2 token management with caching and auto-refresh
      - STK Push (Lipa Na M-Pesa Online) initiation

    Usage:
        daraja = DarajaClient()
        result = await daraja.stk_push("254712345678", 50, "WIFI-TEST", "WiFi Test")
        checkout_id = result["CheckoutRequestID"]
    """

    def __init__(self) -> None:
        self.base_url = settings.DARAJA_BASE_URL  # sandbox or production

        # Token cache. Starts empty — will be populated on first API call.
        # We use instance variables (not class variables) so each instance
        # has its own cache. If you ever run multiple workers, each worker
        # gets its own token — that's fine, tokens are independent.
        self._token: str | None = None
        self._token_expires_at: datetime | None = None

        self._timeout = httpx.Timeout(30.0)  # Daraja can be slow under load

    async def get_access_token(self) -> str:
        """
        Returns a valid Daraja access token, fetching a new one if expired.

        WHY WE SUBTRACT 60 SECONDS FROM THE EXPIRY:
        Daraja gives us `expires_in` seconds. If we cache until exactly
        expires_in, there's a race condition: the token could expire between
        when we check it and when Daraja processes our request (network
        latency + Daraja clock drift). Subtracting 60 seconds means we
        refresh the token 1 minute before it officially expires — giving
        enough margin to avoid mid-request failures.

        Returns:
            A valid Bearer token string.

        Raises:
            DarajaError: If the token request fails.
        """
        now = datetime.now(timezone.utc)

        # Check if we have a cached token that's still valid (with 60s buffer).
        if self._token and self._token_expires_at and now < self._token_expires_at:
            return self._token

        # Token is missing or expired — fetch a new one.
        logger.info("Daraja: fetching new access token")

        # Basic Auth header: base64(consumer_key:consumer_secret)
        # This is standard HTTP Basic Auth as defined in RFC 7617.
        credentials = f"{settings.DARAJA_CONSUMER_KEY}:{settings.DARAJA_CONSUMER_SECRET}"
        encoded = base64.b64encode(credentials.encode()).decode()

        async with httpx.AsyncClient(base_url=self.base_url, timeout=self._timeout) as client:
            response = await client.get(
                "/oauth/v1/generate",
                params={"grant_type": "client_credentials"},
                headers={"Authorization": f"Basic {encoded}"},
            )

        if not response.is_success:
            raise DarajaError(
                f"Failed to get Daraja access token: {response.status_code} {response.text}"
            )

        data = response.json()
        token = data.get("access_token")
        expires_in = int(data.get("expires_in", 3600))

        if not token:
            raise DarajaError(f"Daraja token response missing access_token: {data}")

        # Cache the token with the expiry minus 60s buffer.
        self._token = token
        self._token_expires_at = now + timedelta(seconds=expires_in - 60)

        logger.info(f"Daraja: new token cached, expires in {expires_in - 60}s")
        return token

    async def stk_push(
        self,
        phone: str,
        amount: int,
        account_reference: str,
        description: str,
    ) -> dict:
        """
        Initiates an STK Push payment request to the customer's phone.

        Args:
            phone:             Customer phone in 2547XXXXXXXX format.
                               Must be normalised BEFORE calling this method.
                               The normalise_phone() utility in app/core/utils.py
                               handles 0712..., +2547..., 2547... inputs.
            amount:            Payment amount in KES. MUST be an integer.
                               QUIRK 1: Daraja technically accepts decimals but
                               some callbacks return validation errors for
                               non-integer amounts. Always cast to int:
                               int(package.price_kes) — never send 50.0.
            account_reference: Max 12 characters. Appears on the customer's
                               M-Pesa confirmation SMS as the account charged.
                               QUIRK 2: Daraja has a hard 12-char limit with
                               no error feedback — exceeding it causes the STK
                               push to appear to succeed (you get a
                               CheckoutRequestID back) but the callback NEVER
                               arrives. We truncate defensively.
                               Example: "WIFI-001234"
            description:       Max 13 characters. Appears in Daraja logs and
                               the customer's M-Pesa menu. Same silent-failure
                               risk as account_reference if exceeded.
                               Example: "WiFi Payment"

        Returns:
            The full Daraja response dict. Key fields:
              CheckoutRequestID — store in payments.mpesa_checkout_id
              MerchantRequestID — Daraja's internal ID, not needed by us
              ResponseCode      — "0" means the request was queued (NOT paid yet)
              ResponseDescription — human readable status
              CustomerMessage   — shown to customer by Daraja

        Raises:
            DarajaError: If Daraja rejects the request (bad credentials,
                phone validation failure, service unavailable).

        HOW THE TIMESTAMP+PASSWORD WORKS (non-obvious):
            Daraja requires a "Password" field in the STK push body. This is NOT
            your M-Pesa PIN or any stored password. It's a one-time proof that
            you know your Lipa Na M-Pesa passkey, generated as follows:

            1. timestamp = current time in "YYYYMMDDHHmmss" format (14 digits)
               e.g. "20260617141530" for 2026-06-17 14:15:30

            2. raw_string = shortcode + passkey + timestamp
               e.g. "174379bfb27............20260617141530"

            3. password = base64(raw_string)

            Why base64? Safaricom's documentation doesn't explain it — it's just
            how they designed the auth scheme. The timestamp is included so the
            password changes every second, making it a time-based one-time token.
            A replayed request with a stale timestamp will be rejected by Daraja.

            The passkey comes from your Daraja portal. For sandbox:
            DARAJA_PASSKEY=bfb27xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
            (it's in your .env, set during onboarding)
        """

        # ── QUIRK 2 DEFENCE: truncate to Daraja's hard limits ─────────────────
        # These limits are not documented in error messages — Daraja silently
        # drops the callback if you exceed them. We truncate here so the STK
        # push actually completes end-to-end.
        account_reference = account_reference[:12]
        description = description[:13]

        # ── Generate timestamp and password ────────────────────────────────────
        # Daraja requires the timestamp in "YYYYMMDDHHmmss" format.
        # We use UTC for consistency — Safaricom's servers are UTC+3 but their
        # API accepts UTC timestamps fine in the sandbox.
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

        # password = base64( shortcode + passkey + timestamp )
        raw = f"{settings.DARAJA_SHORTCODE}{settings.DARAJA_PASSKEY}{timestamp}"
        password = base64.b64encode(raw.encode()).decode()

        # ── QUIRK 1 DEFENCE: ensure integer amount ─────────────────────────────
        # The function signature already requires int, but we cast defensively
        # in case someone passes a Decimal or float.
        amount = int(amount)

        # ── Get a valid access token ───────────────────────────────────────────
        token = await self.get_access_token()

        # ── Fire the STK push ──────────────────────────────────────────────────
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self._timeout) as client:
            response = await client.post(
                "/mpesa/stkpush/v1/processrequest",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    # BusinessShortCode: your Lipa Na M-Pesa shortcode (or till number).
                    # In sandbox this is 174379.
                    "BusinessShortCode": settings.DARAJA_SHORTCODE,

                    # Password: the base64 token explained in the docstring above.
                    "Password": password,

                    # Timestamp: same value used to generate Password.
                    # Must match exactly — Daraja verifies the password against this.
                    "Timestamp": timestamp,

                    # TransactionType: "CustomerPayBillOnline" for paybill numbers,
                    # "CustomerBuyGoodsOnline" for till numbers. Use PayBill for ISPs.
                    "TransactionType": "CustomerPayBillOnline",

                    # Amount: integer KES only. No decimals. No cents.
                    "Amount": amount,

                    # PartyA: the customer's phone in 2547XXXXXXXX format.
                    "PartyA": phone,

                    # PartyB: your paybill number (same as BusinessShortCode
                    # for paybill; different for till number setups).
                    "PartyB": settings.DARAJA_SHORTCODE,

                    # PhoneNumber: where to send the STK push prompt.
                    # Same as PartyA for customer-initiated payments.
                    "PhoneNumber": phone,

                    # CallBackURL: Daraja will POST the result here.
                    # Must be publicly reachable (ngrok in dev, real URL in prod).
                    "CallBackURL": settings.DARAJA_CALLBACK_URL,

                    # AccountReference: appears on customer's M-Pesa SMS. Max 12 chars.
                    "AccountReference": account_reference,

                    # TransactionDesc: appears in Daraja logs. Max 13 chars.
                    "TransactionDesc": description,
                },
            )

        if not response.is_success:
            raise DarajaError(
                f"Daraja STK push failed: {response.status_code} {response.text}"
            )

        result = response.json()

        # Daraja returns ResponseCode "0" to mean "queued successfully" — NOT paid.
        # The actual payment result comes via the callback webhook.
        # Any other ResponseCode means Daraja couldn't even queue the request.
        if result.get("ResponseCode") != "0":
            raise DarajaError(
                f"Daraja STK push rejected: {result.get('ResponseDescription', result)}"
            )

        logger.info(
            f"Daraja: STK push queued for {phone} KES {amount} "
            f"CheckoutRequestID={result.get('CheckoutRequestID')}"
        )
        return result

    async def register_c2b_url(
        self,
        confirmation_url: str,
        validation_url: str,
    ) -> dict:
        """
        Registers Validation and Confirmation URLs for C2B payments on Safaricom Daraja.

        C2B is customer-initiated: the reseller pays via M-Pesa to the Paybill
        with their wallet reference as the account number. Safaricom sends
        validation and confirmation webhooks to check and complete the transaction.
        """
        token = await self.get_access_token()
        logger.info(f"Daraja: registering C2B URLs with Confirmation={confirmation_url}, Validation={validation_url}")

        async with httpx.AsyncClient(base_url=self.base_url, timeout=self._timeout) as client:
            response = await client.post(
                "/mpesa/c2b/v1/registerurl",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "ShortCode": settings.DARAJA_SHORTCODE,
                    "ResponseType": "Completed",
                    "ConfirmationURL": confirmation_url,
                    "ValidationURL": validation_url,
                },
            )

        if not response.is_success:
            raise DarajaError(
                f"Daraja C2B URL registration failed: {response.status_code} {response.text}"
            )

        result = response.json()
        logger.info(f"Daraja: C2B URL registration result: {result}")
        return result



# ── Module-level singleton ────────────────────────────────────────────────────
# Single instance shared across all requests. The token cache is on this instance,
# so token re-use works across concurrent requests without external state (Redis).
# In a multi-process setup (gunicorn with workers) each worker has its own
# instance and its own cache — that's fine, tokens are stateless bearer tokens.
daraja_client = DarajaClient()
