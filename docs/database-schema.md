# Database Schema and Table Reference

This document serves as the data dictionary and migration reference manual for the PostgreSQL database structure of ZealSync.

---

## 1. Schema Entity-Relationship Map

The database architecture is designed with strict relational constraints and row-level multi-tenancy bounds. Below is the relational structure of the tables:

```text
                                  ┌───────────────┐
                                  │    tenants    │
                                  └──────┬────────┘
                                         │
        ┌──────────────┬─────────────────┼──────────────┬────────────────┐
        ▼              ▼                 ▼              ▼                ▼
 ┌─────────────┐┌──────────────┐ ┌─────────────┐┌──────────────┐┌─────────────────┐
 │   routers   ││   packages   │ │    users    ││ subscriptions││platform_payments│
 └──────┬──────┘└──────┬───────┘ └──────┬──────┘└──────────────┘└─────────────────┘
        │              │                │
        │              └────────┐ ┌──────┼──────────────┐
        │                       ▼ ▼      ▼              ▼
        │                ┌─────────────┐┌──────────────┐┌───────────────────┐
        │                │  payments   ││ refresh_token││wallet_transactions│
        │                └──────┬──────┘└──────────────┘└───────────────────┘
        │                       │
        ▼                       ▼
 ┌─────────────┐         ┌─────────────┐
 │  vouchers   │◄────────┤   invoices  │
 └──────┬──────┘         └─────────────┘
        │
        ▼
 ┌─────────────┐         ┌─────────────┐
 │  sessions   │◄────────┤   radacct   │
 └─────────────┘         └─────────────┘

 FreeRADIUS Auth tables:  [radcheck], [radreply], [radusergroup], [radgroupcheck], [radgroupreply], [radpostauth]
```

---

## 2. Database Migration Files

Migrations are executed in lexicographical order via `./scripts/run_migrations.sh`. Each script is designed for idempotency.

| File | Creates / Alters | Dependency Requirement |
| :--- | :--- | :--- |
| `001_create_users.sql` | `users` table, `uuid-ossp` extension, indices. | Root table (None). |
| `002_create_packages.sql` | `packages` table, soft delete flag, indices. | `001_create_users.sql` (References `users.id` for creator). |
| `003_create_payments.sql` | `payments` table, checks, unique receipt constraint. | `001_create_users` & `002_create_packages`. |
| `004_create_vouchers.sql` | `vouchers` table, unique payment mapping, code uniqueness. | `001_create_users`, `002_create_packages`, `003_create_payments`. |
| `005_create_sessions.sql` | `sessions` table (hotspot telemetry mirror). | `001_create_users` & `004_create_vouchers`. |
| `006_create_tenants.sql` | `tenants` table, subscription tier checks, indices. | None. |
| `007_add_tenant_id.sql` | Adds `tenant_id` to users, packages, payments, vouchers, sessions. Backfills default tenant ID (`aaaaaaaa-0000-0000-0000-000000000001`) and sets `NOT NULL`. | `006_create_tenants.sql`. |
| `008_packages_name_unique_per_tenant.sql` | Drops global `packages_name_unique` constraint and replaces it with composite unique constraint `(tenant_id, name)`. | `007_add_tenant_id.sql`. |
| `009_create_routers.sql` | `routers` table (AES credential storage, status heartbeats). | `006_create_tenants.sql`. |
| `009b_router_id.sql` | Adds `router_id` column to `vouchers` and `users` tables, indices. | `009_create_routers.sql`. |
| `010_create_wallet_transactions.sql` | Adds `wallet_reference` unique column to `users`, creates append-only ledger `wallet_transactions` table. | `009b_router_id.sql` / `001_create_users.sql`. |
| `011_create_radius_tables.sql` | `radcheck`, `radreply`, `radusergroup`, `radgroupcheck`, `radgroupreply`, `radpostauth`, `radacct` tables. Alters `sessions` adding `acct_unique_id`, `packages` adding `data_quota_mb`. | `010_create_wallet_transactions.sql`. |
| `012_create_subscriptions.sql` | `subscriptions` table (PPPoE recurring billing). | `007_add_tenant_id.sql`, `002_create_packages.sql`, `001_create_users.sql`. |
| `013_alter_packages_duration.sql` | Renames `duration_days` to `duration_minutes` in `packages` and scales existing records (1 day = 1440 mins). | `002_create_packages.sql`. |
| `013b_create_invoices.sql` | `invoices` table, trigger `trg_set_invoice_number` for sequential numbering. | `012_create_subscriptions.sql`. |
| `014_create_security_tables.sql` | `refresh_tokens` and `audit_log` tables. | `013b_create_invoices.sql`. |
| `015_create_platform_billing.sql` | Adds `next_billing_date` to `tenants`, creates `platform_payments` table for ZealSync monthly collection. | `006_create_tenants.sql`. |
| `016_add_wireguard_columns.sql` | Adds `wireguard_public_key`, `wireguard_assigned_ip`, `wireguard_peer_public_key` to `routers`, adjusts connection nullabilities. | `009_create_routers.sql`. |

