#!/usr/bin/env python3
"""
seed_db.py -Database Seeder for ZealSync (Phase 1: Multi-Tenant)
===================================================================
Inserts a known set of users and packages so you have working data
to test every route immediately after running migrations.

PHASE 1 CHANGE:
  All users and packages now reference the default tenant created by
  migration 007_add_tenant_id.sql. The default tenant's UUID is fixed:
  'aaaaaaaa-0000-0000-0000-000000000001'

Run from inside Docker Compose:
    docker compose exec api python seed_db.py

Run from your local machine (with virtualenv activated):
    python seed_db.py

Idempotency: uses INSERT ... ON CONFLICT DO NOTHING so running this
script twice doesn't fail -it just skips rows that already exist.
"""

import asyncio
import sys
import os

import asyncpg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.core.security import hash_password

# ---------------------------------------------------------------------------
# Seed data definitions
# ---------------------------------------------------------------------------

TEST_PASSWORD = "TestPassword123!"

ADMIN_EMAIL    = "admin@zealsync.dev"
RESELLER_EMAIL = "reseller@zealsync.dev"
CUSTOMER_EMAIL = "customer@zealsync.dev"

# The default tenant UUID created by migration 007.
# All seed data belongs to this tenant.
DEFAULT_TENANT_ID = "aaaaaaaa-0000-0000-0000-000000000001"

PACKAGES = [
    {
        "name":             "Daily 10Mbps",
        "description":      "1-day internet access at 10 Mbps. Perfect for light browsing.",
        "price_kes":        50.00,
        "duration_minutes": 1440,
        "speed_mbps":       10,
    },
    {
        "name":             "Weekly 20Mbps",
        "description":      "7-day internet access at 20 Mbps. Great for regular users.",
        "price_kes":        300.00,
        "duration_minutes": 10080,
        "speed_mbps":       20,
    },
]


async def seed():
    print("=" * 60)
    print("  ZealSync -Database Seeder (Phase 1: Multi-Tenant)")
    print("=" * 60)

    conn = await asyncpg.connect(dsn=settings.DATABASE_URL)

    try:
        async with conn.transaction():

            # ── 0. Verify the default tenant exists ──────────────────────────
            # Migration 007 should have created this. If it's missing, the
            # migration hasn't run yet.
            tenant = await conn.fetchrow(
                "SELECT id, business_name FROM tenants WHERE id = $1",
                DEFAULT_TENANT_ID,
            )
            if not tenant:
                print("⚠  Default tenant not found. Run migrations first:")
                print("     ./scripts/run_migrations.sh")
                return
            print(f"✓  Default tenant:          {tenant['business_name']} ({tenant['id']})")

            # ── 1. Admin user ─────────────────────────────────────────────────
            # Now includes tenant_id -admin belongs to the default tenant.
            admin_row = await conn.fetchrow(
                """
                INSERT INTO users (email, phone, hashed_password, role, reseller_id, tenant_id)
                VALUES ($1, $2, $3, 'admin', NULL, $4)
                ON CONFLICT (email) DO NOTHING
                RETURNING id, email, role
                """,
                ADMIN_EMAIL,
                "254700000001",
                hash_password(TEST_PASSWORD),
                DEFAULT_TENANT_ID,
            )

            if admin_row is None:
                admin_row = await conn.fetchrow(
                    "SELECT id, email, role FROM users WHERE email = $1",
                    ADMIN_EMAIL,
                )
                print(f"⚠  Admin already exists:    {admin_row['email']} ({admin_row['id']})")
            else:
                print(f"✓  Created admin:           {admin_row['email']} ({admin_row['id']})")

            admin_id = admin_row["id"]

            # ── 2. Reseller user ──────────────────────────────────────────────
            reseller_row = await conn.fetchrow(
                """
                INSERT INTO users (email, phone, hashed_password, role, reseller_id, tenant_id, wallet_reference)
                VALUES ($1, $2, $3, 'reseller', $4, $5, 'WS12345')
                ON CONFLICT (email) DO NOTHING
                RETURNING id, email, role
                """,
                RESELLER_EMAIL,
                "254700000002",
                hash_password(TEST_PASSWORD),
                admin_id,
                DEFAULT_TENANT_ID,
            )

            if reseller_row is None:
                reseller_row = await conn.fetchrow(
                    "SELECT id, email, role FROM users WHERE email = $1",
                    RESELLER_EMAIL,
                )
                # Ensure it has the WS12345 wallet reference even if already seeded
                await conn.execute(
                    "UPDATE users SET wallet_reference = 'WS12345' WHERE id = $1 AND wallet_reference IS NULL",
                    reseller_row["id"],
                )
                print(f"⚠  Reseller already exists: {reseller_row['email']} ({reseller_row['id']})")
            else:
                print(f"✓  Created reseller:        {reseller_row['email']} ({reseller_row['id']})")

            reseller_id = reseller_row["id"]

            # ── 3. Customer user ──────────────────────────────────────────────
            customer_row = await conn.fetchrow(
                """
                INSERT INTO users (email, phone, hashed_password, role, reseller_id, tenant_id)
                VALUES ($1, $2, $3, 'customer', $4, $5)
                ON CONFLICT (email) DO NOTHING
                RETURNING id, email, role
                """,
                CUSTOMER_EMAIL,
                "254700000003",
                hash_password(TEST_PASSWORD),
                reseller_id,
                DEFAULT_TENANT_ID,
            )

            if customer_row is None:
                customer_row = await conn.fetchrow(
                    "SELECT id, email, role FROM users WHERE email = $1",
                    CUSTOMER_EMAIL,
                )
                print(f"⚠  Customer already exists: {customer_row['email']} ({customer_row['id']})")
            else:
                print(f"✓  Created customer:        {customer_row['email']} ({customer_row['id']})")

            # ── 4. Packages ───────────────────────────────────────────────────
            print("")
            for pkg in PACKAGES:
                pkg_row = await conn.fetchrow(
                    """
                    INSERT INTO packages
                        (name, description, price_kes, duration_minutes, speed_mbps, created_by, tenant_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (tenant_id, name) DO NOTHING
                    RETURNING id, name, price_kes
                    """,
                    pkg["name"],
                    pkg["description"],
                    pkg["price_kes"],
                    pkg["duration_minutes"],
                    pkg["speed_mbps"],
                    admin_id,
                    DEFAULT_TENANT_ID,
                )

                if pkg_row is None:
                    pkg_row = await conn.fetchrow(
                        "SELECT id, name, price_kes FROM packages WHERE name = $1",
                        pkg["name"],
                    )
                    print(f"⚠  Package already exists:  {pkg_row['name']} (KES {pkg_row['price_kes']}) ({pkg_row['id']})")
                else:
                    print(f"✓  Created package:         {pkg_row['name']} (KES {pkg_row['price_kes']}) ({pkg_row['id']})")

        print("")
        print("=" * 60)
        print("  Seeding complete.")
        print(f"  Login credentials for all test accounts:")
        print(f"    Password:  {TEST_PASSWORD}")
        print(f"    Admin:     {ADMIN_EMAIL}")
        print(f"    Reseller:  {RESELLER_EMAIL}")
        print(f"    Customer:  {CUSTOMER_EMAIL}")
        print(f"    Tenant ID: {DEFAULT_TENANT_ID}")
        print("=" * 60)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
