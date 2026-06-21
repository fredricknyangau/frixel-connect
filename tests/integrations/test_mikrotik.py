"""
tests/integrations/test_mikrotik.py
====================================
Integration tests for the MikroTik REST API client.
Runs only when the MikroTik CHR is active and reachable.
"""

import httpx
import pytest

from app.config import settings
from app.integrations.mikrotik import get_mikrotik_client, MikroTikError

# ── Reachability Check ────────────────────────────────────────────────────────
# Performs a quick synchronous ping to RouterOS to determine if the virtual router is booted.
# If unreachable, the integration tests are skipped dynamically instead of failing.
def is_chr_reachable() -> bool:
    try:
        base_url = f"http://{settings.MIKROTIK_HOST}:{settings.MIKROTIK_PORT}/rest"
        auth = (settings.MIKROTIK_USERNAME, settings.MIKROTIK_PASSWORD)
        # Check profiles list (which should always be readable)
        response = httpx.get(
            f"{base_url}/ip/hotspot/user/profile",
            auth=auth,
            timeout=2.0
        )
        return response.is_success
    except Exception:
        return False


# Skip all tests in this file if the MikroTik CHR is not reachable
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not is_chr_reachable(),
        reason="MikroTik CHR is not booted or reachable. Skipping integration tests."
    )
]


@pytest.mark.asyncio
async def test_create_and_delete_hotspot_user():
    """
    Integration test asserting that the client can create a hotspot user
    and subsequently delete them from RouterOS.
    """
    username = "ITEST001"
    # Ensure profile matches a standard seeded speed limit profile
    profile = "10Mbps"
    time_limit = "1d"

    async with get_mikrotik_client() as client:
        # Make sure user does not exist before starting test
        try:
            await client.remove_hotspot_user(username)
        except Exception:
            pass

        # 1. Create the hotspot user on the router
        created_user = await client.generate_hotspot_user(
            username=username,
            password=username,
            profile=profile,
            time_limit=time_limit
        )

        assert created_user[".id"] is not None
        assert created_user["name"] == username
        assert created_user["profile"] == profile
        assert created_user["limit-uptime"] == time_limit

        # 2. Revoke/delete the user and confirm
        await client.remove_hotspot_user(username)

        # 3. Idempotent check: calling delete again should return silently
        await client.remove_hotspot_user(username)


@pytest.mark.asyncio
async def test_get_active_sessions_returns_list():
    """
    Integration test asserting that the active session fetch succeeds
    and returns a structured list.
    """
    async with get_mikrotik_client() as client:
        sessions = await client.get_active_sessions()
        assert isinstance(sessions, list)
        if sessions:
            # Check common RouterOS properties
            session = sessions[0]
            assert "user" in session
            assert "address" in session

