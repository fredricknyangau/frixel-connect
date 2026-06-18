from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

class InvoiceResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    payment_id: UUID
    invoice_number: int
    kra_etims_qr_code: Optional[str] = None
    pdf_path: Optional[str] = None
    created_at: datetime
