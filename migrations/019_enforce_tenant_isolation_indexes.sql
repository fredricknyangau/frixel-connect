-- =============================================================================
-- Migration: 019_enforce_tenant_isolation_indexes.sql
-- Depends on: 007_add_tenant_id.sql, 009_create_routers.sql,
--             010_create_wallet_transactions.sql, 012_create_subscriptions.sql,
--             014_create_security_tables.sql, 018_create_super_admins.sql
--
-- OBJECTIVE (Phase 1-Database Layer Audit and Hardening):
--   1. Enforce NOT NULL on tenant_id across all tenant-scoped data tables.
--   2. Add composite (tenant_id, filter_column) indexes that match actual
--      service-layer query patterns so every tenant-scoped lookup resolves
--      in a single index scan-not a seq scan with a post-filter on tenant_id.
--   3. Document why PostgreSQL Row Level Security (RLS) is deferred to v3.
--
-- NOTE ON MIGRATION NUMBER:
--   The audit spec references 018 for this file, but 018_create_super_admins.sql
--   already exists. This migration is numbered 019 to preserve lexicographic order.
--
-- =============================================================================
-- 1B: ROW-LEVEL SECURITY (RLS)-ADVISORY, NOT IMPLEMENTED
-- =============================================================================
-- PostgreSQL Row Level Security (RLS) can enforce tenant isolation at the
-- database driver level: even if application code omits WHERE tenant_id = $1,
-- the database rejects rows that do not match the session's tenant context.
--
-- WHY RLS IS NOT IMPLEMENTED IN THIS PHASE:
--
--   1. CONNECTION POOL CONTAMINATION
--      RLS requires SET app.tenant_id = '<uuid>' before each query.
--      asyncpg's connection pool reuses connections across requests. A
--      connection that served Tenant A and returns to the pool without
--      clearing the session variable could serve Tenant B's query with A's
--      RLS context-a catastrophic cross-tenant data leak at the DB layer.
--
--   2. CONNECTION LIFECYCLE COMPLEXITY
--      Mitigating (1) requires checkout/checkin hooks on every pool connection
--      to SET and RESET session variables. This adds significant complexity
--      and introduces a new failure mode: a missed RESET on connection return
--      silently poisons the pool for all subsequent tenants.
--
--   3. APPLICATION-LEVEL ENFORCEMENT IS THE PRIMARY DEFENSE
--      This audit implements tenant_id scoping in dependencies, service
--      functions, and background jobs. Application-level enforcement is the
--      correct primary defense because it is explicit, testable, and visible
--      in code review. RLS is a secondary safety net, not a substitute.
--
--   4. V3 CONSIDERATION
--      When the codebase is stable enough to safely add connection lifecycle
--      hooks (checkout: SET app.tenant_id; checkin: RESET app.tenant_id), RLS
--      policies can be added as defense-in-depth. Track as a v3 item.
--
-- =============================================================================

BEGIN;

-- Default tenant ID from migration 007-used to backfill any orphaned NULL rows
-- before promoting columns to NOT NULL. Safe because migration 007 already
-- backfilled all pre-existing rows; this is a safety net for edge cases.
DO $$
DECLARE
    default_tenant UUID := 'aaaaaaaa-0000-0000-0000-000000000001';
BEGIN
    -- Ensure the default tenant exists (idempotent)
    INSERT INTO tenants (id, business_name, owner_email, owner_phone, subscription_tier, max_customers, status)
    VALUES (default_tenant, 'Default ISP (ZealSync MLP)', 'admin@zealsync.dev', '254700000001', 'enterprise', 99999, 'active')
    ON CONFLICT (owner_email) DO NOTHING;

    -- Backfill any NULL tenant_id rows before NOT NULL promotion
    UPDATE users               SET tenant_id = default_tenant WHERE tenant_id IS NULL;
    UPDATE packages            SET tenant_id = default_tenant WHERE tenant_id IS NULL;
    UPDATE payments            SET tenant_id = default_tenant WHERE tenant_id IS NULL;
    UPDATE vouchers            SET tenant_id = default_tenant WHERE tenant_id IS NULL;
    UPDATE sessions            SET tenant_id = default_tenant WHERE tenant_id IS NULL;
    UPDATE routers             SET tenant_id = default_tenant WHERE tenant_id IS NULL;
    UPDATE wallet_transactions SET tenant_id = default_tenant WHERE tenant_id IS NULL;
    UPDATE subscriptions       SET tenant_id = default_tenant WHERE tenant_id IS NULL;
    UPDATE audit_log           SET tenant_id = default_tenant WHERE tenant_id IS NULL;
END $$;


-- =============================================================================
-- STEP 1: Enforce NOT NULL on tenant_id across all tenant-scoped tables
-- =============================================================================
-- WHY: A nullable tenant_id allows rows to exist outside any tenant boundary.
--      Application code that forgets to filter tenant_id could return or mutate
--      orphaned rows. NOT NULL makes "every row belongs to exactly one tenant"
--      a database invariant, not just an application convention.
--
-- Idempotent: ALTER SET NOT NULL on an already-NOT-NULL column is a no-op.

