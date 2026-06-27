"""
tests/security/test_tenant_isolation.py
========================================
Cross-tenant penetration tests — every attack vector must fail with 404 (not 403).
"""

from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from unittest.mock import patch

from app.config import settings
from app.core.security import hash_password, create_access_token, create_super_admin_access_token
from app.worker import generate_voucher_task


async def create_tenant_and_admin(
    conn: asyncpg.Connection,
    business_name: str,
    email: str,
    phone: str,
) -> tuple[str, str, str]:
    tenant_id = await conn.fetchval(
        """
        INSERT INTO tenants (business_name, owner_email, owner_phone,
                             subscription_tier, max_customers, status)
        VALUES ($1, $2, $3, 'starter', 50, 'active')
        RETURNING id
        """,
        business_name,
        email,
        phone,
    )
    user_id = await conn.fetchval(
        """
        INSERT INTO users (email, phone, hashed_password, role, tenant_id)
        VALUES ($1, $2, $3, 'admin', $4)
        RETURNING id
        """,
        email,
        phone,
        hash_password("TestPassword123!"),
        tenant_id,
    )
    token = create_access_token(
        user_id=str(user_id),
        role="admin",
        tenant_id=str(tenant_id),
    )
    return str(tenant_id), str(user_id), token


async def create_customer(
    conn: asyncpg.Connection,
    tenant_id: str,
    email: str,
    phone: str,
) -> str:
    return str(
        await conn.fetchval(
            """
            INSERT INTO users (email, phone, hashed_password, role, tenant_id)
            VALUES ($1, $2, $3, 'customer', $4)
            RETURNING id
            """,
            email,
            phone,
            hash_password("TestPassword123!"),
            UUID(tenant_id),
        )
    )


async def create_package(
    conn: asyncpg.Connection,
    tenant_id: str,
    admin_id: str,
    name: str,
) -> str:
    return str(
        await conn.fetchval(
            """
            INSERT INTO packages (name, price_kes, duration_minutes, speed_mbps, created_by, tenant_id)
            VALUES ($1, 100.00, 10080, 20, $2, $3)
            RETURNING id
            """,
            name,
            UUID(admin_id),
            UUID(tenant_id),
        )
    )


async def create_payment(
    conn: asyncpg.Connection,
    tenant_id: str,
    customer_id: str,
    package_id: str,
    checkout_id: str | None = None,
) -> str:
    checkout = checkout_id or f"checkout-{uuid4().hex[:8]}"
    return str(
        await conn.fetchval(
            """
            INSERT INTO payments
                (customer_id, package_id, amount_kes, status, phone_number,
                 mpesa_checkout_id, tenant_id)
            VALUES ($1, $2, 100.00, 'confirmed', '254700000099', $3, $4)
            RETURNING id
            """,
            UUID(customer_id),
            UUID(package_id),
            checkout,
            UUID(tenant_id),
        )
    )


async def create_voucher(
    conn: asyncpg.Connection,
    tenant_id: str,
    customer_id: str,
    package_id: str,
    payment_id: str,
    code: str = "TESTCODE001",
) -> str:
    return str(
        await conn.fetchval(
            """
            INSERT INTO vouchers
                (payment_id, customer_id, package_id, code, status, tenant_id)
            VALUES ($1, $2, $3, $4, 'active', $5)
            RETURNING id
            """,
            UUID(payment_id),
            UUID(customer_id),
            UUID(package_id),
            code,
            UUID(tenant_id),
        )
    )


async def create_router(
    conn: asyncpg.Connection,
    tenant_id: str,
    name: str = "Test Router",
) -> str:
    return str(
        await conn.fetchval(
            """
            INSERT INTO routers (name, host, port, username, password_encrypted, site_name, tenant_id, status)
            VALUES ($1, '10.0.0.1', 8728, 'admin', 'enc', 'Site A', $2, 'online')
            RETURNING id
            """,
            name,
            UUID(tenant_id),
        )
    )


@pytest.fixture
async def tenant_fixtures(conn: asyncpg.Connection):
    """Seed Tenant A resources and Tenant B admin token for cross-tenant attacks."""
    tenant_a_id, admin_a_id, token_a = await create_tenant_and_admin(
        conn, "Tenant A ISP", "sec_a_admin@test.com", "254711100001"
    )
    customer_a_id = await create_customer(
        conn, tenant_a_id, "sec_a_cust@test.com", "254711100002"
    )
    package_a_id = await create_package(conn, tenant_a_id, admin_a_id, "Package A")
    payment_a_id = await create_payment(conn, tenant_a_id, customer_a_id, package_a_id, "checkout-tenant-a")
    voucher_a_id = await create_voucher(
        conn, tenant_a_id, customer_a_id, package_a_id, payment_a_id
    )
    router_a_id = await create_router(conn, tenant_a_id)

    tenant_b_id, admin_b_id, token_b = await create_tenant_and_admin(
        conn, "Tenant B ISP", "sec_b_admin@test.com", "254711100003"
    )
    package_b_id = await create_package(conn, tenant_b_id, admin_b_id, "Package B")

    return {
        "tenant_a_id": tenant_a_id,
        "tenant_b_id": tenant_b_id,
        "token_a": token_a,
        "token_b": token_b,
        "admin_a_id": admin_a_id,
        "admin_b_id": admin_b_id,
        "customer_a_id": customer_a_id,
        "package_a_id": package_a_id,
        "package_b_id": package_b_id,
        "payment_a_id": payment_a_id,
        "voucher_a_id": voucher_a_id,
        "router_a_id": router_a_id,
        "headers_a": {"Authorization": f"Bearer {token_a}"},
        "headers_b": {"Authorization": f"Bearer {token_b}"},
    }