---

## 3. Table Reference Directory

### tenants
* **Purpose**: Stores registered ISP business accounts subscribing to the SaaS platform.
* **Created in**: `006_create_tenants.sql` (Altered in `015_create_platform_billing.sql`)

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY`, `DEFAULT uuid_generate_v4()` | Unique tenant identifier. |
| `business_name` | `VARCHAR(200)` | `NOT NULL` | Registered trade name of the ISP. |
| `owner_email` | `VARCHAR(255)` | `NOT NULL`, `UNIQUE` | Contact email address of the business owner. |
| `owner_phone` | `VARCHAR(20)` | `NOT NULL`, `UNIQUE` | M-Pesa billing number (format: `2547XXXXXXXX`). |
| `subscription_tier` | `VARCHAR(20)` | `NOT NULL`, `DEFAULT 'starter'` | Limits tier (`starter`, `growth`, `scale`, `enterprise`). |
| `max_customers` | `INTEGER` | `NOT NULL`, `DEFAULT 50`, `CHECK (> 0)` | Maximum active customer accounts allowed. |
| `status` | `VARCHAR(20)` | `NOT NULL`, `DEFAULT 'active'` | State flags (`active`, `suspended`, `cancelled`). |
| `next_billing_date`| `TIMESTAMPTZ` | `NOT NULL`, `DEFAULT NOW() + 1 Month` | Due date for the next platform subscription charge. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, `DEFAULT NOW()` | Date of registration. |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL`, `DEFAULT NOW()` | Timestamp of last metadata update. |

* **Indexes**:
  * `idx_tenants_status` on `tenants(status)`: Speeds up cron task sweeps processing monthly dues.
  * `idx_tenants_owner_email` on `tenants(owner_email)`: Optimizes tenant login flow.

---

### users
* **Purpose**: Holds profiles for system operators, resellers, and end customers.
* **Created in**: `001_create_users.sql` (Altered in `007`, `009b`, `010`)

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY`, `DEFAULT uuid_generate_v4()` | Unique profile identifier. |
| `tenant_id` | `UUID` | `NOT NULL`, `REFERENCES tenants(id)` | Parent tenant context mapping. |
| `email` | `VARCHAR(255)` | `NOT NULL`, `UNIQUE` | Login address. |
| `phone` | `VARCHAR(20)` | `NOT NULL`, `UNIQUE` | Customer phone number for STK pushing. |
| `hashed_password` | `VARCHAR(255)` | `NOT NULL` | 60-character bcrypt hash string. |
| `role` | `VARCHAR(20)` | `NOT NULL`, `CHECK IN (admin, reseller, customer)` | Permissions enforcement flag. |
| `reseller_id` | `UUID` | `REFERENCES users(id) ON DELETE SET NULL` | Parent reseller mapping for credit billing. |
| `router_id` | `UUID` | `REFERENCES routers(id) ON DELETE SET NULL` | Fixed home router assignment for PPPoE/Hotspot. |
| `wallet_reference`| `VARCHAR(50)` | `UNIQUE` | Unique Paybill Account reference code (format: `WSXXXXX`). |
| `is_active` | `BOOLEAN` | `NOT NULL`, `DEFAULT TRUE` | Soft-disable user status toggle. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, `DEFAULT NOW()` | Creation timestamp. |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL`, `DEFAULT NOW()` | Profile updates timestamp. |

