-- =============================================================================
-- Migration: 016_add_wireguard_columns.sql
-- Description: Add wireguard columns, update status check constraints, and make
--              connection details nullable to support pending routers.
-- =============================================================================

BEGIN;

-- Add wireguard columns if not present
ALTER TABLE routers
  ADD COLUMN IF NOT EXISTS wireguard_public_key TEXT,
  ADD COLUMN IF NOT EXISTS wireguard_assigned_ip INET,
  ADD COLUMN IF NOT EXISTS wireguard_peer_public_key TEXT;

-- Drop existing status check constraint if it exists
ALTER TABLE routers
  DROP CONSTRAINT IF EXISTS routers_status_check;

-- Recreate check constraint to allow 'pending_setup' and 'testing'
ALTER TABLE routers
  ADD CONSTRAINT routers_status_check CHECK (
    status IN ('online', 'offline', 'unknown', 'pending_setup', 'testing')
  );

-- Make connection fields nullable to support PENDING setup state
ALTER TABLE routers
  ALTER COLUMN host DROP NOT NULL,
  ALTER COLUMN port DROP NOT NULL,
  ALTER COLUMN username DROP NOT NULL,
  ALTER COLUMN password_encrypted DROP NOT NULL;

COMMIT;
