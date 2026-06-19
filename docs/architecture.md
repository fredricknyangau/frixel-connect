# System Architecture and Component Design

This document details the system design, core components, request sequence flows, and architectural constraints of ZealSync.

---

## 1. System Overview

ZealSync is a multi-tenant WiFi billing SaaS platform built on a modular monolith backend (FastAPI) and a single-page frontend (React 19). It automates payment collection and service provisioning for small and medium ISPs in Kenya. The platform handles user authentication, billing, payments via Safaricom M-Pesa, SMS delivery via Africa's Talking, KRA eTIMS invoice generation, and real-time session control on remote MikroTik routers. Secure router connections are established through kernel-level WireGuard VPN tunnels, and user authentication is handled via a PostgreSQL-backed FreeRADIUS setup.

---

## 2. Architectural Decisions

| Decision | Choice Made | Rejected Alternative | Reason |
| :--- | :--- | :--- | :--- |
| **Database access** | Raw SQL (asyncpg) | SQLAlchemy ORM | Full query control on complex financial data, avoiding lazy loading bugs, and maximizing throughput. |
| **Background jobs** | arq (Redis-backed) | FastAPI BackgroundTasks | Durability -FastAPI's built-in queue runs in-memory and dies if the process restarts; `arq` state survives container crashes. |
| **Router access** | WireGuard VPN | Public port forwarding | Security -MikroTik REST APIs are never exposed to the public internet; routers connect to Hetzner via isolated tunnels. |
| **Auth tokens** | JWT access + refresh | Session cookies | Stateless API, simplified React integration, and flexibility for future native mobile clients. |
| **Tenant isolation** | `tenant_id` on every table | Separate databases | Operational simplicity and low hosting costs at the current scale; row-level isolation via query parameters is highly cost-effective. |
| **RADIUS vs REST** | Both (RADIUS auth, REST provisioning) | REST only | RADIUS allows real-time AAA accounting and instant Disconnect-Requests (CoA) on router interfaces. |
| **Password storage** | bcrypt | argon2 | Industry standard, widely supported across libraries, and doesn't require compiling C bindings inside Alpine. |
| **Router credentials** | Fernet-encrypted in DB | `.env` file | Multi-tenancy support -since each tenant configures their own routers, credentials must be stored dynamically in PostgreSQL. |

---

## 3. Component Diagram

```text
                                     CLIENT LAYER
             ┌──────────────────────────────────────────────────────────┐
             │   Admin Portal (Web)   Reseller App   Customer Portal    │
             └────────────────────────────┬─────────────────────────────┘
                                          │ (HTTPS)
                                          ▼
                                     VERCEL LAYER
             ┌──────────────────────────────────────────────────────────┐
             │                   React 19 SPA Frontend                  │
             └────────────────────────────┬─────────────────────────────┘
                                          │ (HTTPS API requests)
                                          ▼
                         HETZNER VPS INFRASTRUCTURE (Ubuntu 22.04)
┌───────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                       │
│                                      Nginx Proxy                                      │
│                                    (SSL Termination)                                  │
│                                             │                                         │
│                    ┌────────────────────────┴────────────────────────┐                │
│                    ▼                                                 ▼                │
│              FastAPI API                                        arq Worker            │
│            (Web Processes)                                   (Job Execution)          │
│             │            │                                    │            │          │
│             │            └────────────────┐  ┌────────────────┘            │          │
│             ▼                             ▼  ▼                             ▼          │
│        PostgreSQL 16                      Redis 7                     FreeRADIUS      │
│      (Raw SQL Storage)              (Job Queue & Cache)              (AAA Daemon)     │
│             ▲                                                              │          │
│             └──────────────────────────────────────────────────────────────┘          │
│                                     (rlm_sql queries)                                 │
│                                                                                       │
│                               WireGuard Kernel Interface                              │
│                                      (wg0 on Host)                                    │
│                                                                                       │
└─────────────────────────────────────────┬─────────────────────────────────────────────┘
                                          │
                                 INTERNET / VPN LAYER
             ┌────────────────────────────┼─────────────────────────────┐
             │                            │ (WireGuard Tunnel)          │
             ▼                            ▼                             ▼
     ┌──────────────┐             ┌──────────────┐             ┌──────────────┐
     │ Safaricom    │             │  MikroTik    │             │ Africa's     │
     │ Daraja API   │             │  RouterOS v7 │             │ Talking API  │
     └──────────────┘             └──────┬───────┘             └──────────────┘
                                         │ (Hotspot/PPPoE interfaces)
                                         ▼
                                  CLIENT DEVICES
                               ┌─────────────────┐
                               │ Customer Phones │
                               └─────────────────┘
```

---

## 4. Request Flow Diagrams