* **Indexes**:
  * `idx_users_email` on `users(email)`: Speeds up credentials checking at `/auth/login`.
  * `idx_users_reseller_id` on `users(reseller_id)`: Speeds up reseller-to-customer listing query.
  * `idx_users_phone` on `users(phone)`: Speeds up phone lookup matching incoming STK events.
  * `idx_users_tenant_is_active` on `users(tenant_id, is_active)`: Measures active limits.

---

### packages
* **Purpose**: Product packages dictating pricing, speed limits, and usage durations.
* **Created in**: `002_create_packages.sql` (Altered in `007`, `011`, `013`)

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY`, `DEFAULT uuid_generate_v4()` | Package identifier. |
| `tenant_id` | `UUID` | `NOT NULL`, `REFERENCES tenants(id)` | Tenant owner. |
| `name` | `VARCHAR(100)` | `NOT NULL` | Name of package (e.g. `Daily 10Mbps`). |
| `description` | `TEXT` | Nullable | Detail shown on purchase pages. |
| `price_kes` | `NUMERIC(10,2)`| `NOT NULL`, `CHECK (> 0)` | Accurate decimal price in Kenyan Shillings. |
| `duration_minutes`| `INTEGER` | `NOT NULL`, `CHECK (> 0)` | Session validity length in minutes. |
| `speed_mbps` | `INTEGER` | `NOT NULL`, `CHECK (> 0)` | Bandwidth throughput ceiling. |
| `data_quota_mb` | `INTEGER` | Nullable | FUP cap limit (triggers radius throttle). |
| `is_active` | `BOOLEAN` | `NOT NULL`, `DEFAULT TRUE` | Soft delete flag. |
| `created_by` | `UUID` | `REFERENCES users(id) ON DELETE SET NULL` | Creation admin user. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, `DEFAULT NOW()` | Date created. |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL`, `DEFAULT NOW()` | Date modified. |

* **Indexes**:
  * `packages_tenant_name_unique` (Composite Unique): `(tenant_id, name)` prevents name collisions within a tenant while allowing duplicates across tenants.
  * `idx_packages_tenant_is_active` on `packages(tenant_id, is_active)`: Filters available customer packages.

---

### payments
* **Purpose**: Records cash collection requests initiated via M-Pesa STK pushes.
* **Created in**: `003_create_payments.sql` (Altered in `007`)

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY`, `DEFAULT uuid_generate_v4()` | Transaction identifier. |
| `tenant_id` | `UUID` | `NOT NULL`, `REFERENCES tenants(id)` | Target tenant context. |
| `customer_id` | `UUID` | `NOT NULL`, `REFERENCES users(id) ON DELETE RESTRICT` | Paying client. |
| `package_id` | `UUID` | `NOT NULL`, `REFERENCES packages(id) ON DELETE RESTRICT` | Package purchased. |
| `amount_kes` | `NUMERIC(10,2)`| `NOT NULL`, `CHECK (> 0)` | Snapshotted price at time of purchase. |
| `status` | `VARCHAR(20)` | `NOT NULL`, `DEFAULT 'pending'` | States: `pending`, `confirmed`, `failed`, `cancelled`. |
| `mpesa_receipt_number`| `VARCHAR(20)`| `UNIQUE` (Confirmed payments) | Safaricom unique receipt code (format: `QHDXXXXXXXX`). |
| `mpesa_checkout_id`| `VARCHAR(100)`| Nullable | Safaricom STK checkout request ID. |
| `phone_number` | `VARCHAR(20)` | `NOT NULL` | Phone receiving push prompt. |
| `failure_reason` | `TEXT` | Nullable | Error description on callback failures. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, `DEFAULT NOW()` | Transaction start date. |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL`, `DEFAULT NOW()` | Transaction resolution date. |

* **Indexes**:
  * `idx_payments_checkout_id` on `payments(mpesa_checkout_id)`: Quick search index for webhook processing.
  * `idx_payments_receipt_confirmed` (Partial index): `ON payments(mpesa_receipt_number) WHERE status = 'confirmed'` guarantees receipt uniqueness.

---

