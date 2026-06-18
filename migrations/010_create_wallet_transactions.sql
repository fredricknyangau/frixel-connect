-- =============================================================================
-- Migration: 010_create_wallet_transactions.sql
-- Creates: wallet_transactions table, adds wallet_reference to users
-- Depends on: 009_router_id.sql
-- =============================================================================

-- 1. Add wallet_reference column to users table if it does not exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'users'
          AND column_name = 'wallet_reference'
    ) THEN
        ALTER TABLE users ADD COLUMN wallet_reference VARCHAR(50);
        ALTER TABLE users ADD CONSTRAINT users_wallet_reference_unique UNIQUE (wallet_reference);
    END IF;
END $$;

-- Create index for faster wallet_reference lookups
CREATE INDEX IF NOT EXISTS idx_users_wallet_reference ON users (wallet_reference);

-- 2. Populate default unique reference for any existing reseller that has none
UPDATE users
SET wallet_reference = 'WS' || UPPER(substring(md5(id::text || random()::text) from 1 for 5))
WHERE role = 'reseller' AND wallet_reference IS NULL;

-- 3. Create append-only wallet transactions ledger table
CREATE TABLE IF NOT EXISTS wallet_transactions (
    sequence_id    BIGSERIAL,
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id      UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    reseller_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type           VARCHAR(20) NOT NULL CHECK (type IN ('topup', 'debit', 'adjustment')),
    amount_kes     NUMERIC(10,2) NOT NULL,
    balance_after  NUMERIC(10,2) NOT NULL,
    reference      VARCHAR(100) NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT wallet_transactions_reference_unique UNIQUE (reference)
);

-- Ensure sequence_id exists on wallet_transactions (handles retrofitting)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'wallet_transactions'
          AND column_name = 'sequence_id'
    ) THEN
        ALTER TABLE wallet_transactions ADD COLUMN sequence_id BIGSERIAL;
    END IF;
END $$;

-- Index for querying transaction ledger history
CREATE INDEX IF NOT EXISTS idx_wallet_transactions_reseller_id ON wallet_transactions (reseller_id);
CREATE INDEX IF NOT EXISTS idx_wallet_transactions_sequence_id ON wallet_transactions (sequence_id);

