import os
import uuid
import logging
import qrcode
from io import BytesIO
from asyncpg.connection import Connection
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from fastapi import HTTPException, status

from app.integrations.etims import etims_client

logger = logging.getLogger(__name__)

# Project root directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
INVOICES_DIR = os.path.join(BASE_DIR, "storage", "invoices")

async def _generate_pdf(
    invoice_number: int,
    tenant_name: str,
    tenant_pin: str,
    customer_phone: str,
    package_name: str,
    amount: int,
    kra_qr_url: str,
    kra_sign: str
) -> str:
    """
    Generates a PDF invoice and saves it to a static directory.
    Returns the file path.
    """
    os.makedirs(INVOICES_DIR, exist_ok=True)
    pdf_filename = f"INV-{invoice_number}-{uuid.uuid4().hex[:6]}.pdf"
    pdf_path = os.path.join(INVOICES_DIR, pdf_filename)
    
    c = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4
    
    # Title
    c.setFont("Helvetica-Bold", 24)
    c.drawString(50, height - 50, f"TAX INVOICE")
    
    # Tenant Info
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 90, tenant_name)
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 110, f"PIN: {tenant_pin}")
    
    # Invoice Details
    c.setFont("Helvetica-Bold", 12)
    c.drawString(350, height - 90, f"Invoice Number: {invoice_number}")
    c.drawString(350, height - 110, f"Customer: {customer_phone}")
    
    # Items Header
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 160, "Description")
    c.drawString(450, height - 160, "Amount (KES)")
    c.line(50, height - 165, 500, height - 165)
    
    # Items
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 190, f"WiFi Subscription - {package_name}")
    c.drawString(450, height - 190, f"{amount}.00")
    
    # Totals
    c.line(50, height - 210, 500, height - 210)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(350, height - 230, "Total:")
    c.drawString(450, height - 230, f"{amount}.00")
    
    # KRA Details
    if kra_qr_url:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, 150, "KRA eTIMS Compliance")
        c.setFont("Helvetica", 8)
        c.drawString(50, 135, f"Signature: {kra_sign}")
        
        # Draw QR Code
        qr = qrcode.QRCode(version=1, box_size=4, border=1)
        qr.add_data(kra_qr_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert PIL image to format ReportLab can read
        img_buffer = BytesIO()
        img.save(img_buffer, format="PNG")
        img_buffer.seek(0)
        
        c.drawImage(ImageReader(img_buffer), 50, 30, width=80, height=80)
        
    c.save()
    return pdf_path

async def generate_invoice_for_payment(conn: Connection, payment_id: str) -> None:
    """
    Creates an invoice for a completed payment, calls eTIMS, and generates a PDF.
    This runs in a background task (idempotent).
    """
    # 1. Fetch payment, tenant, and package details
    row = await conn.fetchrow("""
        SELECT p.id as payment_id, p.tenant_id, p.amount_kes as amount, p.status,
               t.business_name as tenant_name, t.owner_email,
               u.phone as customer_phone,
               pkg.name as package_name
        FROM payments p
        JOIN tenants t ON p.tenant_id = t.id
        JOIN users u ON p.customer_id = u.id
        JOIN packages pkg ON p.package_id = pkg.id
        WHERE p.id = $1
    """, payment_id)

    if not row:
        logger.error(f"Invoice generation failed: Payment {payment_id} not found.")
        return
        
    if row["status"] != "confirmed":
        logger.warning(f"Cannot generate invoice: Payment {payment_id} is not confirmed.")
        return
        
    # 2. Check if invoice already exists
    existing = await conn.fetchrow(
        "SELECT id, invoice_number FROM invoices WHERE payment_id = $1", 
        payment_id
    )
    if existing:
        logger.info(f"Invoice already exists for payment {payment_id}.")
        return
        
    # 3. Create initial invoice record to get the per-tenant invoice_number
    # The database trigger `trg_set_invoice_number` will populate invoice_number.
    invoice_row = await conn.fetchrow("""
        INSERT INTO invoices (tenant_id, payment_id)
        VALUES ($1, $2)
        RETURNING id, invoice_number
    """, row["tenant_id"], payment_id)
    
    invoice_id = invoice_row["id"]
    invoice_number = invoice_row["invoice_number"]
    
    # 4. Call eTIMS API
    # In a real setup, TIN and BHF ID would come from a `tenant_etims_configs` table.
    # For now, we use a placeholder TIN and BHF ID for the sandbox.
    tenant_tin = "P000000000A"
    tenant_bhf_id = "00"
    
    try:
        etims_result = await etims_client.submit_invoice(
            tin=tenant_tin,
            bhf_id=tenant_bhf_id,
            invoice_number=invoice_number,
            amount=row["amount"],
            package_name=row["package_name"]
        )
        
        qr_url = etims_result.get("qrCodeUrl", "")
        kra_sign = etims_result.get("rcptSign", "")
        kra_qr_code_data = f"{kra_sign}|{qr_url}"
        
    except Exception as e:
        logger.error(f"eTIMS submission failed for payment {payment_id}: {e}")
        # Even if eTIMS fails, we generated the internal invoice number.
        # A robust system would enqueue a retry task for eTIMS submission specifically.
        # For simplicity, we continue and leave kra_etims_qr_code as NULL.
        qr_url = ""
        kra_sign = ""
        kra_qr_code_data = None
        
    # 5. Generate PDF
    pdf_path = await _generate_pdf(
        invoice_number=invoice_number,
        tenant_name=row["tenant_name"],
        tenant_pin=tenant_tin,
        customer_phone=row["customer_phone"],
        package_name=row["package_name"],
        amount=row["amount"],
        kra_qr_url=qr_url,
        kra_sign=kra_sign
    )
    
    # 6. Update invoice record with QR code and PDF path
    await conn.execute("""
        UPDATE invoices
        SET kra_etims_qr_code = $1, pdf_path = $2
        WHERE id = $3
    """, kra_qr_code_data, pdf_path, invoice_id)
    
    logger.info(f"Successfully generated invoice {invoice_number} for payment {payment_id}")

async def get_invoice_by_id(conn: Connection, invoice_id: str, tenant_id: str):
    row = await conn.fetchrow("""
        SELECT i.*, p.amount_kes,
               CASE WHEN i.pdf_path IS NULL THEN NULL ELSE '/invoices/' || i.id::text || '/pdf' END AS pdf_url
        FROM invoices i
        JOIN payments p ON i.payment_id = p.id
        WHERE i.id = $1 AND i.tenant_id = $2
    """, invoice_id, tenant_id)
    
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return dict(row)

async def list_invoices(conn: Connection, tenant_id: str):
    rows = await conn.fetch("""
        SELECT i.*, p.amount_kes,
               CASE WHEN i.pdf_path IS NULL THEN NULL ELSE '/invoices/' || i.id::text || '/pdf' END AS pdf_url
        FROM invoices i
        JOIN payments p ON i.payment_id = p.id
        WHERE i.tenant_id = $1
        ORDER BY i.created_at DESC
    """, tenant_id)
    return [dict(r) for r in rows]


async def list_customer_invoices(conn: Connection, tenant_id: str, customer_id: str):
    rows = await conn.fetch("""
        SELECT i.*, p.amount_kes,
               CASE WHEN i.pdf_path IS NULL THEN NULL ELSE '/invoices/' || i.id::text || '/pdf' END AS pdf_url
        FROM invoices i
        JOIN payments p ON i.payment_id = p.id
        WHERE i.tenant_id = $1
          AND p.tenant_id = $1
          AND p.customer_id = $2
        ORDER BY i.created_at DESC
    """, tenant_id, customer_id)
    return [dict(r) for r in rows]


async def get_customer_invoice_by_id(conn: Connection, invoice_id: str, tenant_id: str, customer_id: str):
    row = await conn.fetchrow("""
        SELECT i.*, p.amount_kes,
               CASE WHEN i.pdf_path IS NULL THEN NULL ELSE '/invoices/' || i.id::text || '/pdf' END AS pdf_url
        FROM invoices i
        JOIN payments p ON i.payment_id = p.id
        WHERE i.id = $1
          AND i.tenant_id = $2
          AND p.tenant_id = $2
          AND p.customer_id = $3
    """, invoice_id, tenant_id, customer_id)

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return dict(row)