### vouchers
* **Purpose**: Internet access passes generated after successful payments.
* **Created in**: `004_create_vouchers.sql` (Altered in `007`, `009b`)

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY`, `DEFAULT uuid_generate_v4()` | Voucher identifier. |
| `tenant_id` | `UUID` | `NOT NULL`, `REFERENCES tenants(id)` | Parent tenant. |
| `payment_id` | `UUID` | `NOT NULL`, `UNIQUE`, `REFERENCES payments(id)` | Link to payment receipt. |
| `customer_id` | `UUID` | `NOT NULL`, `REFERENCES users(id)` | Customer owning the voucher. |
| `package_id` | `UUID` | `NOT NULL`, `REFERENCES packages(id)` | Package constraints. |
| `router_id` | `UUID` | `REFERENCES routers(id) ON DELETE SET NULL` | Target provisioning router. |
| `code` | `VARCHAR(50)` | `NOT NULL`, `UNIQUE` | 8-character connection code. |
| `status` | `VARCHAR(25)` | `NOT NULL`, `DEFAULT 'active'` | States: `active`, `used`, `expired`, `revoked`, `pending_provision`. |
| `activated_at` | `TIMESTAMPTZ` | Nullable | First login connection timestamp. |
| `expires_at` | `TIMESTAMPTZ` | Nullable | Expiration time (`activated_at` + `duration_minutes`). |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, `DEFAULT NOW()` | Timestamp created. |

* **Indexes**:
  * `idx_vouchers_code` on `vouchers(code)`: Fast lookup index for authentication requests.
  * `idx_vouchers_tenant_status` on `vouchers(tenant_id, status)`: Filters dashboard views.

---

### sessions
* **Purpose**: Mirrors active session records from RADIUS accounting for analytics.
* **Created in**: `005_create_sessions.sql` (Altered in `007`, `011`)

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY`, `DEFAULT uuid_generate_v4()` | Session record identifier. |
| `tenant_id` | `UUID` | `NOT NULL`, `REFERENCES tenants(id)` | Parent tenant. |
| `voucher_id` | `UUID` | `NOT NULL`, `REFERENCES vouchers(id)` | Active voucher code connection. |
| `customer_id` | `UUID` | `NOT NULL`, `REFERENCES users(id)` | Client mapping. |
| `mac_address` | `VARCHAR(17)` | Nullable | MAC address of handset device. |
| `ip_address` | `INET` | Nullable | IPv4 address assigned to handset device. |
| `bytes_uploaded` | `BIGINT` | `NOT NULL`, `DEFAULT 0` | Bytes uploaded. |
| `bytes_downloaded`| `BIGINT` | `NOT NULL`, `DEFAULT 0` | Bytes downloaded. |
| `started_at` | `TIMESTAMPTZ` | `NOT NULL`, `DEFAULT NOW()` | Session start time. |
| `ended_at` | `TIMESTAMPTZ` | Nullable | Session end time (Null = Active session). |
| `acct_unique_id` | `VARCHAR(50)` | `UNIQUE` | Radius unique accounting session hash. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, `DEFAULT NOW()` | Sync insertion timestamp. |

* **Indexes**:
  * `idx_sessions_active` (Partial Index): `ON sessions(started_at) WHERE ended_at IS NULL` optimizes calculations for live telemetry.

---

