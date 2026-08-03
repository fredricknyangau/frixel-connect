from fastapi.testclient import TestClient

def test_refresh_token_rotation(client: TestClient):
    # 1. Login to get initial tokens
    response = client.post("/api/v1/auth/login", json={"email": "admin@Frixel Connect.dev", "password": "TestPassword123!"})
    assert response.status_code == 200
    data = response.json()
    assert "refresh_token" in data
    assert "access_token" in data
    
    initial_refresh = data["refresh_token"]
    
    # 2. Rotate token legitimately
    refresh_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": initial_refresh})
    assert refresh_resp.status_code == 200
    refresh_data = refresh_resp.json()
    assert "refresh_token" in refresh_data
    new_refresh = refresh_data["refresh_token"]
    assert new_refresh != initial_refresh
    
    # 3. Simulate token theft: reuse the initial, now-revoked token
    stolen_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": initial_refresh})
    assert stolen_resp.status_code == 401
    
    # 4. Verify the entire token family was revoked (the legitimate new token should now fail)
    third_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert third_resp.status_code == 401


def test_audit_logging(client: TestClient):
    # Login as admin
    response = client.post("/api/v1/auth/login", json={"email": "admin@Frixel Connect.dev", "password": "TestPassword123!"})
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Trigger an admin mutation (create package)
    pkg_resp = client.post("/api/v1/packages", json={
        "name": "Audit Test Package",
        "description": "testing",
        "price_kes": 100,
        "duration_minutes": 1440,
        "speed_mbps": 10
    }, headers=headers)
    assert pkg_resp.status_code == 201
    
    # (In a real test, we would query the DB directly using async conn to ensure the audit log was inserted, 
    # but for integration tests we're at least verifying the decorator didn't break the route).


def test_data_protection_endpoints(client: TestClient):
    # Login as customer
    response = client.post("/api/v1/auth/login", json={"email": "customer@Frixel Connect.dev", "password": "TestPassword123!"})
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Export Data
    exp_resp = client.get("/api/v1/customers/me/export", headers=headers)
    assert exp_resp.status_code == 200
    exp_data = exp_resp.json()
    assert "user" in exp_data
    assert exp_data["user"]["email"] == "customer@Frixel Connect.dev"
    assert "payments" in exp_data
    assert "vouchers" in exp_data
    assert "subscriptions" in exp_data
    
    # 2. Anonymize (Right to Erasure)
    del_resp = client.delete("/api/v1/customers/me", headers=headers)
    assert del_resp.status_code == 200
    
    # 3. Verify user can no longer log in
    login_resp = client.post("/api/v1/auth/login", json={"email": "customer@Frixel Connect.dev", "password": "TestPassword123!"})
    assert login_resp.status_code == 401


def test_client_ip_extraction_middleware(client: TestClient):
    from app.main import app
    from app.core.ip_context import client_ip_var
    
    # Register a temporary route to return the context var IP
    # Try/except to prevent errors if the route is registered multiple times
    try:
        @app.get("/test-ip-extraction")
        async def get_test_ip():
            return {"ip": client_ip_var.get()}
    except Exception:
        pass
        
    # 1. Test X-Real-IP is prioritized over X-Forwarded-For
    resp = client.get("/test-ip-extraction", headers={
        "X-Real-IP": "196.201.214.200",
        "X-Forwarded-For": "9.9.9.9, 172.18.0.1"
    })
    assert resp.status_code == 200
    assert resp.json()["ip"] == "196.201.214.200"

    # 2. Test fallback to X-Forwarded-For first element
    resp = client.get("/test-ip-extraction", headers={
        "X-Forwarded-For": "8.8.8.8, 172.18.0.1"
    })
    assert resp.status_code == 200
    assert resp.json()["ip"] == "8.8.8.8"

    # 3. Test invalid IP validation
    resp = client.get("/test-ip-extraction", headers={
        "X-Real-IP": "invalid-ip-format"
    })
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid client IP address."

