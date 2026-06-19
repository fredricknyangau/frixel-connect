from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.database import get_db
from app.dependencies import require_role
from app.modules.invoices.schemas import InvoiceResponse
from app.modules.invoices.service import (
    list_invoices,
    list_customer_invoices,
    get_invoice_by_id,
    get_customer_invoice_by_id,
)

router = APIRouter(tags=["invoices"])

@router.get("/admin/invoices", response_model=List[InvoiceResponse])
async def get_invoices(
    current_user: dict = Depends(require_role("admin")),
):
    """
    List all generated invoices for the tenant.
    """
    tenant_id = UUID(str(current_user["tenant_id"]))
    async with get_db() as conn:
        invoices = await list_invoices(conn, tenant_id)
        return invoices

@router.get("/invoices/me", response_model=List[InvoiceResponse])
async def get_my_invoices(
    current_user: dict = Depends(require_role("customer")),
):
    """List invoices for the authenticated customer only."""
    tenant_id = UUID(str(current_user["tenant_id"]))
    customer_id = UUID(str(current_user["user_id"]))
    async with get_db() as conn:
        invoices = await list_customer_invoices(conn, tenant_id, customer_id)
        return invoices


@router.get("/admin/invoices/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: str,
    current_user: dict = Depends(require_role("admin")),
):
    """
    Download the PDF file for a specific invoice.
    """
    tenant_id = UUID(str(current_user["tenant_id"]))
    async with get_db() as conn:
        invoice = await get_invoice_by_id(conn, invoice_id, tenant_id)
        
    pdf_path = invoice.get("pdf_path")
    if not pdf_path:
        raise HTTPException(status_code=404, detail="Invoice PDF not found")
        
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"invoice_{invoice['invoice_number']}.pdf"
    )


@router.get("/invoices/{invoice_id}/pdf")
async def download_invoice_pdf_scoped(
    invoice_id: str,
    current_user: dict = Depends(require_role("admin", "customer")),
):
    tenant_id = UUID(str(current_user["tenant_id"]))
    async with get_db() as conn:
        if current_user["role"] == "admin":
            invoice = await get_invoice_by_id(conn, invoice_id, tenant_id)
        else:
            invoice = await get_customer_invoice_by_id(
                conn,
                invoice_id,
                tenant_id,
                UUID(str(current_user["user_id"])),
            )

    pdf_path = invoice.get("pdf_path")
    if not pdf_path:
        raise HTTPException(status_code=404, detail="Invoice PDF not found")

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"invoice_{invoice['invoice_number']}.pdf"
    )