### routers
* **Purpose**: Stores tenant WireGuard endpoints and credentials for remote MikroTik routers.
* **Created in**: `009_create_routers.sql` (Altered in `016`)

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY`, `DEFAULT uuid_generate_v4()` | Router identifier. |
| `tenant_id` | `UUID` | `NOT NULL`, `REFERENCES tenants(id) ON DELETE CASCADE`| Tenant owning this router. |
| `name` | `VARCHAR(100)` | `NOT NULL` | Friendly location name. |
| `host` | `VARCHAR(255)` | Nullable (Set during activation) | WireGuard IP address (e.g. `10.8.0.10`). |
| `port` | `INTEGER` | Nullable (Default: `80`) | REST connection port. |
| `username` | `VARCHAR(100)` | Nullable (Set during activation) | Winbox api operator user. |
| `password_encrypted`| `TEXT` | Nullable | AES Fernet-encrypted Winbox API password. |
| `site_name` | `VARCHAR(100)` | `NOT NULL` | ISP deployment area site tag. |
| `status` | `VARCHAR(20)` | `NOT NULL`, `DEFAULT 'unknown'` | States: `online`, `offline`, `unknown`, `pending_setup`, `testing`. |
| `last_heartbeat_at`| `TIMESTAMPTZ` | Nullable | Last responsive polling heartbeat. |
| `wireguard_public_key`| `TEXT` | Nullable | Local Router wireguard public key. |
| `wireguard_assigned_ip`| `INET` | Nullable | Static tunnel IP. |
| `wireguard_peer_public_key`| `TEXT` | Nullable | VPS public key profile binding. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, `DEFAULT NOW()` | Date registered. |

* **Composite Constraint**:
  * `routers_tenant_name_unique` on `(tenant_id, name)`: Router names must be unique within a tenant.

---

### wallet_transactions
* **Purpose**: Append-only ledger recording financial transaction histories for resellers.
* **Created in**: `010_create_wallet_transactions.sql`

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `sequence_id` | `BIGSERIAL` | Unique incrementer | Guarantees ordered processing sequence. |
| `id` | `UUID` | `PRIMARY KEY`, `DEFAULT uuid_generate_v4()` | Ledger record identifier. |
| `tenant_id` | `UUID` | `NOT NULL`, `REFERENCES tenants(id)` | Parent tenant owner. |
| `reseller_id` | `UUID` | `NOT NULL`, `REFERENCES users(id)` | Target reseller wallet. |
| `type` | `VARCHAR(20)` | `NOT NULL`, `CHECK IN (topup, debit, adjustment)`| Wallet transaction type. |
| `amount_kes` | `NUMERIC(10,2)`| `NOT NULL` | KES change amount (positive for credit, negative for debits). |
| `balance_after` | `NUMERIC(10,2)`| `NOT NULL` | Balance after transaction execution. |
| `reference` | `VARCHAR(100)` | `NOT NULL`, `UNIQUE` | Unique payment code (e.g. M-Pesa Receipt). |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, `DEFAULT NOW()` | Date of ledger record insertion. |

---

### subscriptions
* **Purpose**: Records recurring PPPoE accounts and cycles.
* **Created in**: `012_create_subscriptions.sql`

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY`, `DEFAULT uuid_generate_v4()` | Subscription identifier. |
| `tenant_id` | `UUID` | `NOT NULL`, `REFERENCES tenants(id)` | Tenant owner. |
| `customer_id` | `UUID` | `NOT NULL`, `REFERENCES users(id)` | Customer user profile. |
| `package_id` | `UUID` | `NOT NULL`, `REFERENCES packages(id)` | Package constraints. |
| `status` | `VARCHAR(20)` | `NOT NULL`, `DEFAULT 'active'` | States: `active`, `grace`, `suspended`, `cancelled`. |
| `current_period_end`| `TIMESTAMPTZ`| `NOT NULL` | Expiration date of active cycle. |
| `auto_renew` | `BOOLEAN` | `NOT NULL`, `DEFAULT TRUE` | Flag to auto-debit billing balance. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, `DEFAULT NOW()` | Subscription start date. |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL`, `DEFAULT NOW()` | Date modified. |

---

### invoices
* **Purpose**: Tracks KRA eTIMS compliant tax invoices generated for payments.
* **Created in**: `013b_create_invoices.sql`

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY`, `DEFAULT gen_random_uuid()` | Invoice record UUID. |
| `tenant_id` | `UUID` | `NOT NULL`, `REFERENCES tenants(id)` | Tenant context. |
| `payment_id` | `UUID` | `NOT NULL`, `UNIQUE`, `REFERENCES payments(id)` | Source payment receipt mapping. |
| `invoice_number` | `INTEGER` | `NOT NULL` | Gapless, sequential invoice number. |
| `kra_etims_qr_code`| `TEXT` | Nullable | Encoded KRA verification link. |
| `pdf_path` | `TEXT` | Nullable | Path to generated PDF file on the server. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, `DEFAULT NOW()` | Invoice generation date. |

