-- =============================================================================
-- Migration: 011_create_radius_tables.sql
-- Creates: radcheck, radreply, radacct, radusergroup, radgroupcheck, radgroupreply, radpostauth tables
-- Alters: packages, sessions
-- Depends on: 010_create_wallet_transactions.sql
-- =============================================================================

BEGIN;

-- 1. Create standard FreeRADIUS tables

CREATE TABLE IF NOT EXISTS radcheck (
    id         SERIAL PRIMARY KEY,
    username   TEXT NOT NULL DEFAULT '',
    attribute  TEXT NOT NULL DEFAULT '',
    op         VARCHAR(2) NOT NULL DEFAULT '==',
    value      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_radcheck_username ON radcheck (username, attribute);

CREATE TABLE IF NOT EXISTS radreply (
    id         SERIAL PRIMARY KEY,
    username   TEXT NOT NULL DEFAULT '',
    attribute  TEXT NOT NULL DEFAULT '',
    op         VARCHAR(2) NOT NULL DEFAULT '=',
    value      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_radreply_username ON radreply (username, attribute);

CREATE TABLE IF NOT EXISTS radusergroup (
    id         SERIAL PRIMARY KEY,
    username   TEXT NOT NULL DEFAULT '',
    groupname  TEXT NOT NULL DEFAULT '',
    priority   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_radusergroup_username ON radusergroup (username);

CREATE TABLE IF NOT EXISTS radgroupcheck (
    id         SERIAL PRIMARY KEY,
    groupname  TEXT NOT NULL DEFAULT '',
    attribute  TEXT NOT NULL DEFAULT '',
    op         VARCHAR(2) NOT NULL DEFAULT '==',
    value      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_radgroupcheck_groupname ON radgroupcheck (groupname, attribute);

CREATE TABLE IF NOT EXISTS radgroupreply (
    id         SERIAL PRIMARY KEY,
    groupname  TEXT NOT NULL DEFAULT '',
    attribute  TEXT NOT NULL DEFAULT '',
    op         VARCHAR(2) NOT NULL DEFAULT '=',
    value      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_radgroupreply_groupname ON radgroupreply (groupname, attribute);

CREATE TABLE IF NOT EXISTS radpostauth (
    id         BIGSERIAL PRIMARY KEY,
    username   TEXT NOT NULL,
    pass       TEXT,
    reply      TEXT,
    authdate   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_radpostauth_username ON radpostauth (username);

CREATE TABLE IF NOT EXISTS radacct (
    radacctid           BIGSERIAL PRIMARY KEY,
    acctsessionid       TEXT NOT NULL,
    acctuniqueid        TEXT NOT NULL UNIQUE,
    username            TEXT,
    groupname           TEXT,
    realm               TEXT,
    nasipaddress        INET NOT NULL,
    nasportid           TEXT,
    nasporttype         TEXT,
    acctstarttime       TIMESTAMPTZ,
    acctupdatetime       TIMESTAMPTZ,
    acctstoptime        TIMESTAMPTZ,
    acctinterval        BIGINT,
    acctsessiontime     BIGINT,
    acctauthentic       TEXT,
    connectinfo_start   TEXT,
    connectinfo_stop    TEXT,
    acctinputoctets     BIGINT,
    acctoutputoctets    BIGINT,
    calledstationid     TEXT,
    callingstationid    TEXT,
    acctterminatecause  TEXT,
    servicetype         TEXT,
    framedprotocol      TEXT,
    framedipaddress     INET,
    framedipv6address   INET,
    framedipv6prefix    INET,
    framedinterfaceid   TEXT,
    delegatedipv6prefix INET,
    class               TEXT
);

CREATE INDEX IF NOT EXISTS idx_radacct_active_session_idx ON radacct (acctuniqueid) WHERE acctstoptime IS NULL;
CREATE INDEX IF NOT EXISTS idx_radacct_bulk_close ON radacct (nasipaddress, acctstarttime) WHERE acctstoptime IS NULL;
CREATE INDEX IF NOT EXISTS idx_radacct_username ON radacct (username);

-- 2. Alter existing application tables

-- Add acct_unique_id to sessions for session sync tracking
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sessions' AND column_name = 'acct_unique_id'
    ) THEN
        ALTER TABLE sessions ADD COLUMN acct_unique_id VARCHAR(50);
        ALTER TABLE sessions ADD CONSTRAINT sessions_acct_unique_id_unique UNIQUE (acct_unique_id);
    END IF;
END $$;

-- Add data_quota_mb to packages for FUP limit tracking
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'packages' AND column_name = 'data_quota_mb'
    ) THEN
        ALTER TABLE packages ADD COLUMN data_quota_mb INTEGER;
    END IF;
END $$;

COMMIT;
