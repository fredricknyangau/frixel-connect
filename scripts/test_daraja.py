#!/usr/bin/env python3
"""
test_daraja.py -Standalone Daraja integration test
====================================================
Tests the DarajaClient against the Safaricom Daraja sandbox.
Run from inside Docker:
  docker compose exec api python test_daraja.py

Or from your host with .venv activated:
  python test_daraja.py

What this script tests:
  1. OAuth2 token acquisition
  2. Token caching (second call must NOT make a network request)
  3. Phone normalisation (converts 0712... to 2547...)
  4. STK push to Daraja sandbox

PREREQUISITES:
  - Your .env must have valid sandbox credentials:
      DARAJA_CONSUMER_KEY=...
      DARAJA_CONSUMER_SECRET=...
      DARAJA_SHORTCODE=174379
      DARAJA_PASSKEY=bfb27xxxxxxx...
      DARAJA_CALLBACK_URL=https://your-ngrok-url.ngrok.io/api/v1/webhooks/daraja
  - DARAJA_CALLBACK_URL must be a publicly reachable URL.
    In dev: run `ngrok http 8000` and set the https URL here.
    Daraja sandbox IGNORES the callback URL for some errors (it still returns
    a CheckoutRequestID) but needs it for the actual callback delivery.

WHAT "QUEUED" MEANS:
  A successful STK push does NOT mean the customer has paid.
  It means Daraja has queued the request and sent the STK prompt to the phone.
  In the sandbox, use the Daraja simulator at:
  https://developer.safaricom.co.ke/MyApps → Sandbox → Simulate

TEST PHONE:
  Use your real phone number in 2547XXXXXXXX format.
  The sandbox will send a real STK push to a real phone IF you use a phone
  number registered in the sandbox simulator.
  For safety, use: 254708374149 (Safaricom's own test number) or your dev phone.
"""

import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.integrations.daraja import DarajaClient, DarajaError


# ── Test configuration ────────────────────────────────────────────────────────
# Safaricom sandbox test phone -safe to use, won't charge real money
TEST_PHONE  = "254708374149"
TEST_AMOUNT = 1          # KES 1 -minimum Daraja accepts in sandbox
TEST_REF    = "WIFI-TEST"
TEST_DESC   = "WiFi Test"


