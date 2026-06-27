import pytest
from uuid import uuid4
from asyncpg import Connection
from app.modules.invoices.service import generate_invoice_for_payment

@pytest.mark.asyncio
async def test_invoice_generation_and_tenant_isolation(conn: Connection):
    """
    Verifies that:
    1. generate_invoice_for_payment creates an invoice with a mock KRA QR code and PDF.
    2. invoice_number increments independently per tenant.
    """
    
    # 1. Setup Data for Tenant 1 (Default Tenant)
    tenant1_id = "aaaaaaaa-0000-0000-0000-000000000001"
    customer1_id = await conn.fetchval(
        "SELECT id FROM users WHERE email = 'customer@zealsync.dev'"
    )
    package_id = "11111111-1111-1111-1111-111111111111"
    
    # Create two payments for Tenant 1
    payment1_id = await conn.fetchval("""
        INSERT INTO payments (tenant_id, customer_id, package_id, amount_kes, status, mpesa_receipt_number, phone_number)
        VALUES ($1, $2, $3, 50, 'confirmed', 'T1PAY1', '254700000001')
        RETURNING id
    """, tenant1_id, customer1_id, package_id)
    
    payment2_id = await conn.fetchval("""
        INSERT INTO payments (tenant_id, customer_id, package_id, amount_kes, status, mpesa_receipt_number, phone_number)
        VALUES ($1, $2, $3, 50, 'confirmed', 'T1PAY2', '254700000001')
        RETURNING id
    """, tenant1_id, customer1_id, package_id)
    
    # 2. Setup Data for Tenant 2
    tenant2_id = str(uuid4())
    await conn.execute("""
        INSERT INTO tenants (id, business_name, owner_email, owner_phone, subscription_tier, status)
        VALUES ($1, 'Tenant 2', 't2@zealsync.dev', '254700000009', 'starter', 'active')
    """, tenant2_id)
    
    customer2_id = await conn.fetchval("""
        INSERT INTO users (email, phone, hashed_password, role, tenant_id)
        VALUES ($1, $2, 'hash', 'customer', $3)
        RETURNING id
    """, "c2@zealsync.dev", "254700000010", tenant2_id)
    
    package2_id = await conn.fetchval("""
        INSERT INTO packages (name, price_kes, duration_minutes, speed_mbps, tenant_id)
        VALUES ('T2Pkg', 100, 1440, 5, $1)
        RETURNING id
    """, tenant2_id)
    
    payment3_id = await conn.fetchval("""
        INSERT INTO payments (tenant_id, customer_id, package_id, amount_kes, status, mpesa_receipt_number, phone_number)
        VALUES ($1, $2, $3, 100, 'confirmed', 'T2PAY1', '254700000010')
        RETURNING id
    """, tenant2_id, customer2_id, package2_id)
    
    # 3. Generate Invoices
    await generate_invoice_for_payment(conn, payment1_id)
    await generate_invoice_for_payment(conn, payment2_id)
    await generate_invoice_for_payment(conn, payment3_id)
    
    # 4. Verify Tenant 1 Invoices (should be 1 and 2)
    t1_invoices = await conn.fetch("""
        SELECT invoice_number, kra_etims_qr_code, pdf_path 
        FROM invoices 
        WHERE tenant_id = $1 
        ORDER BY invoice_number ASC
    """, tenant1_id)
    
    assert len(t1_invoices) == 2
    assert t1_invoices[0]["invoice_number"] == 1
    assert t1_invoices[1]["invoice_number"] == 2
    
    # Verify mock KRA details were populated
    assert t1_invoices[0]["kra_etims_qr_code"] is not None
    assert "MOCK-SIGN" in t1_invoices[0]["kra_etims_qr_code"]
    assert "https://" in t1_invoices[0]["kra_etims_qr_code"]
    assert t1_invoices[0]["pdf_path"].endswith(".pdf")
    
    # 5. Verify Tenant 2 Invoices (should be 1)
    t2_invoices = await conn.fetch("""
        SELECT invoice_number 
        FROM invoices 
        WHERE tenant_id = $1
    """, tenant2_id)
    
    assert len(t2_invoices) == 1
    assert t2_invoices[0]["invoice_number"] == 1  # Independent sequence!
