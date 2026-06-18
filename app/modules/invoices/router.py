from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.database import get_db_pool
from asyncpg.pool import Pool

from app.modules.auth.service import get_current_active_user
from app.modules.invoices.schemas import InvoiceResponse
from app.modules.invoices.service import list_invoices, get_invoice_by_id

router = APIRouter(prefix="/admin/invoices", tags=["invoices"])

@router.get("", response_model=List[InvoiceResponse])
async def get_invoices(
    current_user: dict = Depends(get_current_active_user),
    pool: Pool = Depends(get_db_pool),
):
    """
    List all generated invoices for the tenant.
    """
    tenant_id = current_user["tenant_id"]
    async with pool.acquire() as conn:
        invoices = await list_invoices(conn, tenant_id)
        return invoices

@router.get("/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: str,
    current_user: dict = Depends(get_current_active_user),
    pool: Pool = Depends(get_db_pool),
):
    """
    Download the PDF file for a specific invoice.
    """
    tenant_id = current_user["tenant_id"]
    async with pool.acquire() as conn:
        invoice = await get_invoice_by_id(conn, invoice_id, tenant_id)
        
    pdf_path = invoice.get("pdf_path")
    if not pdf_path:
        raise HTTPException(status_code=404, detail="Invoice PDF not found")
        
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"invoice_{invoice['invoice_number']}.pdf"
    )