class TestPackageIsolation:
    @pytest.mark.asyncio
    async def test_tenant_b_cannot_read_tenant_a_package(
        self, client: TestClient, tenant_fixtures: dict
    ):
        fx = tenant_fixtures
        response = client.get(
            f"/api/v1/packages/{fx['package_a_id']}",
            headers=fx["headers_b"],
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_tenant_b_cannot_update_tenant_a_package(
        self, client: TestClient, tenant_fixtures: dict
    ):
        fx = tenant_fixtures
        response = client.put(
            f"/api/v1/packages/{fx['package_a_id']}",
            json={"name": "Hacked", "price_kes": 1, "duration_minutes": 60, "speed_mbps": 1},
            headers=fx["headers_b"],
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_tenant_b_cannot_delete_tenant_a_package(
        self, client: TestClient, tenant_fixtures: dict
    ):
        fx = tenant_fixtures
        response = client.delete(
            f"/api/v1/packages/{fx['package_a_id']}",
            headers=fx["headers_b"],
        )
        assert response.status_code == 404


class TestPaymentIsolation:
    @pytest.mark.asyncio
    async def test_tenant_b_cannot_read_tenant_a_payment_status(
        self, client: TestClient, conn: asyncpg.Connection, tenant_fixtures: dict
    ):
        fx = tenant_fixtures
        customer_b_id = await create_customer(
            conn, fx["tenant_b_id"], "sec_b_pay@test.com", "254711100005"
        )
        token_b_customer = create_access_token(
            user_id=customer_b_id,
            role="customer",
            tenant_id=fx["tenant_b_id"],
        )
        response = client.get(
            f"/api/v1/payments/{fx['payment_a_id']}/status",
            headers={"Authorization": f"Bearer {token_b_customer}"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cross_tenant_payment_history(
        self, client: TestClient, conn: asyncpg.Connection, tenant_fixtures: dict
    ):
        fx = tenant_fixtures
        customer_b_id = await create_customer(
            conn, fx["tenant_b_id"], "sec_b_cust@test.com", "254711100004"
        )
        token_b_customer = create_access_token(
            user_id=customer_b_id,
            role="customer",
            tenant_id=fx["tenant_b_id"],
        )
        response = client.get(
            "/api/v1/payments/me",
            headers={"Authorization": f"Bearer {token_b_customer}"},
        )
        assert response.status_code == 200
        payment_ids = [p["id"] for p in response.json()]
        assert fx["payment_a_id"] not in payment_ids


class TestVoucherIsolation:
    @pytest.mark.asyncio
    async def test_tenant_b_cannot_read_tenant_a_voucher(
        self, client: TestClient, tenant_fixtures: dict
    ):
        fx = tenant_fixtures
        response = client.get(
            f"/api/v1/vouchers/{fx['voucher_a_id']}",
            headers=fx["headers_b"],
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_tenant_b_cannot_revoke_tenant_a_voucher(
        self, client: TestClient, tenant_fixtures: dict
    ):
        fx = tenant_fixtures
        response = client.post(
            f"/api/v1/vouchers/{fx['voucher_a_id']}/revoke",
            headers=fx["headers_b"],
        )
        assert response.status_code == 404


class TestCustomerIsolation:
    @pytest.mark.asyncio
    async def test_tenant_b_cannot_see_tenant_a_customers(
        self, client: TestClient, tenant_fixtures: dict
    ):
        fx = tenant_fixtures
        response = client.get("/api/v1/admin/users", headers=fx["headers_b"])
        assert response.status_code == 200
        customer_ids = [u["id"] for u in response.json() if u["role"] == "customer"]
        assert fx["customer_a_id"] not in customer_ids


class TestRouterIsolation:
    @pytest.mark.asyncio
    async def test_tenant_b_cannot_read_tenant_a_router(
        self, client: TestClient, tenant_fixtures: dict
    ):
        fx = tenant_fixtures
        response = client.get(
            f"/api/v1/admin/routers/{fx['router_a_id']}",
            headers=fx["headers_b"],
        )
        assert response.status_code == 404


class TestWebhookIsolation:
    @pytest.mark.asyncio
    @patch("app.modules.webhooks.service.get_redis_pool")
    async def test_daraja_webhook_processes_correct_tenant_only(
        self,
        mock_get_redis,
        client: TestClient,
        conn: asyncpg.Connection,
        tenant_fixtures: dict,
    ):
        from tests.modules.test_webhooks import MockArqRedis

        mock_redis = MockArqRedis()
        mock_get_redis.return_value = mock_redis
        fx = tenant_fixtures

        await conn.execute(
            """
            UPDATE payments SET status = 'pending', mpesa_checkout_id = $1
            WHERE id = $2
            """,
            "ws_CO_WEBHOOK_SEC",
            UUID(fx["payment_a_id"]),
        )

        payload = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "test-merchant",
                    "CheckoutRequestID": "ws_CO_WEBHOOK_SEC",
                    "ResultCode": 0,
                    "ResultDesc": "Success",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 100},
                            {"Name": "MpesaReceiptNumber", "Value": "SECWEBHOOK01"},
                            {"Name": "TransactionDate", "Value": 20260617120000},
                            {"Name": "PhoneNumber", "Value": 254700000099},
                        ]
                    },
                }
            }
        }

        response = client.post("/api/v1/webhooks/daraja", json=payload)
        assert response.status_code == 200

        payment_a = await conn.fetchrow(
            "SELECT status FROM payments WHERE id = $1 AND tenant_id = $2",
            UUID(fx["payment_a_id"]),
            UUID(fx["tenant_a_id"]),
        )
        payment_b_count = await conn.fetchval(
            "SELECT COUNT(*) FROM payments WHERE tenant_id = $1",
            UUID(fx["tenant_b_id"]),
        )
        assert payment_a["status"] == "confirmed"
        assert payment_b_count == 0


