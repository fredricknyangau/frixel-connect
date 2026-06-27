import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
import asyncpg

from app.core.security import create_access_token, hash_password, decrypt_secret

# ── Helper: create a tenant + admin user directly in DB ───────────────────────
async def create_tenant_and_admin(
    conn: asyncpg.Connection,
    business_name: str,
    email: str,
    phone: str,
) -> tuple[str, str, str]:
    """Creates a tenant and admin user. Returns (tenant_id, user_id, token)."""
    tenant_id = await conn.fetchval(
        """
        INSERT INTO tenants (business_name, owner_email, owner_phone, subscription_tier, max_customers, status)
        VALUES ($1, $2, $3, 'starter', 50, 'active')
        RETURNING id
        """,
        business_name, email, phone
    )
    user_id = await conn.fetchval(
        """
        INSERT INTO users (email, phone, hashed_password, role, tenant_id)
        VALUES ($1, $2, $3, 'admin', $4)
        RETURNING id
        """,
        email, phone, hash_password("TestPassword123!"), tenant_id
    )
    token = create_access_token(user_id=str(user_id), role="admin", tenant_id=str(tenant_id))
    return str(tenant_id), str(user_id), token

@pytest.mark.asyncio
@patch("app.modules.routers.router.add_wireguard_peer")
@patch("app.modules.routers.router.get_server_public_key")
@patch("app.modules.routers.router.assign_peer_ip")
@patch("app.modules.routers.router.check_peer_connected")
@patch("app.integrations.mikrotik.get_mikrotik_client")
async def test_router_onboarding_wizard_endpoints(
    mock_get_client,
    mock_check_connected,
    mock_assign_ip,
    mock_get_pubkey,
    mock_add_peer,
    client: TestClient,
    conn: asyncpg.Connection,
):
    # Setup mocks
    mock_assign_ip.return_value = "10.8.0.5"
    mock_get_pubkey.return_value = "zealsync_server_public_key_mock_base64_val="
    mock_check_connected.return_value = True

    tenant_id, admin_id, token = await create_tenant_and_admin(
        conn, "Tenant Onboarding", "admin_ob@test.com", "254711999908"
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Step 1: /onboarding/init
    init_payload = {
        "name": "Onboarding Router",
        "site_name": "Staging Site"
    }
    resp = client.post("/api/v1/admin/routers/onboarding/init", json=init_payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    router_id = data["router_id"]
    assert data["zealsync_public_key"] == "zealsync_server_public_key_mock_base64_val="
    assert data["assigned_ip"] == "10.8.0.5"

    # Verify db status is pending_setup
    db_row = await conn.fetchrow("SELECT * FROM routers WHERE id = $1", router_id)
    assert db_row["status"] == "pending_setup"
    assert str(db_row["wireguard_assigned_ip"]) == "10.8.0.5"
    assert db_row["wireguard_public_key"] == "zealsync_server_public_key_mock_base64_val="

    # Step 2: /onboarding/register-peer
    peer_payload = {
        "router_id": router_id,
        "peer_public_key": "mikrotik_peer_public_key_mock_base64_val="
    }
    resp = client.post("/api/v1/admin/routers/onboarding/register-peer", json=peer_payload, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    mock_add_peer.assert_called_once_with("mikrotik_peer_public_key_mock_base64_val=", "10.8.0.5")

    # Verify db peer key is updated
    db_row = await conn.fetchrow("SELECT wireguard_peer_public_key FROM routers WHERE id = $1", router_id)
    assert db_row["wireguard_peer_public_key"] == "mikrotik_peer_public_key_mock_base64_val="

    # Step 3: /onboarding/test-tunnel
    tunnel_payload = {
        "router_id": router_id
    }
    resp = client.post("/api/v1/admin/routers/onboarding/test-tunnel", json=tunnel_payload, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["connected"] is True

    # Step 4: /onboarding/save-credentials
    creds_payload = {
        "router_id": router_id,
        "username": "api_user",
        "password": "secret_password",
        "port": 8728
    }
    resp = client.post("/api/v1/admin/routers/onboarding/save-credentials", json=creds_payload, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Verify DB credentials are saved and encrypted, and status changed to 'testing'
    db_row = await conn.fetchrow("SELECT * FROM routers WHERE id = $1", router_id)
    assert db_row["status"] == "testing"
    assert db_row["username"] == "api_user"
    assert db_row["port"] == 8728
    assert decrypt_secret(db_row["password_encrypted"]) == "secret_password"

    # Step 5: /onboarding/test-api
    # Mock client and get_user_profile_names
    mock_client = MagicMock()
    mock_client.get_user_profile_names = AsyncMock(return_value=["default", "10Mbps"])
    mock_get_client.return_value = mock_client

    test_api_payload = {
        "router_id": router_id
    }
    resp = client.post("/api/v1/admin/routers/onboarding/test-api", json=test_api_payload, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["connected"] is True
    assert resp.json()["profiles"] == ["default", "10Mbps"]

    # Step 6: /onboarding/setup-profiles
    # Mock make_client async context manager and client.post
    mock_http_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.is_success = True
    mock_http_client.post.return_value = mock_response
    
    # Define an async context manager mock
    class AsyncContextManagerMock:
        async def __aenter__(self):
            return mock_http_client
        async def __aexit__(self, exc_type, exc, tb):
            pass
            
    mock_client._make_client.return_value = AsyncContextManagerMock()

    profiles_payload = {
        "router_id": router_id,
        "profiles": [
            {"name": "10Mbps", "rate_limit": "10M/10M"},
            {"name": "20Mbps", "rate_limit": "20M/20M"}
        ]
    }
    resp = client.post("/api/v1/admin/routers/onboarding/setup-profiles", json=profiles_payload, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["created"] == ["10Mbps", "20Mbps"]
    assert resp.json()["failed"] == []

    # Step 7: /onboarding/complete
    complete_payload = {
        "router_id": router_id
    }
    resp = client.post("/api/v1/admin/routers/onboarding/complete", json=complete_payload, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "online"

    # Verify status changed to 'online' in DB
    db_row = await conn.fetchrow("SELECT status FROM routers WHERE id = $1", router_id)
    assert db_row["status"] == "online"
