"""
tests/security/test_error_oracle.py
====================================
Ensures cross-tenant resource access returns 404, never 403 (T7).
"""

import pytest
from fastapi.testclient import TestClient

from tests.security.test_tenant_isolation import tenant_fixtures  # noqa: F401 — fixture reuse


class TestNoErrorOracle:
    @pytest.mark.parametrize(
        "endpoint,resource_key",
        [
            ("/api/v1/packages/{id}", "package_a_id"),
            ("/api/v1/payments/{id}/status", "payment_a_id"),
            ("/api/v1/vouchers/{id}", "voucher_a_id"),
            ("/api/v1/admin/routers/{id}", "router_a_id"),
        ],
    )
    @pytest.mark.asyncio
    async def test_cross_tenant_returns_404_not_403(
        self,
        client: TestClient,
        tenant_fixtures: dict,
        endpoint: str,
        resource_key: str,
    ):
        fx = tenant_fixtures
        resource_id = fx[resource_key]
        url = endpoint.format(id=resource_id)
        response = client.get(url, headers=fx["headers_b"])
        assert response.status_code == 404, (
            f"Expected 404 for cross-tenant access on {url}, "
            f"got {response.status_code}. This is an information oracle."
        )
        assert response.status_code != 403, (
            "403 Forbidden leaks that the resource exists — "
            "attackers can use this to enumerate valid UUIDs across tenants."
        )
