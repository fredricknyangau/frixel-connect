import asyncio
import pyotp
import asyncpg
import sys
import os

# Allow running from project root
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app.config import settings
from app.modules.super_admin import service
from app.services.totp_service import decrypt_totp_secret

async def test_flow():
    # 1. Connect to the database
    conn = await asyncpg.connect(dsn=settings.DATABASE_URL)
    
    email = "superadmin@Frixel Connect.com"
    password = "Frixel ConnectAdmin2026!"
    ip_address = "127.0.0.1"

    print("Step 1: Authenticating password...")
    try:
        # Reset TOTP first to ensure a clean state
        await conn.execute("UPDATE super_admins SET totp_secret = NULL, totp_verified_at = NULL WHERE email = $1", email)
        
        auth_res = await service.authenticate_password(conn, email, password, ip_address)
        print("✓ Password auth successful.")
        print(f"Pre-auth token: {auth_res['pre_auth_token']}")
        print(f"TOTP Setup Required: {auth_res['totp_setup_required']}")
        
        pre_auth_token = auth_res['pre_auth_token']
        
        # 2. Setup TOTP
        print("\nStep 2: Setting up TOTP...")
        setup_res = await service.setup_totp(conn, pre_auth_token)
        print("✓ TOTP setup successful.")
        print(f"Secret Preview: {setup_res['secret_preview']}")
        
        # Fetch the actual secret from database to generate current TOTP code
        row = await conn.fetchrow(
            "SELECT totp_secret FROM super_admins WHERE email = $1",
            email
        )
        encrypted_secret = row['totp_secret']
        raw_secret = decrypt_totp_secret(encrypted_secret)
        
        # Generate the TOTP code using pyotp
        totp = pyotp.TOTP(raw_secret)
        code = totp.now()
        print(f"Generated TOTP Code: {code}")
        
        # 3. Verify TOTP
        print("\nStep 3: Verifying TOTP...")
        verify_res = await service.verify_totp(conn, pre_auth_token, code, ip_address)
        print("✓ TOTP verification successful.")
        print(f"Access Token: {verify_res.access_token[:30]}...")
        print(f"Super Admin Name: {verify_res.full_name}")
        
        # 4. Verify lockout (3 wrong TOTP codes invalidates the pre-auth token)
        print("\nStep 4: Testing brute-force protection...")
        # Get a fresh pre-auth token
        auth_res2 = await service.authenticate_password(conn, email, password, ip_address)
        pat2 = auth_res2['pre_auth_token']
        
        # We try 3 wrong codes
        print("Attempting with wrong TOTP codes...")
        for i in range(3):
            try:
                await service.verify_totp(conn, pat2, "000000", ip_address)
            except Exception as e:
                print(f"Attempt {i+1} failed as expected: {e}")
                
        # The 4th attempt or verifying with the correct code should fail because the token is now locked/used
        try:
            correct_code = totp.now()
            await service.verify_totp(conn, pat2, correct_code, ip_address)
            print("✗ Lockout failed! Token is still valid.")
        except Exception as e:
            print(f"✓ Lockout successful! Token is locked/invalidated: {e}")
            
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(test_flow())
