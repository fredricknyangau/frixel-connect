#!/usr/bin/env python3
"""
scripts/seed_super_admin.py
=============================
Interactive seeder for the first Frixel Connect super admin account.

USAGE:
    # Inside Docker Compose (recommended):
    docker compose exec api python scripts/seed_super_admin.py

    # Direct (with virtualenv activated and DATABASE_URL set):
    python scripts/seed_super_admin.py

IDEMPOTENCY:
    If a super admin with the given email already exists, the script prints
    a message and exits cleanly-no error, no duplicate row.

WHAT HAPPENS AFTER RUNNING:
    The account is created with totp_secret=NULL, totp_verified_at=NULL.
    On first login at /super-admin/auth/login, the system detects that TOTP
    has not been set up and sets totp_setup_required=True in the response.
    The super admin must then:
      1. POST /super-admin/auth/totp/setup  → scan the QR code
      2. POST /super-admin/auth/totp/verify → confirm a valid 6-digit code

RECOVERY (if authenticator is lost):
    Directly reset the account in the database to restart TOTP setup:
        UPDATE super_admins
        SET totp_secret = NULL, totp_verified_at = NULL
        WHERE email = 'your@email.com';
    Then log in again and repeat the TOTP setup flow.
"""

import asyncio
import getpass
import os
import sys

# Allow running from the project root: python scripts/seed_super_admin.py
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import asyncpg

from app.config import settings
from app.core.security import hash_password


async def seed_super_admin() -> None:
    print()
    print("=" * 60)
    print("  Frixel Connect-Super Admin Account Seeder")
    print("=" * 60)
    print()
    print("  This creates the first super admin (Frixel Connect operator) account.")
    print("  TOTP (Google Authenticator) setup will be required on first login.")
    print()

    # ── Prompt for credentials ────────────────────────────────────────────────
    email = input("  Email address: ").strip()
    if not email or "@" not in email:
        print("  ✗ Invalid email address. Aborting.")
        sys.exit(1)

    full_name = input("  Full name:     ").strip()
    if not full_name:
        print("  ✗ Full name cannot be empty. Aborting.")
        sys.exit(1)

    # getpass hides the password from terminal echo-essential for a seed script.
    password = getpass.getpass("  Password:      ")
    if len(password) < 12:
        print("  ✗ Password must be at least 12 characters. Aborting.")
        sys.exit(1)

    confirm = getpass.getpass("  Confirm:       ")
    if password != confirm:
        print("  ✗ Passwords do not match. Aborting.")
        sys.exit(1)

    print()

    # ── Connect to database ───────────────────────────────────────────────────
    try:
        conn = await asyncpg.connect(dsn=settings.DATABASE_URL)
    except Exception as exc:
        print(f"  ✗ Database connection failed: {exc}")
        print("    Is Docker Compose running? Try: docker compose up -d db")
        sys.exit(1)

    try:
        # ── Idempotency check ─────────────────────────────────────────────────
        existing = await conn.fetchrow(
            "SELECT id, email, totp_verified_at FROM super_admins WHERE email = $1",
            email,
        )

        if existing:
            print(f"  ⚠  Super admin already exists: {existing['email']} ({existing['id']})")
            if existing["totp_verified_at"] is None:
                print("     TOTP setup is NOT complete. Log in to complete setup:")
            else:
                print("     TOTP is fully configured. Account is ready.")
            print("     Login at: /super-admin/auth/login")
            print()
            return

        # ── Hash password (slow-bcrypt with cost factor 12) ─────────────────
        print("  Hashing password (this takes ~2 seconds)...")
        hashed = hash_password(password)

        # ── Insert the super admin ────────────────────────────────────────────
        # totp_secret and totp_verified_at are NULL by design.
        # The TOTP setup flow runs on first login.
        row = await conn.fetchrow(
            """
            INSERT INTO super_admins (email, hashed_password, full_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (email) DO NOTHING
            RETURNING id, email, full_name, created_at
            """,
            email,
            hashed,
            full_name,
        )

        if row is None:
            # Extremely unlikely race condition: someone created the account
            # between our check above and the INSERT.
            print(f"  ⚠  Race condition: account for '{email}' was created by another process.")
            print("     Run the script again to verify.")
            return

        print()
        print("  ✓  Super admin created successfully!")
        print()
        print(f"     ID:         {row['id']}")
        print(f"     Email:      {row['email']}")
        print(f"     Full name:  {row['full_name']}")
        print(f"     Created at: {row['created_at'].isoformat()}")
        print()
        print("  NEXT STEPS:")
        print("  1. Log in at:  POST /super-admin/auth/login")
        print("  2. Scan the QR code:  POST /super-admin/auth/totp/setup")
        print("  3. Verify the code:   POST /super-admin/auth/totp/verify")
        print()
        print("  IMPORTANT: Keep your authenticator device safe.")
        print("  If lost, TOTP reset requires direct database access by Fred:")
        print("    UPDATE super_admins")
        print("    SET totp_secret = NULL, totp_verified_at = NULL")
        print(f"   WHERE email = '{email}';")
        print()

    finally:
        await conn.close()

    print("=" * 60)
    print()


if __name__ == "__main__":
    asyncio.run(seed_super_admin())
