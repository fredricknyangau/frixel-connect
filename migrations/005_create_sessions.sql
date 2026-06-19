-- =============================================================================
-- Migration: 005_create_sessions.sql
-- Creates: sessions table
-- Depends on: 001_create_users.sql, 004_create_vouchers.sql
--
-- NOTE: In v1, this table is populated manually or by a future MikroTik
-- accounting sync job -NOT by this API directly. MikroTik tracks active
-- sessions internally; we mirror that data here for billing dashboards.
-- =============================================================================

CREATE TABLE IF NOT EXISTS sessions (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Which voucher (and therefore which customer + package) this session belongs to.
    voucher_id        UUID         NOT NULL REFERENCES vouchers(id) ON DELETE RESTRICT,

    -- Denormalised for fast customer-facing lookups (GET /sessions/me).
    customer_id       UUID         NOT NULL REFERENCES users(id) ON DELETE RESTRICT,

    -- The physical network identifier of the customer's device.
    -- VARCHAR(17): MAC addresses are 17 chars in colon-hex notation (AA:BB:CC:DD:EE:FF).
    mac_address       VARCHAR(17),

    -- INET is a PostgreSQL native type for IPv4/IPv6 addresses.
    -- It validates the address format and supports subnet operators.
    -- Better than VARCHAR for IP addresses because you can do:
    --   WHERE ip_address << '192.168.1.0/24'  (subnet membership check)
    ip_address        INET,

    -- Traffic counters from MikroTik accounting.
    -- BIGINT because a 7-day session at 20Mbps can consume:
    --   20Mbps * 7 * 86400 = ~150 GB = ~161 billion bytes → needs BIGINT.
    bytes_uploaded    BIGINT NOT NULL DEFAULT 0,
    bytes_downloaded  BIGINT NOT NULL DEFAULT 0,

    -- When the customer's hotspot session started and ended.
    -- ended_at is NULL for currently active sessions.
    started_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at          TIMESTAMPTZ,

    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Indexes ───────────────────────────────────────────────────────────────────

-- GET /sessions/me -customer fetches their own sessions.
CREATE INDEX IF NOT EXISTS idx_sessions_customer_id ON sessions (customer_id);

-- Lookup all sessions for a specific voucher (e.g. to calculate total data used).
CREATE INDEX IF NOT EXISTS idx_sessions_voucher_id ON sessions (voucher_id);

-- Admin dashboard: filter active sessions (ended_at IS NULL).
-- This partial index only indexes rows where ended_at IS NULL,
-- making it tiny and fast for the "active sessions" query.
CREATE INDEX IF NOT EXISTS idx_sessions_active
    ON sessions (started_at)
    WHERE ended_at IS NULL;
