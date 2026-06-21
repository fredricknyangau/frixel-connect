# scripts/test_hardening.py
import asyncio
import os
import sys
import hashlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import asyncpg
from app.config import settings
from app.core.security import hash_password
from app.services.totp_service import generate_totp_secret, verify_totp_code
import pyotp

async def run_test():
    print("Connecting to DB...")
    conn = await asyncpg.connect(dsn=settings.DATABASE_URL)
    
    print("Initializing Redis...")
    from app.core.redis import init_redis, close_redis
    await init_redis()
    
    sa_id = None
    try:
        # 1. Clean up any existing test accounts
        await conn.execute("DELETE FROM super_admin_audit_log WHERE super_admin_id IN (SELECT id FROM super_admins WHERE email = $1)", "test_hardening@zealsync.com")
        await conn.execute("DELETE FROM super_admins WHERE email = $1", "test_hardening@zealsync.com")
        
        # 2. Create test super admin
        hashed = hash_password("TestPassword123!")
        sa_id = await conn.fetchval(
            """
            INSERT INTO super_admins (email, hashed_password, full_name, totp_secret, totp_verified_at)
            VALUES ($1, $2, $3, $4, NOW())
            RETURNING id
            """,
            "test_hardening@zealsync.com",
            hashed,
            "Test Hardening",
            None
        )
        print(f"Created test super admin with ID: {sa_id}")
        
        # Setup TOTP for it
        raw_secret = pyotp.random_base32()
        from app.services.totp_service import encrypt_totp_secret
        encrypted_secret = encrypt_totp_secret(raw_secret)
        await conn.execute(
            "UPDATE super_admins SET totp_secret = $1 WHERE id = $2",
            encrypted_secret,
            sa_id
        )
        print("TOTP secret configured.")
        
        # 3. Create a pre-auth token
        from app.modules.super_admin import service
        ip = "1.2.3.4"
        res = await service.authenticate_password(conn, "test_hardening@zealsync.com", "TestPassword123!", ip)
        pre_auth_token = res["pre_auth_token"]
        print(f"Pre-auth token generated: {pre_auth_token}")
        
        # 4. Try wrong TOTP 3 times
        print("\n--- Testing 3-strikes TOTP brute force lockout ---")
        for i in range(1, 4):
            try:
                print(f"Attempt {i}: submitting wrong code '000000'")
                await service.verify_totp(conn, pre_auth_token, "000000", ip)
                print(f"  Attempt {i} succeeded? This should not happen!")
            except Exception as exc:
                print(f"  Attempt {i} failed: {exc} (type: {type(exc).__name__})")
                if i == 3:
                    if "Session expired. Please log in again." in str(exc):
                        print("  ✓ Correctly received lockout exception on 3rd attempt.")
                    else:
                        print(f"  ✗ Unexpected exception message: {exc}")
                        
        # 5. Try 4th attempt
        print("\nAttempt 4: submitting code")
        try:
            await service.verify_totp(conn, pre_auth_token, "000000", ip)
            print("  Attempt 4 succeeded? This should not happen!")
        except Exception as exc:
            print(f"  Attempt 4 failed: {exc} (type: {type(exc).__name__})")
            if "Session expired. Please log in again." in str(exc):
                print("  ✓ Correctly received lockout exception on 4th attempt.")
            else:
                print(f"  ✗ Unexpected exception message: {exc}")
                
        # 6. Verify that the token is marked used in DB
        token_hash = hashlib.sha256(pre_auth_token.encode()).hexdigest()
        row = await conn.fetchrow("SELECT used_at FROM super_admin_pre_auth_tokens WHERE token_hash = $1", token_hash)
        if row and row["used_at"] is not None:
            print(f"  ✓ Token successfully marked used in database at {row['used_at']}")
        else:
            print("  ✗ Token is NOT marked used in database!")
            
        # 7. Check audit log has the correct IP address and failure logs
        logs = await conn.fetch(
            "SELECT action, metadata, ip_address FROM super_admin_audit_log WHERE super_admin_id = $1 ORDER BY created_at ASC",
            sa_id
        )
        print("\n--- Verifying Audit Log entries and IP logging ---")
        for l in logs:
            action_name = l['action']
            logged_ip = l['ip_address']
            meta = l['metadata']
            print(f"  Action: {action_name}, IP: {logged_ip}, Metadata: {meta}")
            if str(logged_ip) == ip:
                print("  ✓ Correct IP logged.")
            else:
                print(f"  ✗ Incorrect IP logged: {repr(logged_ip)} (expected: {repr(ip)})")
                
    finally:
        # Clean up
        if sa_id:
            await conn.execute("DELETE FROM super_admin_audit_log WHERE super_admin_id = $1", sa_id)
            await conn.execute("DELETE FROM super_admins WHERE id = $1", sa_id)
            print("\nDatabase cleaned up.")
        
        await close_redis()
        await conn.close()
        print("Connections closed.")

if __name__ == "__main__":
    asyncio.run(run_test())
