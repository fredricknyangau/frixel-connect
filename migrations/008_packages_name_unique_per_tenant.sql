-- =============================================================================
-- Migration: 008_packages_name_unique_per_tenant.sql
-- Depends on: 007_add_tenant_id.sql
--
-- PROBLEM THIS FIXES:
--   The original packages_name_unique constraint is:
--     CONSTRAINT packages_name_unique UNIQUE (name)
--   This is a GLOBAL constraint — "Daily 10Mbps" can exist only once
--   in the entire table, across all tenants. That was fine in the
--   single-tenant MLP, but in a multi-tenant system:
--     - ISP "Nairobi Fibre" wants a package called "Daily 10Mbps"
--     - ISP "Mombasa WiFi" also wants a package called "Daily 10Mbps"
--     - The second INSERT violates the constraint and fails
--   This is wrong. Each ISP should manage their own package names
--   independently.
--
-- THE FIX:
--   1. DROP the global constraint.
--   2. ADD a composite constraint on (tenant_id, name) — unique WITHIN
--      a tenant, but multiple tenants can reuse the same name.
--
-- WHY NOT DO THIS IN MIGRATION 007?
--   Migration 007 adds tenant_id first. A composite UNIQUE on
--   (tenant_id, name) requires tenant_id to exist in the table before
--   the constraint can be created. Running these as separate migrations
--   preserves the independence and re-runability of each file.
--
-- SAFETY:
--   DROP CONSTRAINT is a DDL operation that acquires ACCESS EXCLUSIVE
--   on the table. On a live production table with active traffic this
--   would block reads and writes for the duration. For our current
--   table size (<10,000 rows) this completes in milliseconds. For
--   large tables, the safe alternative is:
--     - Take a maintenance window, OR
--     - Use a NOT VALID constraint, validate offline, then promote.
-- =============================================================================

BEGIN;

-- Step 1: Remove the global unique constraint on name alone
ALTER TABLE packages
    DROP CONSTRAINT IF EXISTS packages_name_unique;

-- Step 2: Add a composite constraint — unique per (tenant, name)
--         An ISP cannot have two active packages with the same name,
--         but a different ISP can reuse any name freely.
ALTER TABLE packages
    ADD CONSTRAINT packages_tenant_name_unique UNIQUE (tenant_id, name);

COMMIT;
