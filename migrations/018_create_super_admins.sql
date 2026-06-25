-- =============================================================================
-- Migration: 018_create_super_admins.sql
-- Creates:   super_admins, super_admin_pre_auth_tokens, super_admin_audit_log
--
-- DESIGN RATIONALE-WHY A SEPARATE TABLE (NOT A ROLE IN users):
--   1. users.tenant_id is NOT NULL in practice-super admin belongs to no tenant.
--      Adding NULL carve-outs everywhere would be error-prone and leak surface area.
--   2. Every service function scopes queries by tenant_id; mixing super admin into
--      that table would require guarding every query against the super_admin case.
--   3. Super admin has distinct security requirements: TOTP mandatory, 15-min
--      access tokens, no refresh tokens, audit on reads.
--   4. Simpler operational story: DELETE super_admin touches no tenant data.
--
-- TOTP SECRET STORAGE:
--   totp_secret is stored Fernet-encrypted (same key as router credentials).
--   Even if the DB is compromised, the attacker still needs the FERNET_SECRET_KEY
--   to derive the TOTP secrets and bypass MFA.
--   totp_secret = NULL means TOTP setup is incomplete-account cannot fully log in.
--   totp_verified_at = NULL after totp_secret is set means the QR was generated
--   but the user has not yet scanned and verified a valid code.
--
-- RECOVERY NOTE (DOCUMENTED BY DESIGN):
--   If a super admin loses their authenticator app, there is NO self-service
--   recovery path. Recovery requires direct DB intervention by Fred:
--     UPDATE super_admins
--     SET totp_secret = NULL, totp_verified_at = NULL
--     WHERE email = 'lost@example.com';
--   This resets the account to "TOTP setup required" state.
--   The next login attempt will restart the QR code setup flow.
-- =============================================================================

BEGIN;

-- ── 1. Super Admins ────────────────────────────────────────────────────────────
-- Stores ZealSync operator identities. Intentionally NOT linked to any tenant.
-- Credentials here belong to Zeal Digital Solutions employees / Fred himself.

CREATE TABLE IF NOT EXISTS super_admins (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

    email            VARCHAR(255) UNIQUE NOT NULL,
    hashed_password  TEXT         NOT NULL,
    full_name        VARCHAR(100) NOT NULL,

    -- Fernet-encrypted pyotp Base32 secret (NULL until first-login TOTP setup).
    -- Encrypt with app.core.security.encrypt_secret() before storing.
    -- Decrypt with app.core.security.decrypt_secret() only at verify time.
    totp_secret      TEXT,

    -- Set to NOW() when the super admin first verifies a valid TOTP code.
    -- NULL = TOTP setup is still incomplete; login is blocked at the TOTP
    -- verify step with a clear "please complete setup" message.
    totp_verified_at TIMESTAMPTZ,

    is_active        BOOLEAN     NOT NULL DEFAULT TRUE,
    last_login_at    TIMESTAMPTZ,

    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Hot path: every login attempt does a lookup by email.
CREATE INDEX IF NOT EXISTS idx_super_admins_email
    ON super_admins(email);


-- ── 2. Pre-Auth Tokens ────────────────────────────────────────────────────────
-- Step-1 tokens: issued after successful password check, before TOTP validation.
-- These are NOT access tokens. They cannot call any protected endpoint.
-- They are single-use (used_at IS NOT NULL → rejected) and short-lived (5 min).
--
-- WHY HASH THE TOKEN?
--   If the tokens table is leaked (e.g. SQL injection dump), the attacker gets
--   only SHA256 hashes-they cannot reverse a pre-auth token without already
--   knowing the raw value. The raw token lives only in the HTTP response body
--   (in flight over TLS) and the client's memory.

CREATE TABLE IF NOT EXISTS super_admin_pre_auth_tokens (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

    super_admin_id UUID        NOT NULL
                       REFERENCES super_admins(id) ON DELETE CASCADE,

    -- SHA256(raw_token) stored as a hex string. Never store the raw token.
    token_hash     TEXT        NOT NULL UNIQUE,

    -- 5 minutes is intentionally short. The super admin must complete TOTP
    -- verification within this window. If expired, they restart from login.
    expires_at     TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '5 minutes',

    -- NULL = unused and valid (assuming not expired).
    -- Timestamp = consumed; any further use is rejected.
    used_at        TIMESTAMPTZ,

    -- Stored for audit purposes-which IP address requested this pre-auth token?
    ip_address     INET,

    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ── 3. Super Admin Audit Log ──────────────────────────────────────────────────
-- SEPARATE from the tenant-scoped audit_log table.
-- Reasons:
--   a) tenant audit_log has a tenant_id FK-super admin has no tenant_id.
--   b) tenant audit_log data belongs to ISP tenants; mixing in super admin
--      actions would make it impossible to isolate tenant audit exports.
--   c) Different retention requirements: super admin actions are ZealSync's
--      own compliance record, not the ISP's.
--
-- Every super admin action (including reads) is logged here.
-- Action naming convention: 'domain.verb'
--   Examples: 'auth.password_ok', 'tenant.suspend', 'impersonation.start',
--             'impersonation.api_call', 'tenant.list', 'super_admin.create'

CREATE TABLE IF NOT EXISTS super_admin_audit_log (
    id             UUID         PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Who performed the action.
    super_admin_id UUID         NOT NULL
                       REFERENCES super_admins(id),

    -- Domain-qualified event name: 'tenant.suspend', 'auth.login_success', etc.
    action         VARCHAR(100) NOT NULL,

    -- What kind of entity was acted upon: 'tenant', 'super_admin', 'system'
    target_type    VARCHAR(50),

    -- UUID of the affected entity (tenant_id, super_admin_id, etc.)
    target_id      UUID,

    -- Structured supplementary data: {"reason": "...", "previous_status": "active"}
    -- JSONB enables indexed queries: WHERE metadata @> '{"tenant_id": "..."}'
    metadata       JSONB        NOT NULL DEFAULT '{}',

    -- Client IP for security forensics.
    ip_address     INET,

    -- Immutable timestamp. No updated_at-audit rows are never modified.
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Look up all actions by a specific operator (e.g. "what did Fred do today?")
CREATE INDEX IF NOT EXISTS idx_sa_audit_super_admin
    ON super_admin_audit_log(super_admin_id);

-- Time-range queries: "show me all audit events in the last 24 hours"
-- DESC so the most recent rows are the cheapest to retrieve.
CREATE INDEX IF NOT EXISTS idx_sa_audit_created_at
    ON super_admin_audit_log(created_at DESC);

-- Filter by action type: "show me all tenant suspensions"
CREATE INDEX IF NOT EXISTS idx_sa_audit_action
    ON super_admin_audit_log(action);

-- Filter by what was acted on: "show me everything that touched tenant X"
CREATE INDEX IF NOT EXISTS idx_sa_audit_target
    ON super_admin_audit_log(target_type, target_id);

COMMIT;
