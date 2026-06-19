-- =============================================================================
-- Migration: 001_create_users.sql
-- Creates: users table
-- Depends on: nothing (this is the root table)
--
-- Every other table in this system has a FK to users, so this must be
-- the first migration applied.
-- =============================================================================

-- The uuid-ossp extension gives us uuid_generate_v4() for primary keys.
-- We use CREATE EXTENSION IF NOT EXISTS so re-running this file is safe.
-- Note: IF NOT EXISTS cannot be used on TABLE column constraints or CHECK
-- constraints -only on the CREATE TABLE statement and extensions.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS users (
    -- UUID primary key: harder to enumerate than serial integers.
    -- An attacker who knows customer ID 5 can try 4 and 6. With UUIDs they can't.
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    email            VARCHAR(255) NOT NULL,
    phone            VARCHAR(20)  NOT NULL,

    -- We never store the plain password -only the bcrypt hash.
    -- bcrypt hashes are always 60 chars. VARCHAR(255) gives room for future algo changes.
    hashed_password  VARCHAR(255) NOT NULL,

    -- role is an enum-like column enforced with a CHECK constraint.
    -- We use VARCHAR + CHECK instead of a PostgreSQL ENUM type because:
    --   1. Adding a value to a PG ENUM requires ALTER TYPE which locks the table.
    --   2. CHECK constraints are easier to modify without downtime.
    role             VARCHAR(20)  NOT NULL DEFAULT 'customer'
                         CHECK (role IN ('admin', 'reseller', 'customer')),

    -- Self-referential FK: a customer's reseller_id points to a reseller's id.
    -- A reseller's reseller_id points to the admin (or is NULL for the top admin).
    -- ON DELETE SET NULL: if a reseller is deleted, their customers become parentless
    -- rather than being cascade-deleted (we never hard-delete in this system anyway).
    reseller_id      UUID REFERENCES users(id) ON DELETE SET NULL,

    is_active        BOOLEAN NOT NULL DEFAULT TRUE,

    -- timezone: we store ALL timestamps as UTC. The application layer converts
    -- to Africa/Nairobi (UTC+3) only for display purposes.
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- UNIQUE constraints at the DB layer are the last line of defence.
    -- Even if application code has a bug that lets duplicates through,
    -- PostgreSQL will reject them here.
    CONSTRAINT users_email_unique UNIQUE (email),
    CONSTRAINT users_phone_unique UNIQUE (phone)
);

-- ── Indexes ───────────────────────────────────────────────────────────────────
-- We add indexes on every column that appears in a WHERE clause in our routes.

-- /auth/login looks up users by email -the most frequent query in the system.
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

-- /reseller/customers filters customers by reseller_id.
CREATE INDEX IF NOT EXISTS idx_users_reseller_id ON users (reseller_id);

-- Role filtering for /admin/users?role=customer
CREATE INDEX IF NOT EXISTS idx_users_role ON users (role);

-- Phone lookups: Daraja callbacks include a phone number that we match back to a customer.
CREATE INDEX IF NOT EXISTS idx_users_phone ON users (phone);