### FLOW A -Customer buys a hotspot voucher (STK Push path)
```text
Customer          Customer Portal            FastAPI API                 Daraja API
   │                    │                         │                           │
   │ 1. Select Package  │                         │                           │
   ├───────────────────►│ 2. POST /payments/stk   │                           │
   │    & Input Phone   │├───────────────────────►│                           │
   │                    ││                        │ 3. POST /mpesa/stkpush    │
   │                    ││                        ├──────────────────────────►│
   │                    ││                        │                           │
   │                    ││                        │ 4. STK Response (Pending) │
   │                    ││                        │◄──────────────────────────┤
   │                    ││ 5. HTTP 202 Accepted   │                           │
   │                    ││◄───────────────────────┤                           │
   │                    ││                        │                           │
   │                    ││                        │                           │ 6. Send STK Push PIN
   │                    ││                        │                           │  Prompt to Phone
   │◄───────────────────┴┴────────────────────────┴───────────────────────────┼──────────
   │                                                                          │
   │ 7. Customer enters M-Pesa PIN on handset                                 │
   └──────────────────────────────────────────────────────────────────────────┘
```

### FLOW B -Daraja webhook arrives (idempotency path)
```text
Safaricom Daraja           FastAPI Webhook               PostgreSQL                Redis Queue
      │                           │                           │                         │
      │ 1. POST /webhooks/daraja  │                           │                         │
      ├──────────────────────────►│                           │                         │
      │                           │ 2. Check if checkout_id   │                         │
      │                           │    processed              │                         │
      │                           ├──────────────────────────►│                         │
      │                           │ 3. Row Status='pending'   │                         │
      │                           │◄──────────────────────────┤                         │
      │                           │                           │                         │
      │                           │ 4. BEGIN TRANSACTION      │                         │
      │                           │    UPDATE payments        │                         │
      │                           │    SET status='confirmed' │                         │
      │                           ├──────────────────────────►│                         │
      │                           │ 5. TX Commit Succeeded    │                         │
      │                           │◄──────────────────────────┤                         │
      │                           │ (Absorbs unique violations│                         │
      │                           │  if callback retried)     │                         │
      │                           │                           │                         │
      │                           │ 6. Enqueue worker job     │                         │
      │                           ├───────────────────────────┼────────────────────────►│
      │                           │                           │ 7. Job Accepted         │
      │                           │◄──────────────────────────┼─────────────────────────┤
      │ 8. HTTP 200 (ResultCode=0)│                           │                         │
      │◄──────────────────────────┤                           │                         │
```

### FLOW C -arq worker provisions MikroTik user
```text
arq Worker                 PostgreSQL                 MikroTik Router          FreeRADIUS DB
    │                           │                           │                        │
    │ 1. Poll / Fetch Job       │                           │                        │
    ├──────────────────────────►│                           │                        │
    │                           │                           │                        │
    │ 2. Fetch Payment Detail   │                           │                        │
    ├──────────────────────────►│                           │                        │
    │ 3. Return payment/tenant  │                           │                        │
    │◄──────────────────────────┤                           │                        │
    │                           │                           │                        │
    │                           │ 4. POST /rest/ip/hotspot  │                        │
    │                           │    /user (Create profile) │                        │
    │                           ├──────────────────────────►│                        │
    │                           │ 5. API Response OK        │                        │
    │                           │◄──────────────────────────┤                        │
    │                           │                           │                        │
    │ 6. Insert radcheck        │                           │                        │
    │    (Username/Password =   │                           │                        │
    │     Voucher Code)         │                           │                        │
    ├───────────────────────────┼───────────────────────────┼───────────────────────►│
    │ 7. INSERT vouchers (DB)   │                           │                        │
    ├──────────────────────────►│                           │                        │
```

### FLOW D -Reconciliation cron finds stuck payment
```text
arq worker (Cron)             PostgreSQL               Redis Queue              arq worker (Job)
       │                           │                        │                           │
       │ 1. Every 5 minutes        │                        │                           │
       ├──────────────────────────►│                        │                           │
       │                           │                        │                           │
       │ 2. Find confirmed payments│                        │                           │
       │    >2 min old, no voucher │                        │                           │
       ├──────────────────────────►│                        │                           │
       │ 3. Return Payments List   │                        │                           │
       │◄──────────────────────────┤                        │                           │
       │                           │                        │                           │
       │ 4. Re-enqueue stuck job   │                        │                           │
       ├───────────────────────────┼───────────────────────►│                           │
       │                           │                        │ 5. Poll Job               │
       │                           │                        │◄──────────────────────────┤
       │                           │                        │ 6. Run Voucher Generation │
       │                           │                        │├─────────────────────────►│
```