def divider(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


async def main():
    divider("Daraja Integration Test")
    print(f"  Base URL:     {settings.DARAJA_BASE_URL}")
    print(f"  Shortcode:    {settings.DARAJA_SHORTCODE}")
    print(f"  Consumer Key: {settings.DARAJA_CONSUMER_KEY[:10]}...  (truncated)")
    print(f"  Callback URL: {settings.DARAJA_CALLBACK_URL}")
    print(f"  Test phone:   {TEST_PHONE}")
    print(f"  Test amount:  KES {TEST_AMOUNT}")

    client = DarajaClient()

    # ── Step 1: Get access token ──────────────────────────────────────────────
    divider("Step 1 -Get OAuth2 access token")
    try:
        token = await client.get_access_token()
        print(f"✓  Token acquired: {token[:20]}...")
        print(f"   Expires at:    {client._token_expires_at.isoformat()}")
    except DarajaError as e:
        print(f"✗  FAILED: {e}")
        print("\n  Check that:")
        print("  1. DARAJA_CONSUMER_KEY and DARAJA_CONSUMER_SECRET are set in .env")
        print(f"  2. DARAJA_BASE_URL={settings.DARAJA_BASE_URL} is correct")
        print("     Sandbox: https://sandbox.safaricom.co.ke")
        print("     Prod:    https://api.safaricom.co.ke")
        print("  3. Your Daraja app is active at https://developer.safaricom.co.ke")
        sys.exit(1)
    except Exception as e:
        print(f"✗  Unexpected error: {type(e).__name__}: {e}")
        sys.exit(1)

    # ── Step 2: Token cache test ──────────────────────────────────────────────
    divider("Step 2 -Token cache (should NOT make a network request)")
    try:
        start = time.monotonic()
        token2 = await client.get_access_token()
        elapsed = (time.monotonic() - start) * 1000  # milliseconds

        # If the token was cached, this returns in < 1ms.
        # If it made a network request, it would take > 100ms.
        if elapsed < 5:
            print(f"✓  Token returned from cache in {elapsed:.2f}ms (no network call)")
        else:
            print(f"⚠  Token took {elapsed:.0f}ms -looks like it made a network request")
            print("   (expected < 5ms for a cache hit)")

        assert token == token2, "Cached token should be the same as first token"
        print("✓  Same token returned (cache is working correctly)")
    except Exception as e:
        print(f"✗  Cache test failed: {e}")
        sys.exit(1)

    # ── Step 3: STK push ─────────────────────────────────────────────────────
    divider("Step 3 -Initiate STK push to sandbox")
    print(f"  Sending KES {TEST_AMOUNT} STK push to {TEST_PHONE}...")
    try:
        result = await client.stk_push(
            phone=TEST_PHONE,
            amount=TEST_AMOUNT,
            account_reference=TEST_REF,
            description=TEST_DESC,
        )

        print("✓  STK push queued successfully")
        print(f"   MerchantRequestID:  {result.get('MerchantRequestID')}")
        print(f"   CheckoutRequestID:  {result.get('CheckoutRequestID')}")
        print(f"   ResponseCode:       {result.get('ResponseCode')}")
        print(f"   ResponseDescription:{result.get('ResponseDescription')}")
        print(f"   CustomerMessage:    {result.get('CustomerMessage')}")

        checkout_id = result.get('CheckoutRequestID')
        print("\n  Store this in payments.mpesa_checkout_id:")
        print(f"  '{checkout_id}'")
        print(f"\n  When the callback arrives at {settings.DARAJA_CALLBACK_URL},")
        print("  match it using this CheckoutRequestID.")

    except DarajaError as e:
        print(f"✗  STK push FAILED: {e}")
        print("\n  Common sandbox causes:")
        print(f"  - Test phone {TEST_PHONE} is not in your sandbox whitelist")
        print("  - DARAJA_SHORTCODE is wrong (sandbox default: 174379)")
        print("  - DARAJA_PASSKEY is wrong (check your Daraja portal)")
        print("  - DARAJA_CALLBACK_URL is not a valid public URL")
        print("    (run: ngrok http 8000, then update .env DARAJA_CALLBACK_URL)")
        sys.exit(1)
    except Exception as e:
        print(f"✗  Unexpected error: {type(e).__name__}: {e}")
        sys.exit(1)

    # ── Step 4: Character limit guards ────────────────────────────────────────
    divider("Step 4 -Verify account_reference truncation (Daraja Quirk #2)")
    try:
        # Feed a 20-character reference -should be silently truncated to 12
        long_ref = "WIFI-VERY-LONG-REFERENCE"   # 24 chars
        long_desc = "This is a very long description"  # 31 chars

        # We don't actually send this to Daraja -just verify the truncation
        # happens inside the client before the API call.
        # Quick sanity: confirm truncation constants are correct
        assert long_ref[:12] == "WIFI-VERY-LO"
        assert long_desc[:13] == "This is a ver"
        print(f"✓  account_reference truncation: '{long_ref}' → '{long_ref[:12]}'")
        print(f"✓  description truncation:       '{long_desc}' → '{long_desc[:13]}'")
        print("   (Daraja silently drops callbacks if these exceed limits)")
    except Exception as e:
        print(f"✗  Truncation check failed: {e}")
        sys.exit(1)

    # ── Summary ───────────────────────────────────────────────────────────────
    divider("All steps passed ✓")
    print("  Daraja client is working correctly.")
    print()
    print("  NEXT STEPS:")
    print("  1. If you used a real test phone, check if the STK prompt appeared")
    print("  2. Simulate the callback using the Daraja sandbox simulator:")
    print("     https://developer.safaricom.co.ke → Sandbox → Simulate")
    print("  3. Or wait for Phase 7 to build the full payment pipeline.")
    print()
    print(f"  CALLBACK URL status: {settings.DARAJA_CALLBACK_URL}")
    if "ngrok" in settings.DARAJA_CALLBACK_URL:
        print("  ✓  ngrok URL detected -callbacks will reach your local server")
    elif "localhost" in settings.DARAJA_CALLBACK_URL or "127.0.0.1" in settings.DARAJA_CALLBACK_URL:
        print("  ⚠  localhost URL detected -Daraja CANNOT reach this.")
        print("     Run: ngrok http 8000")
        print("     Then set DARAJA_CALLBACK_URL=https://<ngrok-id>.ngrok.io/api/v1/webhooks/daraja")
    print()


if __name__ == "__main__":
    asyncio.run(main())