* **Unique Constraints**:
  * `(tenant_id, invoice_number)` enforces sequential gaps isolation between independent ISPs.

---

### audit_log
* **Purpose**: Keeps a history of administrative modifications for troubleshooting and compliance.
* **Created in**: `014_create_security_tables.sql`

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY`, `DEFAULT gen_random_uuid()` | Audit event identifier. |
| `tenant_id` | `UUID` | `NOT NULL`, `REFERENCES tenants(id)` | Tenant target. |
| `actor_user_id` | `UUID` | `NOT NULL`, `REFERENCES users(id)` | Admin actor user profile. |
| `action` | `VARCHAR(100)` | `NOT NULL` | Event tag (e.g. `revoked_voucher`). |
| `target_type` | `VARCHAR(100)` | `NOT NULL` | Impacted entity type (e.g. `router`). |
| `target_id` | `UUID` | Nullable | Impacted entity UUID identifier. |
| `metadata` | `JSONB` | `DEFAULT '{}'::jsonb` | Payload detail of changes. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, `DEFAULT NOW()` | Occurrence timestamp. |

---

### refresh_tokens
* **Purpose**: Manages JWT refresh tokens to support token rotation security.
* **Created in**: `014_create_security_tables.sql`

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY`, `DEFAULT gen_random_uuid()` | Token record UUID. |
| `user_id` | `UUID` | `NOT NULL`, `REFERENCES users(id)` | Authenticated user profile mapping. |
| `token_hash` | `VARCHAR(255)` | `NOT NULL`, `UNIQUE` | Cryptographic SHA-256 hash. |
| `family_id` | `UUID` | `NOT NULL` | Tracks token rotation chains. |
| `expires_at` | `TIMESTAMPTZ`| `NOT NULL` | Token expiration date. |
| `revoked` | `BOOLEAN` | `NOT NULL`, `DEFAULT FALSE` | Revocation status. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, `DEFAULT NOW()` | Issuance date. |

---

### FreeRADIUS Schema (Core Tables)
* **Purpose**: Core tables read by the FreeRADIUS `rlm_sql` module to authenticate users and log accounting metrics.
* **Created in**: `011_create_radius_tables.sql`

#### radcheck
Stores connection passwords. The voucher `code` is set as `username` and `value`.
* Columns: `id` (SERIAL), `username` (TEXT), `attribute` (TEXT, e.g. `Cleartext-Password`), `op` (VARCHAR, e.g. `==`), `value` (TEXT).

#### radreply
Holds radius attributes sent back to the NAS (MikroTik router) during authentication.
* Columns: `id` (SERIAL), `username` (TEXT), `attribute` (TEXT, e.g. `Mikrotik-Rate-Limit`), `op` (VARCHAR, e.g. `=`), `value` (TEXT, e.g. `10M/10M`).

#### radacct
Detailed accounting logs written by FreeRADIUS when sessions start, update, and end.
* Key Columns: `radacctid` (BIGSERIAL), `acctsessionid` (TEXT), `acctuniqueid` (TEXT UNIQUE), `username` (TEXT), `nasipaddress` (INET), `acctstarttime` (TIMESTAMPTZ), `acctstoptime` (TIMESTAMPTZ), `acctinputoctets` (BIGINT), `acctoutputoctets` (BIGINT), `framedipaddress` (INET).

---

## 4. Key Design Decisions

1. **NUMERIC vs FLOAT for currency**: The KES currency columns (`price_kes`, `amount_kes`, `balance_after`) use the `NUMERIC(10,2)` type. Floating-point calculations introduce rounding errors (`0.1 + 0.2 = 0.30000000000000004`), which can cause issues during audits. `NUMERIC` guarantees exact decimal arithmetic.
2. **INET vs VARCHAR for IP Addresses**: Tables storing IP configurations (`sessions.ip_address`, `radacct.nasipaddress`, `routers.wireguard_assigned_ip`) use PostgreSQL's native `INET` type. This validates IP formats at the database layer and allows subnet queries (e.g. `WHERE ip_address << '10.8.0.0/24'`).
3. **UUID vs SERIAL keys**: High-frequency tables use UUIDs for primary keys. SERIAL integer keys are easily enumerable, allowing attackers to guess resource URLs (e.g. `payments/1` -> `payments/2`). Random UUID v4s prevent enumeration attacks.
4. **Append-Only Wallet Ledger**: Reseller wallet balances are calculated by summing transaction records in the `wallet_transactions` table, rather than updating a single `balance` column on the user profile. This prevents race conditions during concurrent transactions and maintains a complete audit trail.

