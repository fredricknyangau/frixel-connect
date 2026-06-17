"""
tests/modules/test_auth.py
===========================
Integration tests for user authentication and authorization logic.
"""

from fastapi.testclient import TestClient


def test_register_new_user(client: TestClient):
    """Asserts that a user can successfully register and receive a JWT token."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "new_user@zealsync.dev",
            "phone": "0798765432",
            "password": "Password123!",
            "role": "customer"
        }
    )
    assert response.status_code == 211 or response.status_code == 201  # HTTP_201_CREATED
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "customer"


def test_register_duplicate_email(client: TestClient):
    """Asserts that registering with an already existing email returns a 409 Conflict."""
    # Register the first user
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "duplicate@zealsync.dev",
            "phone": "0711223344",
            "password": "Password123!",
            "role": "customer"
        }
    )

    # Attempt to register with the same email
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "duplicate@zealsync.dev",
            "phone": "0755667788",
            "password": "DifferentPassword123!",
            "role": "customer"
        }
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_login_correct_credentials(client: TestClient):
    """Asserts that a user can log in with valid credentials and receive a JWT token."""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "customer@zealsync.dev",
            "password": "TestPassword123!"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "customer"


def test_login_wrong_password(client: TestClient):
    """Asserts that logging in with an incorrect password returns a 401 Unauthorized."""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "customer@zealsync.dev",
            "password": "WrongPassword!"
        }
    )
    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower() or "email" in response.json()["detail"].lower()


def test_protected_route_no_token(client: TestClient):
    """Asserts that accessing a guarded endpoint without a token returns a 401 Unauthorized."""
    # GET /payments/me is a customer-restricted route
    response = client.get("/api/v1/payments/me")
    assert response.status_code == 401
    assert "not authenticated" in response.json()["detail"].lower()


def test_protected_route_wrong_role(client: TestClient):
    """Asserts that accessing a route with an unauthorized role returns a 403 Forbidden."""
    # Obtain customer token
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "customer@zealsync.dev",
            "password": "TestPassword123!"
        }
    )
    token = login_response.json()["access_token"]

    # Try to access admin-only payments list as a customer
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/v1/admin/payments", headers=headers)
    assert response.status_code == 403
    assert "role" in response.json()["detail"].lower() or "permission" in response.json()["detail"].lower()
