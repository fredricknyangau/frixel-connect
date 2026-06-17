"""
tests/conftest.py
==================
Pytest configuration and global fixtures.
Enables running unit and integration tests against a clean, isolated database.
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

# Extract DB credentials and construct a URL pointing to 'postgres' (default) and the test DB
parsed_url = urllib.parse.urlparse(settings.DATABASE_URL)
POSTGRES_DB_URL = parsed_url._replace(path="/postgres").geturl()
TEST_DB_URL = parsed_url._replace(path="/wifi_billing_test").geturl()

# Override the application-wide database URL settings to point to the test database
settings.DATABASE_URL = TEST_DB_URL

TEST_PASSWORD = "TestPassword123!"


@pytest.fixture(autouse=True)
async def setup_test_database():
    """
    Function-scoped fixture that:
      1. Connects to the default 'postgres' database.
      2. Drops any existing 'wifi_billing_test' database.
      3. Creates a fresh 'wifi_billing_test' database.
      4. Connects to 'wifi_billing_test' and executes all migrations in order.
      5. Tears down (drops) the test database at the end of the test.
    """
    # Step 1: Connect to default 'postgres' to manage databases
    conn = await asyncpg.connect(dsn=POSTGRES_DB_URL)
    try:
        # Close any active connections to the test DB to allow dropping it
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

    # Step 2: Connect to the new test database and run all migrations
    test_conn = await asyncpg.connect(dsn=TEST_DB_URL)
    try:
        # Determine the migrations directory relative to this file
        migrations_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "migrations"
        )
        # Sort migrations alphabetically (001_..., 002_...)
        migration_files = sorted(
            [f for f in os.listdir(migrations_dir) if f.endswith(".sql")]
        )

        for filename in migration_files:
            filepath = os.path.join(migrations_dir, filename)
            with open(filepath, "r") as f:
                sql_content = f.read()
            # asyncpg can execute multi-statement SQL content directly
            await test_conn.execute(sql_content)
    finally:
        await test_conn.close()

    # Yield control to the test
    yield

    # Step 3: Tear down after the test finishes
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
      1. Truncates all tables in dependency order.
      2. Seeds the database with standard admin, reseller, and customer accounts.
      3. Seeds standard packages.
    This guarantees that every individual test starts with a clean database and identical seed data.
    """
    async with db_pool.acquire() as conn:
        # 1. Truncate all tables
        await conn.execute(
            "TRUNCATE sessions, vouchers, payments, packages, users CASCADE;"
        )

        # 2. Seed Users
        hashed = hash_password(TEST_PASSWORD)

        # Admin user
        admin_id = await conn.fetchval(
            """
            INSERT INTO users (email, phone, hashed_password, role, reseller_id)
            VALUES ($1, $2, $3, 'admin', NULL)
            RETURNING id
            """,
            "admin@zealsync.dev", "254700000001", hashed
        )

        # Reseller user (owned by admin)
        reseller_id = await conn.fetchval(
            """
            INSERT INTO users (email, phone, hashed_password, role, reseller_id)
            VALUES ($1, $2, $3, 'reseller', $4)
            RETURNING id
            """,
            "reseller@zealsync.dev", "254700000002", hashed, admin_id
        )

        # Customer user (owned by reseller)
        await conn.execute(
            """
            INSERT INTO users (email, phone, hashed_password, role, reseller_id)
            VALUES ($1, $2, $3, 'customer', $4)
            """,
            "customer@zealsync.dev", "254700000003", hashed, reseller_id
        )

        # 3. Seed Packages
        await conn.execute(
            """
            INSERT INTO packages (id, name, description, price_kes, duration_days, speed_mbps, created_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            "11111111-1111-1111-1111-111111111111",
            "Daily 10Mbps",
            "1-day internet access at 10 Mbps. Perfect for light browsing.",
            Decimal("50.00"),
            1,
            10,
            admin_id
        )

        await conn.execute(
            """
            INSERT INTO packages (id, name, description, price_kes, duration_days, speed_mbps, created_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            "22222222-2222-2222-2222-222222222222",
            "Weekly 20Mbps",
            "7-day internet access at 20 Mbps. Great for regular users.",
            Decimal("300.00"),
            7,
            20,
            admin_id
        )

    yield


@pytest.fixture
def client(db_pool: asyncpg.Pool) -> Generator[TestClient, None, None]:
    """
    Returns a FastAPI TestClient configured to run against the test database.
    """
    from app.main import app as fastapi_app

    with TestClient(fastapi_app) as test_client:
        yield test_client


@pytest.fixture
async def conn(db_pool: asyncpg.Pool) -> AsyncGenerator[asyncpg.Connection, None]:
    """Yields a database connection from the test pool for direct SQL verification."""
    async with db_pool.acquire() as connection:
        yield connection
