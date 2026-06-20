import pytest
import asyncpg
from fastapi.testclient import TestClient

@pytest.mark.asyncio
async def test_system_health_endpoint_response_fields(
    client: TestClient, conn: asyncpg.Connection
):
    """
    Verifies that the /admin/system-health endpoint responds correctly
    and returns both backend metrics and the specific fields required by the frontend layout:
    - reconciliation_backlog
    - webhook_success_rate_24h
    - last_heartbeat_at in routers
    """
    # 1. Setup default admin user and token
    tenant_id = "aaaaaaaa-0000-0000-0000-000000000001"
    admin = await conn.fetchrow("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
    from app.core.security import create_access_token
    token = create_access_token(str(admin["id"]), "admin", tenant_id)

    # 2. Add a sample router to verify router list parsing
    await conn.execute(
        """
        INSERT INTO routers (id, tenant_id, name, host, username, password_encrypted, site_name, status, last_heartbeat_at)
        VALUES ('11111111-2222-3333-4444-555555555555', $1, 'Test Router', '192.168.88.1', 'admin', 'enc_pw', 'Main Site', 'online', NOW())
        """,
        tenant_id
    )

    # 3. Call the API endpoint
    response = client.get(
        "/api/v1/admin/system-health",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()

    # 4. Assert backend model compatibility fields exist
    assert "status" in data
    assert "queue_depth" in data
    assert "unreconciled_payments" in data
    assert "active_routers" in data
    assert "total_routers" in data
    assert "stuck_payments_count" in data
    assert "webhook_success_rate" in data
    assert "routers" in data

    # 5. Assert frontend layout compatibility fields exist and are populated
    assert "reconciliation_backlog" in data
    assert data["reconciliation_backlog"] == data["unreconciled_payments"]
    assert "webhook_success_rate_24h" in data
    assert data["webhook_success_rate_24h"] == data["webhook_success_rate"]

    # 6. Assert router items contain both sets of last seen / last heartbeat fields
    routers = data["routers"]
    assert len(routers) > 0
    router_item = routers[0]
    assert "id" in router_item
    assert "name" in router_item
    assert "status" in router_item
    assert "last_seen" in router_item
    assert "last_heartbeat_at" in router_item
    assert router_item["last_seen"] == router_item["last_heartbeat_at"]