### FLOW E -Reseller tops up wallet (C2B path)
```text
Reseller               M-Pesa C2B Menu             Daraja Webhook             PostgreSQL
   │                          │                           │                       │
   │ 1. Input Paybill Number  │                           │                       │
   │    & Account (Ref Code)  │                           │                       │
   ├─────────────────────────►│                           │                       │
   │ 2. Input KES amount      │                           │                       │
   ├─────────────────────────►│                           │                       │
   │                          │ 3. Validate Request       │                       │
   │                          ├──────────────────────────►│ (Checks BillRefNumber │
   │                          │                           │  against reseller references)
   │                          │ 4. POST Confirmation      │                       │
   │                          ├──────────────────────────►│                       │
   │                          │                           │ 5. INSERT wallet_trans│
   │                          │                           ├──────────────────────►│
   │                          │                           │ 6. Commit TX          │
   │                          │                           │◄──────────────────────┤
```

### FLOW F -Reseller generates voucher from wallet balance
```text
Reseller              Reseller Portal              FastAPI API                PostgreSQL
   │                         │                          │                          │
   │ 1. Request Voucher      │                          │                          │
   ├────────────────────────►│ 2. POST /vouchers/resell │                          │
   │                         ├─────────────────────────►│                          │
   │                         │                          │ 3. BEGIN TRANSACTION     │
   │                         │                          │    Calculate Ledger sum  │
   │                         │                          │    and verify balance    │
   │                         │                          ├─────────────────────────►│
   │                         │                          │ 4. Debit Wallet Ledger  │
   │                         │                          ├─────────────────────────►│
   │                         │                          │ 5. INSERT Voucher       │
   │                         │                          ├─────────────────────────►│
   │                         │                          │ 6. Commit Succeeded     │
   │                         │                          │◄────────────────────────┤
   │                         │ 7. HTTP 201 Created      │                          │
   │                         │◄─────────────────────────┤                          │
   │◄────────────────────────┴──────────────────────────┘                          │
```

### FLOW G -PPPoE subscription auto-renewal
```text
arq worker (Cron)             PostgreSQL               MikroTik Router          Africa's Talking
       │                           │                          │                        │
       │ 1. Midnight trigger       │                          │                        │
       ├──────────────────────────►│                          │                        │
       │                           │                          │                        │
       │ 2. Fetch overdue accounts │                          │                        │
       ├──────────────────────────►│                          │                        │
       │ 3. Return Subscriptions   │                          │                        │
       │◄──────────────────────────┤                          │                        │
       │                           │                          │                        │
       │ 4. UPDATE Status =        │                          │                        │
       │    'suspended'            │                          │                        │
       ├──────────────────────────►│                          │                        │
       │                           │ 5. Disable PPP Secret    │                        │
       ├───────────────────────────┼─────────────────────────►│                        │
       │                           │ 6. Send Disconnect SMS   │                        │
       ├───────────────────────────┼──────────────────────────┼───────────────────────►│
```

### FLOW H -Voucher revocation with CoA instant disconnect
```text
Admin Portal                FastAPI API                PostgreSQL              FreeRADIUS (CoA)
     │                           │                          │                         │
     │ 1. DELETE /vouchers/{id}  │                          │                         │
     ├──────────────────────────►│                          │                         │
     │                           │ 2. Mark Voucher status   │                         │
     │                           │    as 'revoked'          │                         │
     │                           ├─────────────────────────►│                         │
     │                           │ 3. DELETE radcheck       │                         │
     │                           ├─────────────────────────►│                         │
     │                           │                          │                         │
     │                           │ 4. Send UDP Disconnect   │                         │
     │                           │    to NAS Port 3799      │                         │
     │                           ├──────────────────────────┼────────────────────────►│
     │                           │                          │ (Radius sends Disconnect│
     │                           │                          │  packet to router)      │
     │ 5. HTTP 200 OK            │                          │                         │
     │◄──────────────────────────┤                          │                         │
```

---

## 5. Modular Monolithic Structure

The backend codebase is organized as a structured modular monolith. Each module under `app/modules/` is isolated and self-contained, encapsulating its own routing, models, services, and schemas:

```text
app/
├── core/                  # Core modules (security, logging, Redis, DB connections)
├── integrations/          # Lower-level HTTP wrappers & clients (No business logic)
│   ├── daraja.py          # Safaricom payments
│   ├── mikrotik.py        # Router API commands
│   ├── africastalking.py  # SMS integration
│   ├── wireguard.py       # Tunnel controller
│   ├── radius_coa.py      # Radius Disconnect client
│   └── etims.py           # eTIMS invoices
└── modules/               # High-level business logic packages
    ├── auth/              # JWT issuance and token validation
    ├── tenants/           # Business accounts and metering
    ├── users/             # Account management
    ├── packages/          # WiFi packages
    ├── payments/          # Payments ledger
    ├── vouchers/          # Vouchers generation
    ├── sessions/          # RADIUS mirror accounting
    ├── wallets/           # Reseller wallet ledgers
    └── webhooks/          # Webhook receivers (Daraja)
```

