import pytest
import asyncpg
from fastapi.testclient import TestClient

from tests.conftest import DEFAULT_TENANT_ID

@pytest.mark.asyncio
async def test_hotspot_free_trial_flow(client: TestClient, conn: asyncpg.Connection):
    """
    Verifies the Free Trial captive portal flow:
    1. A guest requests a trial. A confirmed payment of 1 KES and voucher PIN are provisioned.
    2. A second request with the same phone in 24 hours returns 409 Conflict.
    3. Confirms the RADIUS attributes are inserted for the trial voucher.
    """
    phone = "254711222333"
    mac = "AA:BB:CC:DD:EE:FF"
    
    # 1. Post to the public trial activation endpoint
    response = client.post(
        "/api/v1/hotspot/trial",
        json={
            "phone": phone,
            "tenant_id": DEFAULT_TENANT_ID,
            "mac_address": mac,
        }
    )
    
    assert response.status_code == 200, f"Error: {response.text}"
    data = response.json()
    assert "voucher_code" in data
    code = data["voucher_code"]
    assert code is not None
    
    # 2. Check the payments database table
    payment = await conn.fetchrow(
        "SELECT * FROM payments WHERE phone_number = $1 AND tenant_id = $2",
        phone,
        DEFAULT_TENANT_ID,
    )
    assert payment is not None
    assert payment["amount_kes"] == 1.00
    assert payment["status"] == "confirmed"
    assert payment["mpesa_receipt_number"].startswith("TRIAL-")

    # 3. Check the vouchers table
    voucher = await conn.fetchrow(
        "SELECT * FROM vouchers WHERE payment_id = $1",
        payment["id"],
    )
    assert voucher is not None
    assert voucher["code"] == code

    # 4. Check FreeRADIUS tables for this voucher credentials
    radcheck_row = await conn.fetchrow(
        "SELECT username, attribute, value FROM radcheck WHERE username = $1",
        code,
    )
    assert radcheck_row is not None
    assert radcheck_row["attribute"] == "Cleartext-Password"
    assert radcheck_row["value"] == code

    radreply_rows = await conn.fetch(
        "SELECT username, attribute, value FROM radreply WHERE username = $1",
        code,
    )
    assert len(radreply_rows) > 0
    attributes = {row["attribute"]: row["value"] for row in radreply_rows}
    assert "Mikrotik-Rate-Limit" in attributes
    assert attributes["Mikrotik-Rate-Limit"] == "2M"
    assert "Session-Timeout" in attributes
    assert attributes["Session-Timeout"] == "600"

    # 5. Try requesting a trial again with the same phone (should raise 409 Conflict)
    response_again = client.post(
        "/api/v1/hotspot/trial",
        json={
            "phone": phone,
            "tenant_id": DEFAULT_TENANT_ID,
            "mac_address": mac,
        }
    )
    assert response_again.status_code == 409
    assert "already used" in response_again.json()["detail"].lower()
