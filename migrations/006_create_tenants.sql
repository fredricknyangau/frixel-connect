-- =============================================================================
-- Migration: 006_create_tenants.sql
-- Creates: tenants table
-- Depends on: nothing -tenants is the new root of the hierarchy.
--             Previously users was the root; from this migration onward
--             tenants sits ABOVE users.
--
-- WHAT A TENANT IS:
--   A tenant is one ISP business that subscribes to ZealSync.
--   Every user, package, payment, voucher, and session belongs to exactly
--   one tenant. Data belonging to tenant A is structurally invisible to
--   tenant B -not just filtered at the application layer, but unreachable
--   because every query requires a matching tenant_id.
-- =============================================================================

CREATE TABLE IF NOT EXISTS tenants (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- The ISP business name as they would display it to their own customers.
    -- e.g. "FastNet Kenya" or "Nairobi Digital ISP"
    business_name     VARCHAR(200) NOT NULL,

    -- The contact email and phone of the ISP owner (not their customers).
    -- This is who ZealSync bills for the platform subscription in Phase 10.
    owner_email       VARCHAR(255) NOT NULL,
    owner_phone       VARCHAR(20)  NOT NULL,

    -- ZealSync pricing tiers. Each tier maps to max_customers and feature gates.
    --   starter    →  up to 50  active customers
    --   growth     →  up to 500 active customers
    --   scale      →  up to 5,000 active customers
    --   enterprise →  unlimited (contract-based)
    -- We use VARCHAR + CHECK instead of a PG ENUM because adding a new tier
    -- to an ENUM requires ALTER TYPE which acquires an ACCESS EXCLUSIVE lock.
    -- CHECK constraints can be added without locking in Postgres 12+.
    subscription_tier VARCHAR(20) NOT NULL DEFAULT 'starter'
                          CHECK (subscription_tier IN ('starter', 'growth', 'scale', 'enterprise')),

    -- The ceiling on active customer accounts for this tenant.
    -- Set at signup based on subscription_tier; admin can override for enterprise.
    -- Phase 10 compares active customer count against this value.
    max_customers     INTEGER NOT NULL DEFAULT 50 CHECK (max_customers > 0),

    -- Tenant lifecycle:
    --   active    → normal operation; all endpoints available
    --   suspended → ZealSync's own invoice is unpaid past grace period (Phase 10)
    --               OR admin manually suspended due to abuse.
    --               Every login for every user under this tenant returns 403
    --               with a clear "account suspended" message.
    --   cancelled → tenant has offboarded; historical data retained for legal/audit.
    --               Login is blocked like suspended, but status is permanent.
    status            VARCHAR(20) NOT NULL DEFAULT 'active'
                          CHECK (status IN ('active', 'suspended', 'cancelled')),

    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Owner email uniqueness: one business owner signs up once.
    -- They can later add sub-admin users inside the platform.
    CONSTRAINT tenants_owner_email_unique UNIQUE (owner_email),
    CONSTRAINT tenants_owner_phone_unique UNIQUE (owner_phone)
);

-- ── Indexes ───────────────────────────────────────────────────────────────────

-- Phase 10 billing job: find all active tenants for monthly billing run.
CREATE INDEX IF NOT EXISTS idx_tenants_status ON tenants (status);

-- Lookup by owner_email during tenant login resolution (Phase 1 auth flow).
CREATE INDEX IF NOT EXISTS idx_tenants_owner_email ON tenants (owner_email);