ALTER TABLE users               ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE packages            ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE payments            ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE vouchers            ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE sessions            ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE routers             ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE wallet_transactions ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE subscriptions       ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE audit_log           ALTER COLUMN tenant_id SET NOT NULL;


-- =============================================================================
-- STEP 2: Composite indexes-users
-- =============================================================================

-- Query: GET /admin/users?role=customer
--        SELECT ... FROM users WHERE tenant_id = $1 AND role = 'customer'
-- Threat: Without (tenant_id, role), PostgreSQL scans all users for the tenant
--         then filters by role-or uses a single-column role index across ALL
--         tenants, leaking cross-tenant scan cost and enabling timing attacks.
CREATE INDEX IF NOT EXISTS idx_users_tenant_role
    ON users (tenant_id, role);

-- Query: POST /auth/login-email lookup scoped to tenant after registration
--        SELECT ... FROM users WHERE tenant_id = $1 AND email = $2
-- Threat: T1-login must not resolve a user from another tenant with the same
--         email address. Composite index ensures tenant boundary is checked first.
CREATE INDEX IF NOT EXISTS idx_users_tenant_email
    ON users (tenant_id, email);

-- Query: GET /reseller/customers-reseller customer list
--        SELECT ... FROM users WHERE tenant_id = $1 AND reseller_id = $2
-- Threat: T1-reseller must not enumerate customers from another tenant by
--         iterating reseller_id without a tenant_id prefix in the index.
CREATE INDEX IF NOT EXISTS idx_users_tenant_reseller_id
    ON users (tenant_id, reseller_id);

-- Query: Dashboard active customer count
--        SELECT COUNT(*) FROM users WHERE tenant_id = $1 AND is_active = TRUE
-- Threat: Dashboard stats must not scan inactive users across the full table.
-- Note: idx_users_tenant_is_active may already exist from migration 007.
CREATE INDEX IF NOT EXISTS idx_users_tenant_is_active
    ON users (tenant_id, is_active);


-- =============================================================================
-- STEP 2: Composite indexes-packages
-- =============================================================================

-- Query: GET /packages-active packages for tenant
--        SELECT ... FROM packages WHERE tenant_id = $1 AND is_active = TRUE
-- Threat: T1-package list must never include another tenant's packages.
-- Note: idx_packages_tenant_is_active may already exist from migration 007.
CREATE INDEX IF NOT EXISTS idx_packages_tenant_is_active
    ON packages (tenant_id, is_active);

-- Query: Admin package list ordered by recency
--        SELECT ... FROM packages WHERE tenant_id = $1 ORDER BY created_at DESC
-- Note: idx_packages_tenant_created_at may already exist from migration 007.
CREATE INDEX IF NOT EXISTS idx_packages_tenant_created_at
    ON packages (tenant_id, created_at DESC);


-- =============================================================================
-- STEP 2: Composite indexes-payments
-- =============================================================================

-- Query: Dashboard payment counts by status
--        SELECT COUNT(*) FROM payments WHERE tenant_id = $1 AND status = $2
-- Threat: T1-admin dashboard must not aggregate payments across tenants.
-- Note: idx_payments_tenant_status may already exist from migration 007.
CREATE INDEX IF NOT EXISTS idx_payments_tenant_status
    ON payments (tenant_id, status);

-- Query: GET /payments-recent payments list
--        SELECT ... FROM payments WHERE tenant_id = $1 ORDER BY created_at DESC
-- Note: idx_payments_tenant_created_at may already exist from migration 007.
CREATE INDEX IF NOT EXISTS idx_payments_tenant_created_at
    ON payments (tenant_id, created_at DESC);

-- Query: GET /payments/me-customer payment history
--        SELECT ... FROM payments WHERE tenant_id = $1 AND customer_id = $2
-- Threat: T1-customer must not see payment records from another tenant even
--         if they guess a valid customer_id UUID from another ISP.
CREATE INDEX IF NOT EXISTS idx_payments_tenant_customer_id
    ON payments (tenant_id, customer_id);

-- Query: POST /webhooks/daraja-M-Pesa callback lookup
--        SELECT ... FROM payments WHERE mpesa_checkout_id = $1
--        (Phase 3 adds: AND tenant_id = $2 for defense-in-depth)
-- Threat: T2-webhook replay must resolve the payment within the correct
--         tenant boundary. Composite index supports tenant-scoped webhook lookup
--         and prevents cross-tenant checkout_id collision scans.
CREATE INDEX IF NOT EXISTS idx_payments_tenant_mpesa_checkout_id
    ON payments (tenant_id, mpesa_checkout_id);


-- =============================================================================
-- STEP 2: Composite indexes-vouchers
-- =============================================================================

-- Query: Dashboard active voucher count
--        SELECT COUNT(*) FROM vouchers WHERE tenant_id = $1 AND status = 'active'
-- Note: idx_vouchers_tenant_status may already exist from migration 007.
CREATE INDEX IF NOT EXISTS idx_vouchers_tenant_status
    ON vouchers (tenant_id, status);

