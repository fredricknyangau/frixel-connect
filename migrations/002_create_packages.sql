-- =============================================================================
-- Migration: 002_create_packages.sql
-- Creates: packages table
-- Depends on: 001_create_users.sql (references users.id for created_by)
-- =============================================================================

CREATE TABLE IF NOT EXISTS packages (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    name          VARCHAR(100) NOT NULL,
    description   TEXT,

    -- NUMERIC(10,2): exact decimal arithmetic. NEVER use FLOAT for money.
    -- FLOAT uses binary floating point: 50.1 stored as 50.09999999... in binary.
    -- NUMERIC stores the decimal value exactly.
    -- 10,2 means: up to 10 total digits, 2 after the decimal point.
    -- Max value: 99,999,999.99 KES -enough for any ISP package.
    price_kes     NUMERIC(10, 2) NOT NULL CHECK (price_kes > 0),

    duration_days INTEGER        NOT NULL CHECK (duration_days > 0),

    -- speed_mbps: integer is fine -nobody sells 10.5 Mbps plans.
    speed_mbps    INTEGER        NOT NULL CHECK (speed_mbps > 0),

    -- Soft delete: we never hard-delete packages because payments and
    -- vouchers reference package_id. Hard deletion would orphan those records
    -- and break financial history queries.
    is_active     BOOLEAN        NOT NULL DEFAULT TRUE,

    -- Which admin created this package. NULL if the admin account is deleted
    -- (unlikely in practice, but we handle it defensively).
    created_by    UUID REFERENCES users(id) ON DELETE SET NULL,

    created_at    TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    -- Package names must be unique -prevents accidentally creating "Daily 10Mbps" twice.
    CONSTRAINT packages_name_unique UNIQUE (name)
);

-- ── Indexes ───────────────────────────────────────────────────────────────────

-- GET /packages returns only active packages -this index makes that filter fast.
-- Without this index, PostgreSQL scans every row to check is_active.
CREATE INDEX IF NOT EXISTS idx_packages_is_active ON packages (is_active);

-- ORDER BY price_kes ASC on the packages list endpoint -this index supports the sort.
CREATE INDEX IF NOT EXISTS idx_packages_price ON packages (price_kes);
