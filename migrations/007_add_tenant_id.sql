-- =============================================================================
-- Migration: 007_add_tenant_id.sql
-- Adds tenant_id to: users, packages, payments, vouchers, sessions
-- Depends on: 006_create_tenants.sql
--
-- WHY NOT JUST ADD NOT NULL DIRECTLY?
--   Every existing row in users, packages, payments, vouchers, and sessions
--   was inserted before this column existed, so tenant_id is unknown for them.
--   PostgreSQL refuses to add a NOT NULL column to a non-empty table without a
--   DEFAULT that fills in existing rows, because it cannot leave rows with a
--   NULL value in a NOT NULL column -that's a constraint violation.
--
--   The correct three-step pattern for adding NOT NULL to a populated table:
--     1. ADD COLUMN ... NULL          -succeeds immediately, existing rows get NULL
--     2. UPDATE ... SET tenant_id = ? -backfills all existing rows to a real value
--     3. ALTER COLUMN ... SET NOT NULL -now safe because no NULLs remain
--
--   Running ALTER SET NOT NULL before the backfill UPDATE would fail with:
--     ERROR: column "tenant_id" of relation "users" contains null values
--
-- THE DEFAULT TENANT:
--   We create one tenant row that represents "the original single-tenant ISP"
--   -the business that was running before multi-tenancy existed. Every row
--   seeded by seed_db.py (admin, reseller, customer, packages) is backfilled
--   to this tenant's ID. After the backfill and the NOT NULL promotion, the
--   migration is complete and the system behaves as multi-tenant from this
--   point forward.
-- =============================================================================

BEGIN;

-- ── Step 0: Create the default tenant ────────────────────────────────────────
-- This represents the original single ISP that the MLP served.
-- We pin the ID as a fixed UUID so we can reference it in backfill UPDATEs below.
-- INSERT ... ON CONFLICT DO NOTHING makes this migration re-runnable safely:
-- if it already ran once, the tenant row exists and we skip.
INSERT INTO tenants (
    id,
    business_name,
    owner_email,
    owner_phone,
    subscription_tier,
    max_customers,
    status
)
VALUES (
    'aaaaaaaa-0000-0000-0000-000000000001',
    'Default ISP (ZealSync MLP)',
    'admin@zealsync.dev',        -- matches seed_db.py ADMIN_EMAIL
    '254700000001',              -- matches seed_db.py admin phone
    'enterprise',
    99999,
    'active'
)
ON CONFLICT (owner_email) DO NOTHING;


-- ── Step 1: ADD COLUMN NULL (safe on populated tables) ───────────────────────

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE RESTRICT;

ALTER TABLE packages
    ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE RESTRICT;

ALTER TABLE payments
    ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE RESTRICT;

ALTER TABLE vouchers
    ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE RESTRICT;

ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE RESTRICT;


-- ── Step 2: Backfill existing rows ────────────────────────────────────────────
-- Every row created before this migration belongs to the default tenant.
-- WHERE tenant_id IS NULL limits the UPDATE to rows that haven't been assigned
-- yet -makes re-running idempotent (second run touches 0 rows).

UPDATE users    SET tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
UPDATE packages SET tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
UPDATE payments SET tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
UPDATE vouchers SET tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
UPDATE sessions SET tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;


-- ── Step 3: Promote columns to NOT NULL ───────────────────────────────────────
-- This step is safe ONLY after the backfill above has run.
-- PostgreSQL does a full table scan here to verify no NULLs remain.
-- On large tables this takes seconds and acquires ACCESS EXCLUSIVE;
-- in production you'd use a NOT VALID constraint + VALIDATE separately.
-- For our current table sizes this is fine.

ALTER TABLE users    ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE packages ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE payments ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE vouchers ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE sessions ALTER COLUMN tenant_id SET NOT NULL;


-- ── Step 4: Composite indexes ──────────────────────────────────────────────────
-- Every table that the dashboard queries by status also now needs (tenant_id, status)
-- because all WHERE clauses will prefix with tenant_id. A standalone idx_xxx_status
-- index is no longer selective enough -PostgreSQL would still scan the full index
-- range for a tenant's rows before filtering by status.

-- users: is_active used for active customer count in Phase 10
CREATE INDEX IF NOT EXISTS idx_users_tenant_id             ON users    (tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_tenant_is_active      ON users    (tenant_id, is_active);
CREATE INDEX IF NOT EXISTS idx_users_tenant_created_at     ON users    (tenant_id, created_at DESC);

-- packages: status = is_active; dashboard sorts by recency and filters actives
CREATE INDEX IF NOT EXISTS idx_packages_tenant_id          ON packages (tenant_id);
CREATE INDEX IF NOT EXISTS idx_packages_tenant_is_active   ON packages (tenant_id, is_active);
CREATE INDEX IF NOT EXISTS idx_packages_tenant_created_at  ON packages (tenant_id, created_at DESC);

-- payments: dashboard filters by status and sorts by recency constantly
CREATE INDEX IF NOT EXISTS idx_payments_tenant_id          ON payments (tenant_id);
CREATE INDEX IF NOT EXISTS idx_payments_tenant_status      ON payments (tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_payments_tenant_created_at  ON payments (tenant_id, created_at DESC);

-- vouchers: dashboard filters by status (pending_provision, active, revoked)
CREATE INDEX IF NOT EXISTS idx_vouchers_tenant_id          ON vouchers (tenant_id);
CREATE INDEX IF NOT EXISTS idx_vouchers_tenant_status      ON vouchers (tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_vouchers_tenant_created_at  ON vouchers (tenant_id, created_at DESC);

-- sessions: dashboard shows active sessions (ended_at IS NULL) per tenant
CREATE INDEX IF NOT EXISTS idx_sessions_tenant_id          ON sessions (tenant_id);
CREATE INDEX IF NOT EXISTS idx_sessions_tenant_created_at  ON sessions (tenant_id, created_at DESC);

COMMIT;