-- Query: GET /vouchers/me-customer voucher list
--        SELECT ... FROM vouchers WHERE tenant_id = $1 AND customer_id = $2
-- Threat: T1-customer must not retrieve vouchers belonging to another tenant.
CREATE INDEX IF NOT EXISTS idx_vouchers_tenant_customer_id
    ON vouchers (tenant_id, customer_id);

-- Query: Hotspot voucher redemption lookup
--        SELECT ... FROM vouchers WHERE tenant_id = $1 AND code = $2
-- Threat: T4 (partial)-voucher code lookup must be scoped to tenant before
--         RADIUS tenant scoping is fully implemented in Phase 5.
CREATE INDEX IF NOT EXISTS idx_vouchers_tenant_code
    ON vouchers (tenant_id, code);


-- =============================================================================
-- STEP 2: Composite indexes-sessions
-- =============================================================================

-- Query: GET /sessions/me-customer session history
--        SELECT ... FROM sessions WHERE tenant_id = $1 AND customer_id = $2
-- Threat: T1-session history must not leak across tenant boundaries.
CREATE INDEX IF NOT EXISTS idx_sessions_tenant_customer_id
    ON sessions (tenant_id, customer_id);

-- Query: Admin recent sessions dashboard
--        SELECT ... FROM sessions WHERE tenant_id = $1 ORDER BY started_at DESC
-- Threat: T1-admin session list must not include sessions from other ISPs.
CREATE INDEX IF NOT EXISTS idx_sessions_tenant_started_at
    ON sessions (tenant_id, started_at DESC);


-- =============================================================================
-- STEP 2: Composite indexes-routers
-- =============================================================================

-- Query: Dashboard online router check
--        SELECT ... FROM routers WHERE tenant_id = $1 AND status = 'online'
-- Note: idx_routers_tenant_status may already exist from migration 009.
CREATE INDEX IF NOT EXISTS idx_routers_tenant_status
    ON routers (tenant_id, status);

-- Query: Router name uniqueness check during create/update
--        SELECT id FROM routers WHERE tenant_id = $1 AND name = $2
-- Note: routers_tenant_name_unique UNIQUE (tenant_id, name) from migration 009
--       already creates an index on (tenant_id, name). No additional index needed.


-- =============================================================================
-- STEP 2: Composite indexes-wallet_transactions
-- =============================================================================

-- Query: GET /wallet/transactions-reseller wallet history
--        SELECT ... FROM wallet_transactions WHERE tenant_id = $1 AND reseller_id = $2
-- Threat: T1-reseller wallet history must not include transactions from
--         another tenant's resellers, even with a valid reseller_id UUID.
CREATE INDEX IF NOT EXISTS idx_wallet_transactions_tenant_reseller_id
    ON wallet_transactions (tenant_id, reseller_id);


-- =============================================================================
-- STEP 2: Composite indexes-subscriptions
-- =============================================================================

-- Query: Subscription billing cron-active subscriptions per tenant
--        SELECT ... FROM subscriptions WHERE tenant_id = $1 AND status = 'active'
-- Threat: T3-billing cron must process subscriptions tenant-by-tenant,
--         never mixing Tenant A's renewals with Tenant B's package prices.
CREATE INDEX IF NOT EXISTS idx_subscriptions_tenant_status
    ON subscriptions (tenant_id, status);

-- Query: GET /subscriptions/me-customer subscription lookup
--        SELECT ... FROM subscriptions WHERE tenant_id = $1 AND customer_id = $2
-- Threat: T1-customer must not see another tenant's subscription details.
CREATE INDEX IF NOT EXISTS idx_subscriptions_tenant_customer_id
    ON subscriptions (tenant_id, customer_id);

-- Query: Subscription expiry cron-subscriptions due for renewal
--        SELECT ... FROM subscriptions
--        WHERE tenant_id = $1 AND status = 'active'
--          AND current_period_end <= NOW()
-- Threat: T3-expiry cron must not suspend or renew subscriptions across tenants.
CREATE INDEX IF NOT EXISTS idx_subscriptions_tenant_period_end
    ON subscriptions (tenant_id, current_period_end);


-- =============================================================================
-- STEP 2: Composite indexes-audit_log
-- =============================================================================

-- Query: GET /audit-log-admin audit log, newest first
--        SELECT ... FROM audit_log WHERE tenant_id = $1 ORDER BY created_at DESC
-- Threat: T1-audit log must never expose another tenant's admin actions.
CREATE INDEX IF NOT EXISTS idx_audit_log_tenant_created_at
    ON audit_log (tenant_id, created_at DESC);

-- Query: GET /audit-log?action=revoked_voucher-action filter
--        SELECT ... FROM audit_log WHERE tenant_id = $1 AND action = $2
-- Threat: T7-filtered audit queries must not scan audit entries from all tenants.
CREATE INDEX IF NOT EXISTS idx_audit_log_tenant_action
    ON audit_log (tenant_id, action);

COMMIT;
