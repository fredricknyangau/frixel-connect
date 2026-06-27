-- =============================================================================
-- Migration: 020_radius_tenant_scoping.sql
-- Adds tenant_id to FreeRADIUS tables for multi-tenant auth isolation (T4).
-- Depends on: 011_create_radius_tables.sql, 006_create_tenants.sql
-- =============================================================================

BEGIN;

ALTER TABLE radcheck
  ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);

ALTER TABLE radreply
  ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);

ALTER TABLE radacct
  ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);

CREATE INDEX IF NOT EXISTS idx_radcheck_tenant_username ON radcheck (tenant_id, username);
CREATE INDEX IF NOT EXISTS idx_radreply_tenant_username ON radreply (tenant_id, username);
CREATE INDEX IF NOT EXISTS idx_radacct_tenant_username ON radacct (tenant_id, username);

COMMIT;