class TestSuperAdminIsolation:
    @pytest.mark.asyncio
    async def test_super_admin_token_blocked_on_tenant_endpoint(
        self, client: TestClient, conn: asyncpg.Connection
    ):
        super_admin_id = await conn.fetchval(
            """
            INSERT INTO super_admins (email, hashed_password, full_name)
            VALUES ($1, $2, 'Security Test SA')
            RETURNING id
            """,
            "sec_sa@test.com",
            hash_password("TestPassword123!"),
        )
        sa_token = create_super_admin_access_token(str(super_admin_id))
        response = client.get(
            "/api/v1/packages",
            headers={"Authorization": f"Bearer {sa_token}"},
        )
        assert response.status_code == 403
        assert "impersonation" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_super_admin_impersonation_scoped_to_tenant(
        self, client: TestClient, conn: asyncpg.Connection, tenant_fixtures: dict
    ):
        fx = tenant_fixtures
        super_admin_id = await conn.fetchval(
            """
            INSERT INTO super_admins (email, hashed_password, full_name)
            VALUES ($1, $2, 'Impersonation Test SA')
            RETURNING id
            """,
            "sec_sa_imp@test.com",
            hash_password("TestPassword123!"),
        )

        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        impersonation_token = jwt.encode(
            {
                "sub": fx["admin_a_id"],
                "role": "admin",
                "tenant_id": fx["tenant_a_id"],
                "impersonation": True,
                "impersonated_by": str(super_admin_id),
                "iat": now,
                "exp": now + timedelta(minutes=30),
            },
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        imp_headers = {"Authorization": f"Bearer {impersonation_token}"}

        resp = client.get("/api/v1/packages", headers=imp_headers)
        assert resp.status_code == 200

        resp = client.get(f"/api/v1/packages/{fx['package_b_id']}", headers=imp_headers)
        assert resp.status_code == 404


class TestArqJobIsolation:
    @pytest.mark.asyncio
    @patch("app.worker.generate_voucher")
    async def test_job_with_wrong_tenant_id_is_rejected(
        self,
        mock_generate_voucher,
        db_pool: asyncpg.Pool,
        tenant_fixtures: dict,
    ):
        fx = tenant_fixtures
        ctx = {"db_pool": db_pool, "job_try": 1}
        result = await generate_voucher_task(
            ctx,
            fx["payment_a_id"],
            fx["tenant_b_id"],
        )
        assert result is None
        mock_generate_voucher.assert_not_called()

        voucher_count_a = await db_pool.fetchval(
            "SELECT COUNT(*) FROM vouchers WHERE tenant_id = $1",
            UUID(fx["tenant_a_id"]),
        )
        voucher_count_b = await db_pool.fetchval(
            "SELECT COUNT(*) FROM vouchers WHERE tenant_id = $1",
            UUID(fx["tenant_b_id"]),
        )
        assert voucher_count_a == 1  # fixture voucher only
        assert voucher_count_b == 0
