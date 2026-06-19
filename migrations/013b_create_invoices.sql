-- =============================================================================
-- Migration: 013_create_invoices.sql
-- Creates: invoices table and per-tenant sequence trigger
-- Depends on: 012_create_subscriptions.sql
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    payment_id UUID NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
    invoice_number INTEGER NOT NULL,
    kra_etims_qr_code TEXT,
    pdf_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, invoice_number),
    UNIQUE (payment_id)
);

CREATE INDEX IF NOT EXISTS idx_invoices_tenant_id ON invoices(tenant_id);
CREATE INDEX IF NOT EXISTS idx_invoices_created_at ON invoices(created_at);

-- Trigger to generate a gapless, sequential invoice number per tenant
CREATE OR REPLACE FUNCTION set_tenant_invoice_number()
RETURNS TRIGGER AS $$
BEGIN
    -- Acquire row-level lock on the tenant to serialize inserts and prevent race conditions
    PERFORM 1 FROM tenants WHERE id = NEW.tenant_id FOR UPDATE;
    
    SELECT COALESCE(MAX(invoice_number), 0) + 1
    INTO NEW.invoice_number
    FROM invoices
    WHERE tenant_id = NEW.tenant_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_set_invoice_number ON invoices;
CREATE TRIGGER trg_set_invoice_number
BEFORE INSERT ON invoices
FOR EACH ROW
WHEN (NEW.invoice_number IS NULL)
EXECUTE FUNCTION set_tenant_invoice_number();

COMMIT;
