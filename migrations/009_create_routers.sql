-- =============================================================================
-- Migration: 009_create_routers.sql
-- Creates: routers table
-- Depends on: 006_create_tenants.sql
--
-- DESCRIPTION:
--   Creates the routers table to store per-tenant MikroTik router credentials,
--   site associations, online/offline status, and heartbeat timestamps.
--   Passwords must be stored encrypted using Fernet (AES-128-CBC + HMAC-SHA256).
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS routers (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id          UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name               VARCHAR(100) NOT NULL,
    host               VARCHAR(255) NOT NULL,
    port               INTEGER NOT NULL DEFAULT 80,
    username           VARCHAR(100) NOT NULL,
    password_encrypted TEXT NOT NULL,
    site_name          VARCHAR(100) NOT NULL,
    status             VARCHAR(20) NOT NULL DEFAULT 'unknown'
                           CHECK (status IN ('online', 'offline', 'unknown')),
    last_heartbeat_at  TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Unique constraint: A tenant cannot have two routers with the same name.
    CONSTRAINT routers_tenant_name_unique UNIQUE (tenant_id, name)
);

-- Index for querying routers per tenant quickly
CREATE INDEX IF NOT EXISTS idx_routers_tenant_status ON routers (tenant_id, status);

COMMIT;
