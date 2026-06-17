-- =============================================================================
-- Migration: 004_create_vouchers.sql
-- Creates: vouchers table
-- Depends on: 001_create_users.sql, 002_create_packages.sql, 003_create_payments.sql
-- =============================================================================

CREATE TABLE IF NOT EXISTS vouchers (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- One payment produces exactly one voucher — enforced by UNIQUE.
    -- If a payment has two vouchers, a customer got free internet. That is bad.
    payment_id   UUID NOT NULL REFERENCES payments(id) ON DELETE RESTRICT,
    CONSTRAINT   vouchers_payment_id_unique UNIQUE (payment_id),

    -- Denormalised for fast lookup: "show me all vouchers for this customer"
    -- without needing to JOIN through payments.
    customer_id  UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,

    -- The package the voucher grants access to.
    package_id   UUID NOT NULL REFERENCES packages(id) ON DELETE RESTRICT,

    -- The actual credential the customer enters on the hotspot login page.
    -- This becomes BOTH the username AND password in MikroTik (explained in
    -- the MikroTik client code). Must be globally unique.
    -- VARCHAR(50) UNIQUE — MikroTik username has limits, 50 is safe.
    code         VARCHAR(50) NOT NULL,
    CONSTRAINT   vouchers_code_unique UNIQUE (code),

    -- Voucher lifecycle:
    -- active           → generated, pushed to MikroTik, ready to use
    -- used             → customer connected and time ran out (set by sync job)
    -- expired          → expires_at passed without being used
    -- revoked          → admin manually revoked (hotspot user deleted from MikroTik)
    -- pending_provision → MikroTik was unreachable when voucher was generated.
    --                    Payment is confirmed, voucher is in DB, but MikroTik
    --                    doesn't know about it yet. Admin must manually provision.
    status       VARCHAR(25) NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active', 'used', 'expired', 'revoked', 'pending_provision')),

    -- When the customer first used this voucher on the hotspot login page.
    -- NULL until first use.
    activated_at TIMESTAMPTZ,

    -- When this voucher expires (activated_at + package.duration_days).
    -- NULL until activated (we don't know the expiry until they first connect).
    expires_at   TIMESTAMPTZ,

    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Indexes ───────────────────────────────────────────────────────────────────

-- GET /vouchers/me — customer fetches their own vouchers.
CREATE INDEX IF NOT EXISTS idx_vouchers_customer_id ON vouchers (customer_id);

-- Code lookups: MikroTik may pass back the username when a session starts.
-- Also used in the revoke flow to find the voucher by code.
CREATE INDEX IF NOT EXISTS idx_vouchers_code ON vouchers (code);

-- Status filtering: "show me all pending_provision vouchers" for admin retry dashboard.
CREATE INDEX IF NOT EXISTS idx_vouchers_status ON vouchers (status);

-- GET /reseller/vouchers — filter by package to see which plans are most popular.
CREATE INDEX IF NOT EXISTS idx_vouchers_package_id ON vouchers (package_id);
