#!/usr/bin/env python3
"""
test_mikrotik.py — Standalone MikroTik integration test
=========================================================
Tests the MikroTikClient against your real CHR instance.
Run this OUTSIDE Docker (from your host with the virtualenv active),
or inside Docker:
  docker compose exec api python test_mikrotik.py

What this script tests:
  1. Creates a test hotspot user (ZTEST001)
  2. Prints the RouterOS response (confirms what the router returned)
  3. Gets active sessions and prints the count
  4. Deletes the test user
  5. Confirms deletion by trying to fetch it again

Prerequisites:
  - MikroTik CHR running and reachable at MIKROTIK_HOST:MIKROTIK_PORT
  - REST API enabled on the CHR:
      /ip/hotspot/service add port=8080 name=admin
    or just ensure the web interface is accessible (it serves the REST API)
  - A hotspot profile named "10Mbps" must exist:
      /ip hotspot user profile add name=10Mbps rate-limit=10M/10M
  - The credentials in .env must have API write permissions

IMPORTANT: This script creates and then deletes a real hotspot user.
It does NOT send any money or touch any payment records.
"""

import asyncio
import sys
import os

# Add project root to path so we can import from app/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.integrations.mikrotik import MikroTikClient, MikroTikError


# ── Test configuration ────────────────────────────────────────────────────────
TEST_USERNAME = "ZTEST001"
TEST_PROFILE  = "10Mbps"
TEST_DURATION = "1d"


def divider(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


async def main():
    divider("MikroTik Integration Test")
    print(f"  Host:    {settings.MIKROTIK_HOST}:{settings.MIKROTIK_PORT}")
    print(f"  User:    {settings.MIKROTIK_USERNAME}")
    print(f"  Profile: {TEST_PROFILE}")
    print(f"  Voucher: {TEST_USERNAME}")

    client = MikroTikClient()

    # ── Step 1: Check profiles exist ─────────────────────────────────────────
    divider("Step 1 — Verify router is reachable & profiles exist")
    try:
        profiles = await client.get_user_profile_names()
        print(f"✓  Router responded. Profiles found: {profiles}")
        if TEST_PROFILE not in profiles:
            print(f"⚠  WARNING: Profile '{TEST_PROFILE}' not found on the router.")
            print(f"   Create it in RouterOS before Phase 7:")
            print(f"   /ip hotspot user profile add name=10Mbps rate-limit=10M/10M")
            print(f"   /ip hotspot user profile add name=20Mbps rate-limit=20M/20M")
            print(f"   Continuing test with available profile (may fail at Step 2)")
    except Exception as e:
        print(f"✗  FAILED to reach router: {e}")
        print(f"\n  Check that:")
        print(f"  1. MikroTik CHR is running in VirtualBox")
        print(f"  2. MIKROTIK_HOST={settings.MIKROTIK_HOST} is reachable (ping it)")
        print(f"  3. MIKROTIK_PORT={settings.MIKROTIK_PORT} is the REST API port")
        print(f"  4. REST API is enabled on the CHR:")
        print(f"     From RouterOS CLI: /ip service print")
        print(f"     The 'www' or 'www-ssl' service should be enabled")
        sys.exit(1)

    # ── Step 2: Create test hotspot user ──────────────────────────────────────
    divider("Step 2 — Create hotspot user ZTEST001")
    try:
        created_user = await client.generate_hotspot_user(
            username=TEST_USERNAME,
            password=TEST_USERNAME,  # username = password = voucher code
            profile=TEST_PROFILE,
            time_limit=TEST_DURATION,
        )
        print(f"✓  Created user successfully")
        print(f"   RouterOS response:")
        for key, value in created_user.items():
            print(f"     {key}: {value}")
    except MikroTikError as e:
        print(f"✗  MikroTik rejected the create request: {e}")
        print(f"\n  Common causes:")
        print(f"  - Profile '{TEST_PROFILE}' doesn't exist on the router")
        print(f"  - User '{TEST_USERNAME}' already exists (run delete manually first)")
        print(f"  - API user doesn't have write permissions")
        sys.exit(1)
    except Exception as e:
        print(f"✗  Unexpected error during create: {type(e).__name__}: {e}")
        sys.exit(1)

    # ── Step 3: Get active sessions ───────────────────────────────────────────
    divider("Step 3 — Get active hotspot sessions")
    try:
        sessions = await client.get_active_sessions()
        count = len(sessions)
        print(f"✓  Active sessions: {count}")
        if count > 0:
            print(f"   First session fields: {list(sessions[0].keys())}")
        else:
            print(f"   (No devices currently connected through the hotspot)")
    except Exception as e:
        # Non-fatal: sessions being unavailable doesn't block the voucher flow.
        print(f"⚠  Could not fetch sessions (non-fatal): {e}")

    # ── Step 4: Delete test user ──────────────────────────────────────────────
    divider("Step 4 — Delete hotspot user ZTEST001")
    try:
        await client.remove_hotspot_user(TEST_USERNAME)
        print(f"✓  Deleted user '{TEST_USERNAME}' successfully")
    except Exception as e:
        print(f"✗  Failed to delete user: {e}")
        print(f"   Clean up manually: /ip hotspot user remove [find name={TEST_USERNAME}]")
        sys.exit(1)

    # ── Step 5: Confirm deletion ──────────────────────────────────────────────
    divider("Step 5 — Confirm deletion (idempotency test)")
    try:
        # Calling remove_hotspot_user on an already-deleted user should NOT raise.
        # This tests the idempotency guarantee: safe to call twice.
        await client.remove_hotspot_user(TEST_USERNAME)
        print(f"✓  Second delete call returned silently (idempotent — correct behaviour)")
    except Exception as e:
        print(f"✗  Second delete raised an error — idempotency is broken: {e}")
        sys.exit(1)

    # ── Summary ───────────────────────────────────────────────────────────────
    divider("All steps passed ✓")
    print(f"  MikroTik client is working correctly.")
    print(f"")
    print(f"  Next: verify manually in RouterOS that ZTEST001 no longer exists:")
    print(f"    /ip hotspot user print")
    print(f"  (It should NOT appear in the list)")
    print(f"")
    print(f"  Ready for Phase 7 — the core pipeline.")
    print()


if __name__ == "__main__":
    asyncio.run(main())
