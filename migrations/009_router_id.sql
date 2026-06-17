-- =============================================================================
-- Migration: 009_router_id.sql
-- Adds: router_id column to vouchers and users tables
-- Depends on: 009_create_routers.sql
--
-- DESCRIPTION:
--   Associates customers (users table) and vouchers with the specific router
--   they are connected to or provisioned on.
-- =============================================================================

BEGIN;

-- Add router_id to vouchers (nullable, as a router might be deleted or not yet assigned)
ALTER TABLE vouchers
    ADD COLUMN IF NOT EXISTS router_id UUID REFERENCES routers(id) ON DELETE SET NULL;

-- Add router_id to users (nullable, for customers assigned to a specific site/router)
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS router_id UUID REFERENCES routers(id) ON DELETE SET NULL;

-- Create indexes for performance on joins
CREATE INDEX IF NOT EXISTS idx_vouchers_router_id ON vouchers (router_id);
CREATE INDEX IF NOT EXISTS idx_users_router_id ON users (router_id);

COMMIT;