### Core Architecture Rules:
1. **No Circular Imports**: Modules must not import files from the internals of other modules. If `vouchers` needs information from `payments`, it must invoke the public function in `payments/service.py`, never direct SQL or internal functions.
2. **Decoupled Integrations**: Third-party APIs live in `integrations/`. No logic regarding business flows, status flags, or tenant ownership exists here. Files in `modules/` call these clients and handle the business outcomes.

---

## 6. Multi-Tenancy Design

ZealSync implements a logical multi-tenancy model where multiple independent ISPs (tenants) share the same application instance and database.

* **Tenant Isolation**: Every database table that holds tenant-specific data contains a `tenant_id` column referencing `tenants.id`.
* **JWT Scoping**: When an admin or reseller authenticates, their token contains their profile ID and their company's `tenant_id`.
* **Dependency Scoping**: FastAPI endpoint protection utilizes the `get_current_tenant_id` dependency. This extracts the `tenant_id` claim from the JWT, ensuring that database updates are constrained using a `WHERE tenant_id = :tenant_id` clause.
* **Security Scoping**: If a user attempts to retrieve an resource ID belonging to another tenant (e.g. `GET /vouchers/some-other-tenant-uuid`), the system returns a `404 Not Found` instead of a `403 Forbidden`. This prevents resource enumeration and limits scanning vector visibility.
* **Onboarding Flow**: Tenants onboard via the public registration API: `POST /api/v1/tenants/register`. This creates the tenant profile, seeds their administrator account, and sets up default routing profiles.
* **Platform Billing**: ZealSync meters active users per tenant against their subscription tier limits. If a tenant's billing cycle expires, a daily midnight cron initiates a Safaricom STK Push to their registered owner phone. If unpaid past a 7-day grace period, the tenant's status changes to `suspended` and all requests are blocked.

---

## 7. Reliability Design

To meet the core guarantee that payments always result in vouchers, ZealSync implements four fault-tolerance layers:

```text
Incoming Webhook
      │
      ▼
┌──────────────┐
│   Layer 1    ├─► [Unique Receipt Constraint] Checks for duplicates.
└──────┬───────┘
       │ (Succeeds)
       ▼
┌──────────────┐
│   Layer 2    ├─► [Durable arq Queue] Persists provisioning tasks in Redis.
└──────┬───────┘
       │ (Processing)
       ▼
┌──────────────┐
│   Layer 3    ├─► [Exponential Backoff] Retries Router REST calls if down.
└──────┬───────┘
       │ (Exhausted / Fails)
       ▼
┌──────────────┐
│   Layer 4    ├─► [Reconciliation Cron] Safety check runs every 5 minutes.
└──────────────┘
```

1. **Layer 1: Database-Level Idempotency**: The `mpesa_receipt_number` column in the `payments` table has a `UNIQUE` constraint. Duplicate webhook calls trigger a `UniqueViolationError` which is caught in the router to immediately return `HTTP 200 OK`.
2. **Layer 2: Durable Job Queue**: Confirmation writes trigger an `arq` background job enqueued to Redis, separating the webhook HTTP response from the router network calls.
3. **Layer 3: Exponential Backoff Retry**: If the target router is unreachable during the REST call, the worker raises an `arq.Retry` exception. The worker schedules retries at 5s, 15s, and 45s intervals. If all 4 attempts fail, the voucher is marked as `pending_provision` for manual administrative action.
4. **Layer 4: Reconciliation Cron safety net**: Every 5 minutes, a cron sweeps the database for payments marked `confirmed` that are older than 2 minutes and have no corresponding voucher. These are enqueued back to `arq` automatically.

---

## 8. Security Architecture

* **Token Flow**: The authentication service uses standard JWT access tokens (30 minutes expiry) and rotating refresh tokens stored in the `refresh_tokens` table.
* **Credential Encryption**: Tenants configure router passwords through the admin portal. These credentials are encrypted on write using symmetric Fernet keys (`FERNET_SECRET_KEY`) and decrypted only in memory when executing REST queries.
* **VPN Routing**: Router REST ports are bound to the internal WireGuard tunnel interfaces (`10.8.0.0/24`). No router management ports are exposed to the public internet.
* **Sliding Window Rate Limiting**: Redis track requests using rolling sliding windows to block brute-force attempts on login endpoints and API limits.
* **Audit Trails**: Critical state modifications (router updates, package price edits, manually revoked vouchers) write structured metadata records directly to `audit_logs`.
