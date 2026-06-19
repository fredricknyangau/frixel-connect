"""
tests/conftest.py
==================
Pytest configuration and global fixtures.
Enables running unit and integration tests against a clean, isolated database.

PHASE 1 UPDATE:
  - setup_test_database runs ALL migrations including 006 and 007.
  - clean_and_seed_db now creates a default tenant first, then seeds all
    users and packages with tenant_id = DEFAULT_TENANT_ID.
  - The test database URL uses the same DEFAULT_TENANT_ID as production.
"""

import asyncio
import os
import urllib.parse
from datetime import datetime
from decimal import Decimal
from typing import AsyncGenerator, Generator

import asyncpg
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.core.security import hash_password
from app.database import get_db

# Extract DB credentials and construct test DB URL
parsed_url = urllib.parse.urlparse(settings.DATABASE_URL)
POSTGRES_DB_URL = parsed_url._replace(path="/postgres").geturl()
TEST_DB_URL     = parsed_url._replace(path="/wifi_billing_test").geturl()

# Override application-wide DATABASE_URL to point at the test database.
settings.DATABASE_URL = TEST_DB_URL

TEST_PASSWORD      = "TestPassword123!"
DEFAULT_TENANT_ID  = "aaaaaaaa-0000-0000-0000-000000000001"


@pytest.fixture(autouse=True)
async def setup_test_database():
    """
    Function-scoped fixture that:
      1. Connects to 'postgres' database to drop/create 'wifi_billing_test'.
      2. Runs all migrations (001–007) against the fresh test DB.
      3. Tears down after the test completes.
    """
    conn = await asyncpg.connect(dsn=POSTGRES_DB_URL)
    try:
        # Terminate active connections to allow DROP
        await conn.execute(
            """
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = 'wifi_billing_test'
              AND pid <> pg_backend_pid();
            """
        )
        await conn.execute("DROP DATABASE IF EXISTS wifi_billing_test")
        await conn.execute("CREATE DATABASE wifi_billing_test")
    finally:
        await conn.close()

    # Run all migrations in order
    test_conn = await asyncpg.connect(dsn=TEST_DB_URL)
    try:
        migrations_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "migrations"
        )
        migration_files = sorted(
            [f for f in os.listdir(migrations_dir) if f.endswith(".sql")]
        )

        for filename in migration_files:
            filepath = os.path.join(migrations_dir, filename)
            with open(filepath, "r") as f:
                sql_content = f.read()
            await test_conn.execute(sql_content)
    finally:
        await test_conn.close()

    yield

    # Teardown
    conn = await asyncpg.connect(dsn=POSTGRES_DB_URL)
    try:
        await conn.execute(
            """
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = 'wifi_billing_test'
              AND pid <> pg_backend_pid();
            """
        )
        await conn.execute("DROP DATABASE IF EXISTS wifi_billing_test")
    finally:
        await conn.close()


@pytest.fixture
async def db_pool(setup_test_database) -> asyncpg.Pool:
    """Function-scoped connection pool pointing to the test database."""
    pool = await asyncpg.create_pool(
        dsn=TEST_DB_URL,
        min_size=1,
        max_size=5,
    )
    yield pool
    await pool.close()


@pytest.fixture(autouse=True)
async def clean_and_seed_db(db_pool: asyncpg.Pool) -> AsyncGenerator[None, None]:
    """
    Function-scoped fixture that:
      1. Truncates all tables.
      2. Creates the default tenant (migration 007 inserted it, but TRUNCATE removes it).
      3. Seeds admin, reseller, customer accounts with tenant_id.
      4. Seeds packages with tenant_id.
    """
    async with db_pool.acquire() as conn:
        # 1. Truncate in dependency order
        await conn.execute(
            "TRUNCATE sessions, vouchers, payments, packages, users, tenants CASCADE;"
        )

        # 2. Re-insert the default tenant (TRUNCATE removed it)
        await conn.execute(
            """
            INSERT INTO tenants (id, business_name, owner_email, owner_phone,
                                 subscription_tier, max_customers, status)
            VALUES ($1, 'Default ISP (ZealSync MLP)', 'admin@zealsync.dev',
                    '254700000001', 'enterprise', 99999, 'active')
            """,
            DEFAULT_TENANT_ID,
        )

        # 3. Seed users (all in the default tenant)
        hashed = hash_password(TEST_PASSWORD)

        admin_id = await conn.fetchval(
            """
            INSERT INTO users (email, phone, hashed_password, role, reseller_id, tenant_id)
            VALUES ($1, $2, $3, 'admin', NULL, $4)
            RETURNING id
            """,
            "admin@zealsync.dev", "254700000001", hashed, DEFAULT_TENANT_ID
        )

        reseller_id = await conn.fetchval(
            """
            INSERT INTO users (email, phone, hashed_password, role, reseller_id, tenant_id)
            VALUES ($1, $2, $3, 'reseller', $4, $5)
            RETURNING id
            """,
            "reseller@zealsync.dev", "254700000002", hashed, admin_id, DEFAULT_TENANT_ID
        )

        await conn.execute(
            """
            INSERT INTO users (email, phone, hashed_password, role, reseller_id, tenant_id)
            VALUES ($1, $2, $3, 'customer', $4, $5)
            """,
            "customer@zealsync.dev", "254700000003", hashed, reseller_id, DEFAULT_TENANT_ID
        )

        # 4. Seed packages (in the default tenant)
        await conn.execute(
            """
            INSERT INTO packages
                (id, name, description, price_kes, duration_minutes, speed_mbps, created_by, tenant_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            "11111111-1111-1111-1111-111111111111",
            "Daily 10Mbps",
            "1-day internet access at 10 Mbps.",
            Decimal("50.00"),
            1440,
            10,
            admin_id,
            DEFAULT_TENANT_ID,
        )

        await conn.execute(
            """
            INSERT INTO packages
                (id, name, description, price_kes, duration_minutes, speed_mbps, created_by, tenant_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            "22222222-2222-2222-2222-222222222222",
            "Weekly 20Mbps",
            "7-day internet access at 20 Mbps.",
            Decimal("300.00"),
            10080,
            20,
            admin_id,
            DEFAULT_TENANT_ID,
        )

    yield


@pytest.fixture
def client(db_pool: asyncpg.Pool) -> Generator[TestClient, None, None]:
    """Returns a FastAPI TestClient configured to run against the test database."""
    from app.main import app as fastapi_app

    with TestClient(fastapi_app) as test_client:
        yield test_client


@pytest.fixture
async def conn(db_pool: asyncpg.Pool) -> AsyncGenerator[asyncpg.Connection, None]:
    """Yields a database connection from the test pool for direct SQL verification."""
    async with db_pool.acquire() as connection:
        yield connection