---

## 5. Common Database Query Patterns

### Get all active customers for a tenant
```sql
SELECT id, email, phone, created_at
FROM users
WHERE tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001'
  AND role = 'customer'
  AND is_active = TRUE;
```

### Get payment status with voucher code
```sql
SELECT p.id AS payment_id, p.amount_kes, p.status AS payment_status, v.code AS voucher_code, v.status AS voucher_status
FROM payments p
LEFT JOIN vouchers v ON p.id = v.payment_id
WHERE p.tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001'
  AND p.mpesa_checkout_id = 'ws_CO_200620261234567890';
```

### Get reseller wallet balance from ledger
```sql
SELECT COALESCE(SUM(amount_kes), 0.00) AS wallet_balance
FROM wallet_transactions
WHERE tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001'
  AND reseller_id = 'bbbbbbbb-1111-1111-1111-111111111111';
```

### Find stuck payments (confirmed payments older than 2 mins without a voucher)
```sql
SELECT id, customer_id, amount_kes, created_at
FROM payments p
WHERE status = 'confirmed'
  AND created_at < NOW() - INTERVAL '2 minutes'
  AND NOT EXISTS (
      SELECT 1 FROM vouchers v WHERE v.payment_id = p.id
  );
```

### Get tenant usage count vs tier limit
```sql
SELECT t.id AS tenant_id, t.business_name, t.subscription_tier, t.max_customers,
       COUNT(u.id) AS active_customers_count
FROM tenants t
LEFT JOIN users u ON t.id = u.tenant_id AND u.role = 'customer' AND u.is_active = TRUE
WHERE t.id = 'aaaaaaaa-0000-0000-0000-000000000001'
GROUP BY t.id;
```

### Verify M-Pesa receipt number uniqueness
```sql
SELECT COUNT(*)
FROM payments
WHERE mpesa_receipt_number = 'QHD48FJ92K';
```

---

## 6. Data Integrity and Business Constraints

* **`mpesa_receipt_number` UNIQUE**: Prevents duplicate payments if Safaricom sends multiple webhook confirmation payloads.
* **`vouchers.payment_id` UNIQUE**: Enforces a strict 1-to-1 relationship between a payment and a voucher.
* **`vouchers.code` UNIQUE**: Prevents multiple users from authenticating with the same access code.
* **`users.role` CHECK**: Enforces valid system roles: `admin`, `reseller`, or `customer`.
* **`payments.status` CHECK**: Enforces valid payment states: `pending`, `confirmed`, `failed`, or `cancelled`.
* **`price_kes` CHECK**: Prevents negative or zero price settings (`CHECK (price_kes > 0)`).

---

## 7. Backup and Recovery Procedures

### Run a manual database backup
To run a compressed custom-format backup from outside the Docker environment, execute:
```bash
docker compose exec -T db pg_dump -U zealnet -d wifi_billing -F c -b -v -f /var/lib/postgresql/data/backups/wifi_billing_backup.dump
```

### Restore the database from a backup
To restore the database (overwriting existing tables), execute:
```bash
docker compose exec -T db pg_restore -U zealnet -d wifi_billing --clean --no-owner --no-privileges /var/lib/postgresql/data/backups/wifi_billing_backup.dump
```

### Verify database restore integrity
Compare post-restore record counts to verify data integrity:
```sql
SELECT 'tenants' AS table_name, COUNT(*) FROM tenants
UNION ALL SELECT 'users', COUNT(*) FROM users
UNION ALL SELECT 'packages', COUNT(*) FROM packages
UNION ALL SELECT 'payments', COUNT(*) FROM payments
UNION ALL SELECT 'vouchers', COUNT(*) FROM vouchers
UNION ALL SELECT 'sessions', COUNT(*) FROM sessions
UNION ALL SELECT 'routers', COUNT(*) FROM routers;
```
