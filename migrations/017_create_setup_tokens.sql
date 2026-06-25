-- =============================================================================
-- Migration: 017_create_setup_tokens.sql
-- Description: Create setup_tokens table for the Magic Command router onboarding.
--
-- DESIGN RATIONALE:
--   The Magic Command system works by pre-generating a WireGuard keypair and
--   API credentials on the server, embedding them in a short-lived script, and
--   letting the router self-configure via a single terminal command.
--
--   The setup_tokens table stores this one-time bootstrap state:
--     - The token is the authentication mechanism for the public /setup/{token}
--       and /setup/{token}/confirm endpoints (no JWT needed-the token IS auth).
--     - router_wg_private_key is stored temporarily so the script can be
--       re-fetched if the download is interrupted. It is NULLed out the moment
--       the router calls /confirm, implementing zero-knowledge-after-setup.
--     - api_password is stored Fernet-encrypted (same pattern as router
--       password_encrypted column) so we can display the credential if needed
--       for debugging, without storing it in plaintext.
--
-- Depends on: 016_add_wireguard_columns.sql
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS setup_tokens (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Tenant and router this token belongs to. Both FKs ensure tokens are
    -- automatically cleaned up if the parent records are deleted (CASCADE).
    tenant_id               UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    router_id               UUID        NOT NULL REFERENCES routers(id) ON DELETE CASCADE,

    -- The actual secret token. URL-safe base64 (secrets.token_urlsafe(32))
    -- produces 43 characters of [A-Za-z0-9_-]. Safe in URLs and shell commands.
    -- UNIQUE enforces that no two tokens can collide even across tenants.
    token                   VARCHAR(64) NOT NULL UNIQUE,

    -- The WireGuard private key for this router, generated server-side.
    -- This enables the single-command UX: the script carries the private key
    -- so the router does not need to generate and exchange its own key.
    --
    -- SECURITY NOTE: This column is set to NULL immediately after the router
    -- calls POST /setup/{token}/confirm. From that point on, the server has
    -- zero knowledge of the router's private key.
    --
    -- The key is NOT Fernet-encrypted here because:
    --   1. It is already short-lived (24h expiry, single-use).
    --   2. The token itself provides access control-only the bearer of the
    --      URL-safe 43-character token can retrieve it.
    --   3. Adding Fernet encryption would require decrypting it on every
    --      script download request, adding latency with no security benefit
    --      since the token is the authentication barrier.
    router_wg_private_key   TEXT,

    -- The MikroTik REST API password for the zealsync-api user.
    -- Fernet-encrypted (same pattern as routers.password_encrypted) so we
    -- never store credentials in plaintext at rest.
    api_password            TEXT        NOT NULL,

    -- Token expires 24 hours after creation. Checked at the DATABASE level
    -- (WHERE expires_at > NOW()) to avoid clock skew between app server and DB.
    expires_at              TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '24 hours',

    -- NULL means the token has not been used yet.
    -- Set to the current timestamp when the router calls /confirm.
    -- Tokens with used_at IS NOT NULL are rejected immediately.
    used_at                 TIMESTAMPTZ,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Partial index: only index tokens that have NOT been used yet.
-- This is the hot path-every /setup/{token} request hits this index.
-- Once a token is used (used_at IS NOT NULL), it falls out of the index
-- and the query naturally returns 0 rows (filtered by AND used_at IS NULL).
-- This keeps the index small (active tokens only) and the lookup fast.
CREATE UNIQUE INDEX IF NOT EXISTS idx_setup_tokens_active
    ON setup_tokens(token)
    WHERE used_at IS NULL;

-- Standard index for the router_id FK-needed for efficient CASCADE deletes
-- and for looking up "does this router have a pending setup token?"
CREATE INDEX IF NOT EXISTS idx_setup_tokens_router_id
    ON setup_tokens(router_id);

COMMIT;
