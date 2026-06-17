#!/usr/bin/env python3
"""
seed_db.py — Database Seeder for WiFi Billing System
=====================================================
Inserts a known set of users and packages so you have working data
to test every route immediately after running migrations.

Run from inside Docker Compose:
    docker compose exec api python seed_db.py

Run from your local machine (with virtualenv activated):
    python seed_db.py

How it works:
    1. Connects to the database using the same DATABASE_URL as the API.
    2. Wraps all inserts in a single transaction.
    3. Uses INSERT ... ON CONFLICT DO NOTHING so running this script
       twice doesn't fail — it just skips rows that already exist.
       This is the correct idempotency pattern for seeders:
       ON CONFLICT DO NOTHING vs IF NOT EXISTS:
       - IF NOT EXISTS is for DDL (CREATE TABLE, CREATE INDEX).
       - ON CONFLICT DO NOTHING is for DML (INSERT). It tells PostgreSQL:
         "if this row violates a UNIQUE constraint, silently skip it."
"""

import asyncio
import sys
import os

import asyncpg

# ---------------------------------------------------------------------------
# We import settings the same way the API does so DATABASE_URL is read from
# the .env file automatically. This means the seeder always talks to the
# same database the API uses — no separate config needed.
# ---------------------------------------------------------------------------
# Add the project root to sys.path so `from app.config import settings` works
# when running this script as: python seed_db.py (not as a module).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.core.security import hash_password


# ---------------------------------------------------------------------------
# Seed data definitions
# ---------------------------------------------------------------------------

# All test accounts use the same password. In production NEVER do this.
TEST_PASSWORD = "TestPassword123!"


# Users are inserted in order: admin first, then reseller (needs admin.id),
# then customer (needs reseller.id). We resolve the IDs after each insert.
ADMIN_EMAIL    = "admin@zealsync.dev"
RESELLER_EMAIL = "reseller@zealsync.dev"
CUSTOMER_EMAIL = "customer@zealsync.dev"

PACKAGES = [
    {
        "name":          "Daily 10Mbps",
        "description":   "1-day internet access at 10 Mbps. Perfect for light browsing.",
        "price_kes":     50.00,
        "duration_days": 1,
        "speed_mbps":    10,
    },
    {
        "name":          "Weekly 20Mbps",
        "description":   "7-day internet access at 20 Mbps. Great for regular users.",
        "price_kes":     300.00,
        "duration_days": 7,
        "speed_mbps":    20,
    },
]


async def seed():
    print("=" * 60)
    print("  WiFi Billing System — Database Seeder")
    print("=" * 60)

    # Connect using the same DSN as the API. asyncpg.connect() opens a
    # single connection (not a pool) — fine for a one-shot script.
    conn = await asyncpg.connect(dsn=settings.DATABASE_URL)

    try:
        # Wrap everything in a transaction. If any insert fails (e.g. the
        # database schema is wrong), the whole seeder rolls back cleanly
        # instead of leaving partial data.
        async with conn.transaction():

            # ── 1. Admin user ─────────────────────────────────────────────
            # reseller_id = NULL for the top-level admin (no parent).
            # We use RETURNING id to get the UUID the database generated,
            # so we can reference it when creating child records.
            admin_row = await conn.fetchrow(
                """
                INSERT INTO users (email, phone, hashed_password, role, reseller_id)
                VALUES ($1, $2, $3, 'admin', NULL)
                ON CONFLICT (email) DO NOTHING
                RETURNING id, email, role
                """,
                ADMIN_EMAIL,
                "254700000001",
                hash_password(TEST_PASSWORD),
            )

            if admin_row is None:
                # ON CONFLICT triggered — user already exists, fetch their id.
                admin_row = await conn.fetchrow(
                    "SELECT id, email, role FROM users WHERE email = $1",
                    ADMIN_EMAIL,
                )
                print(f"⚠  Admin already exists:    {admin_row['email']} ({admin_row['id']})")
            else:
                print(f"✓  Created admin:           {admin_row['email']} ({admin_row['id']})")

            admin_id = admin_row["id"]

            # ── 2. Reseller user ──────────────────────────────────────────
            # reseller_id = admin's id. In our model, resellers are
            # "owned by" the admin. This is the self-referential FK.
            reseller_row = await conn.fetchrow(
                """
                INSERT INTO users (email, phone, hashed_password, role, reseller_id)
                VALUES ($1, $2, $3, 'reseller', $4)
                ON CONFLICT (email) DO NOTHING
                RETURNING id, email, role
                """,
                RESELLER_EMAIL,
                "254700000002",
                hash_password(TEST_PASSWORD),
                admin_id,                          # reseller's parent = admin
            )

            if reseller_row is None:
                reseller_row = await conn.fetchrow(
                    "SELECT id, email, role FROM users WHERE email = $1",
                    RESELLER_EMAIL,
                )
                print(f"⚠  Reseller already exists: {reseller_row['email']} ({reseller_row['id']})")
            else:
                print(f"✓  Created reseller:        {reseller_row['email']} ({reseller_row['id']})")

            reseller_id = reseller_row["id"]

            # ── 3. Customer user ──────────────────────────────────────────
            # reseller_id = reseller's id. The customer belongs to the reseller.
            customer_row = await conn.fetchrow(
                """
                INSERT INTO users (email, phone, hashed_password, role, reseller_id)
                VALUES ($1, $2, $3, 'customer', $4)
                ON CONFLICT (email) DO NOTHING
                RETURNING id, email, role
                """,
                CUSTOMER_EMAIL,
                "254700000003",
                hash_password(TEST_PASSWORD),
                reseller_id,                       # customer's parent = reseller
            )

            if customer_row is None:
                customer_row = await conn.fetchrow(
                    "SELECT id, email, role FROM users WHERE email = $1",
                    CUSTOMER_EMAIL,
                )
                print(f"⚠  Customer already exists: {customer_row['email']} ({customer_row['id']})")
            else:
                print(f"✓  Created customer:        {customer_row['email']} ({customer_row['id']})")

            # ── 4. Packages ───────────────────────────────────────────────
            print("")
            for pkg in PACKAGES:
                pkg_row = await conn.fetchrow(
                    """
                    INSERT INTO packages
                        (name, description, price_kes, duration_days, speed_mbps, created_by)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (name) DO NOTHING
                    RETURNING id, name, price_kes
                    """,
                    pkg["name"],
                    pkg["description"],
                    pkg["price_kes"],
                    pkg["duration_days"],
                    pkg["speed_mbps"],
                    admin_id,                      # admin created the packages
                )

                if pkg_row is None:
                    pkg_row = await conn.fetchrow(
                        "SELECT id, name, price_kes FROM packages WHERE name = $1",
                        pkg["name"],
                    )
                    print(f"⚠  Package already exists:  {pkg_row['name']} (KES {pkg_row['price_kes']}) ({pkg_row['id']})")
                else:
                    print(f"✓  Created package:         {pkg_row['name']} (KES {pkg_row['price_kes']}) ({pkg_row['id']})")

        # Transaction committed successfully.
        print("")
        print("=" * 60)
        print("  Seeding complete.")
        print(f"  Login credentials for all test accounts:")
        print(f"    Password: {TEST_PASSWORD}")
        print(f"    Admin:    {ADMIN_EMAIL}")
        print(f"    Reseller: {RESELLER_EMAIL}")
        print(f"    Customer: {CUSTOMER_EMAIL}")
        print("=" * 60)

    finally:
        # Always close the connection even if an error occurred.
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
