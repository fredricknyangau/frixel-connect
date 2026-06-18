-- =============================================================================
-- Migration: 015_create_platform_billing.sql
-- Creates: platform_payments table
-- Alters: tenants (adds next_billing_date)
-- =============================================================================

ALTER TABLE tenants
ADD COLUMN IF NOT EXISTS next_billing_date TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '1 month';

-- For existing tenants, make their next_billing_date their created_at + 1 month.
-- If created_at + 1 month is in the past, they will be billed immediately on the next cron run.
UPDATE tenants 
SET next_billing_date = created_at + INTERVAL '1 month'
WHERE next_billing_date IS NULL;

CREATE TABLE IF NOT EXISTS platform_payments (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Which tenant this payment belongs to.
    tenant_id             UUID          NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,

    -- The amount charged for the platform fee based on their subscription tier.
    amount_kes            NUMERIC(10, 2) NOT NULL CHECK (amount_kes > 0),

    -- Status: pending, confirmed, failed, cancelled
    status                VARCHAR(20)   NOT NULL DEFAULT 'pending'
                              CHECK (status IN ('pending', 'confirmed', 'failed', 'cancelled')),

    -- Daraja fields
    mpesa_receipt_number  VARCHAR(20)   UNIQUE,
    mpesa_checkout_id     VARCHAR(100),
    phone_number          VARCHAR(20)   NOT NULL,
    failure_reason        TEXT,

    created_at            TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_platform_payments_tenant_id ON platform_payments (tenant_id);
CREATE INDEX IF NOT EXISTS idx_platform_payments_checkout_id ON platform_payments (mpesa_checkout_id);
CREATE INDEX IF NOT EXISTS idx_platform_payments_status ON platform_payments (status);
