# ZealSync -Multi-Tenant WiFi Billing SaaS

[![Python Version](https://img.shields.io/badge/Python-3.12.2-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.137.1-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-green)](https://opensource.org/licenses/MIT)
[![Deployment Status](https://img.shields.io/badge/Deployment-Live-success)](https://zealsync.dev)

Small ISPs in Kenya spend 3 hours a day manually reconciling M-Pesa payments and enabling MikroTik accounts in Winbox. ZealSync automates the entire pipeline.

ZealSync is a production-deployed, multi-tenant WiFi billing SaaS platform designed specifically for the Kenyan Internet Service Provider (ISP) market. It enables ISPs to manage packages, automate payment reconciliation using Safaricom Daraja API webhooks, provision Hotspot and PPPoE users on MikroTik routers via secure WireGuard VPN tunnels, generate KRA eTIMS-compliant invoices, and manage resellers via a virtual wallet ledger.

---

## Interactive Admin Dashboard (ASCII Preview)

Below is an ASCII preview of the ZealSync ISP Owner Dashboard showing real-time revenue collection, active sessions, and reseller ledger statuses:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  ZEALSYNC ISP DASHBOARD  -  DEFAULT ISP (ZealSync MLP)             [ Role: ISP Owner ]  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  REVENUE (MONTH-TO-DATE)      ACTIVE CUSTOMERS             ACTIVE SESSIONS             │
│  ┌───────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐       │
│  │  KES 142,500.00       │   │  348 / 500           │   │  82 Active Users     │       │
│  │  ▲ +14% vs last month │   │  [████████░░░░] 69%  │   │  Throughput: 84 Mbps │       │
│  └───────────────────────┘   └──────────────────────┘   └──────────────────────┘       │
│                                                                                        │
│  RESELLER WALLET BALANCES                                                              │
│  - WS12345 (Amina Hassan)   : KES  12,450.00  [Active]                                 │
│  - WS89012 (John Kamau)     : KES   4,800.00  [Active]                                 │
│  - WS45678 (Peter Otieno)   : KES     150.00  [Low Balance Warning]                    │
│                                                                                        │
│  RECENT PAYMENTS (M-PESA)                                                              │
│  ┌──────────┬─────────────────┬─────────────┬─────────────┬───────────┬──────────────┐ │
│  │ Time     │ Phone           │ Customer    │ Package     │ KES       │ Status       │ │
│  ├──────────┼─────────────────┼─────────────┼─────────────┼───────────┼──────────────┤ │
│  │ 12:44:02 │ 254712345678    │ John Kamau  │ Daily 10M   │     50.00 │ CONFIRMED    │ │
│  │ 12:41:15 │ 254798765432    │ Amina Hassan│ Weekly 20M  │    300.00 │ CONFIRMED    │ │
│  │ 12:35:50 │ 254722334455    │ Peter Otieno│ Daily 10M   │     50.00 │ CONFIRMED    │ │
│  │ 12:30:10 │ 254711223344    │ Mercy Mwangi│ Monthly 30M │  1,500.00 │ FAILED (PIN) │ │
│  └──────────┴─────────────────┴─────────────┴─────────────┴───────────┴──────────────┘ │
│                                                                                        │
│  ACTIVE HOTSPOT SESSIONS (MIKROTIK)                                                    │
│  - AA:BB:CC:00:11:22 | 10.5.50.4  | Voucher: ZS-9842 (20 Mbps) - Up: 1.2 GB | Down: 8.4 GB │
│  - DD:EE:FF:33:44:55 | 10.5.50.21 | Voucher: ZS-3129 (10 Mbps) - Up: 0.4 GB | Down: 3.1 GB │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Features

| Feature Name | Description |
| :--- | :--- |
| `[Coins]` M-Pesa STK Push | Automatically triggers an STK Push to the customer's phone upon selecting a package. |
| `[Network]` MikroTik RouterOS | Integrates with RouterOS v7 REST API to provision users dynamically. |
| `[Lock]` Webhook Idempotency | Enforces database-level uniqueness on M-Pesa receipts to prevent duplicate voucher creation. |
| `[Server]` Durable Task Queue | Employs Redis-backed `arq` workers to guarantee task durability even across api container restarts. |
| `[Refresh]` Reconciliation Cron | Executes a 5-minute background check to retry stuck payments that haven't generated vouchers. |
| `[Wallet]` Reseller Wallet | Managed virtual ledger utilizing C2B payment top-ups for autonomous voucher generation. |
| `[Key]` RADIUS AAA | Utilizes FreeRADIUS and `rlm_sql` linked directly to PostgreSQL for session control. |
| `[Activity]` Instant Revocation | Leverages RADIUS Change of Authorization (CoA) to terminate active sessions immediately on deletion. |
| `[Calendar]` PPPoE Subscriptions | Manages recurring subscription cycles with automated grace periods and suspension triggers. |
| `[FileText]` KRA eTIMS Invoicing | Automatically generates KRA-compliant invoices complete with QR code signatures via reportlab. |
| `[Users]` Multi-Tenancy | Structurally isolates tenants via `tenant_id` scopes to support multiple independent ISPs. |
| `[MessageSquare]` SMS Integration | Delivers vouchers and expiration alerts via Africa's Talking SMS API. |
| `[Shield]` Security Hardening | Incorporates JWT token rotation, Fernet credential encryption, and Redis rate limiting. |
| `[Database]` Data Protection | Implements endpoints to export or anonymize user profiles according to Kenya's Data Protection Act 2019. |
| `[Laptop]` Modern React Portal | Built with React 19, TypeScript, and Tailwind CSS v4, supporting Dark Mode by default. |

---

## Technology Stack

| Layer | Technology | Version |
| :--- | :--- | :--- |
| Language | Python | 3.12.2 (managed via pyenv) |
| Framework | FastAPI | 0.137.1 |
| Database | PostgreSQL | 16 |
| Task Queue | arq (Redis-backed) | 0.26.1 (Redis server 7) |
| Authentication | JWT (with token rotation) + bcrypt | PyJWT & bcrypt 5.0.0 |
| Payments | Safaricom Daraja API | STK Push / C2B |
| SMS API | Africa's Talking | REST SDK |
| MikroTik API | RouterOS REST API | v7 |
| RADIUS | FreeRADIUS + rlm_sql | 3.0 |
| Virtual Private Network | WireGuard VPN | wg0 Kernel Module / wg-quick |
| Invoicing | KRA eTIMS SDK | Python standard (Mock mode supported) |
| Frontend Framework | React + Vite + TypeScript | React 19, TypeScript 6, Vite 8 |
| UI Styling | Tailwind CSS v4 + shadcn/ui | Tailwind 4.3.1 |
| Reverse Proxy | Nginx | Alpine image |
| Infrastructure | Hetzner VPS | Ubuntu 22.04 LTS |

---

## Quick Start (Local Development)

Execute the following commands in sequence to bring up the environment on your local system:

```bash
# a) Clone and enter directory
git clone https://github.com/fredrick-nyangau/wifi-billing.git
cd wifi-billing

# b) Copy env template configuration
cp .env.example .env

# c) Spin up Docker containers
docker compose up --build -d

# d) Apply SQL schema migrations
./scripts/run_migrations.sh

# e) Seed initial tenant, users, and packages
docker compose exec api python scripts/seed_db.py
```

### Accessing the Applications
* **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **Frontend Portal**: [http://localhost:5173](http://localhost:5173)

### Default Admin Credentials
* **Username**: `admin@zealsync.dev`
* **Password**: `TestPassword123!`
* **Tenant ID**: `aaaaaaaa-0000-0000-0000-000000000001`

---

## Architecture Overview

```text
                               ┌─────────────────┐
                               │  Client Browser │
                               └────────┬────────┘
                                        │ (HTTPS)
                                        ▼
                               ┌─────────────────┐
                               │   Nginx Proxy   │
                               └────────┬────────┘
                                        │
                    ┌───────────────────┴───────────────────┐
                    │ (Port 8000 /api)                      │ (Static Files)
                    ▼                                       ▼
         ┌─────────────────────┐                 ┌─────────────────────┐
         │     FastAPI API     │                 │   React Frontend    │
         └──────────┬──────────┘                 └─────────────────────┘
                    │ (Job Dispatch)
                    ▼
         ┌─────────────────────┐
         │     Redis Queue     │
         └──────────▲──────────┘
                    │ (Job Poll)
                    ▼
         ┌─────────────────────┐                 ┌─────────────────────┐
         │     arq Worker      ├────────────────►│ Africa's Talking SMS│
         └──────────┬──────────┘                 └─────────────────────┘
                    │
         ┌──────────┴──────────┐
         │     PostgreSQL      │◄────────────────┐
         └──────────┬──────────┘                 │ (SQL accounting)
                    │                            │
     ┌──────────────┴──────────────┐   ┌─────────┴───────────┐
     ▼                             ▼   │     FreeRADIUS      │
┌──────────────┐     ┌─────────────┐   └─────────▲───────────┘
│  Daraja API  │     │  WireGuard  │             │ (Auth/Acct/CoA)
└──────────────┘     └──────┬──────┘             │
                            │ (Secure Tunnel)    │
                            ▼                    │
                     ┌─────────────┐             │
                     │  MikroTik   ├─────────────┘
                     └─────────────┘
```

---

## The Core Guarantee

> [!IMPORTANT]
> **The Reliability Promise:** A payment that hits the Daraja webhook is **ALWAYS** persisted to PostgreSQL within the HTTP timeout window and **ALWAYS** results in a MikroTik hotspot user being created -even if the router is briefly offline -via a durable arq job with exponential backoff retry and a 5-minute reconciliation cron as a safety net.

---

## Documentation Registry

| Document | Target Location | Description |
| :--- | :--- | :--- |
| [Architecture Document](file:///home/dev-fred/dev/projects/wifi-billing/docs/architecture.md) | `docs/architecture.md` | Deep dive into system components, sequence flows, modular layout, and network topologies. |
| [Database Schema Reference](file:///home/dev-fred/dev/projects/wifi-billing/docs/database-schema.md) | `docs/database-schema.md` | Schema mapping, column documentation, index usage, integrity constraints, and query patterns. |
| [API Reference](file:///home/dev-fred/dev/projects/wifi-billing/docs/api-reference.md) | `docs/api-reference.md` | OpenAPI-compliant routes, request payloads, response schemas, and role permissions. |
| [Developer Setup Guide](file:///home/dev-fred/dev/projects/wifi-billing/docs/developer-setup.md) | `docs/developer-setup.md` | Step-by-step local workspace config, testing frameworks, and seeder customization. |
| [Deployment Guide](file:///home/dev-fred/dev/projects/wifi-billing/docs/deployment.md) | `docs/deployment.md` | Production server config on Hetzner, Docker setups, SSL certification, and firewall rules. |
| [MikroTik Integration Guide](file:///home/dev-fred/dev/projects/wifi-billing/docs/mikrotik-integration.md) | `docs/mikrotik-integration.md` | WireGuard configuration, Hotspot user profiles, walled gardens, and API integrations. |
| [Daraja Integration Guide](file:///home/dev-fred/dev/projects/wifi-billing/docs/daraja-integration.md) | `docs/daraja-integration.md` | Sandbox vs production setup, certificate uploads, webhook validation, and STK callback structures. |
| [Admin User Guide](file:///home/dev-fred/dev/projects/wifi-billing/docs/guides/admin-guide.md) | `docs/guides/admin-guide.md` | Standard procedures for ISP owners to manage routers, packages, resellers, and billing. |
| [Reseller User Guide](file:///home/dev-fred/dev/projects/wifi-billing/docs/guides/reseller-guide.md) | `docs/guides/reseller-guide.md` | Ledger management, wallet top-ups, voucher generation, and printing. |
| [Customer User Guide](file:///home/dev-fred/dev/projects/wifi-billing/docs/guides/customer-guide.md) | `docs/guides/customer-guide.md` | Captive portal navigation, STK transaction codes, and package support lookup. |
| [Security Documentation](file:///home/dev-fred/dev/projects/wifi-billing/docs/security.md) | `docs/security.md` | Encryption protocols, token rotation policies, VPN security, rate limits, and audit logs. |
| [Troubleshooting Guide](file:///home/dev-fred/dev/projects/wifi-billing/docs/troubleshooting.md) | `docs/troubleshooting.md` | Webhook verification commands, radius client status tools, wireguard pings, and DB fixes. |
| [Changelog and Roadmap](file:///home/dev-fred/dev/projects/wifi-billing/docs/changelog.md) | `docs/changelog.md` | Milestone timelines, system version history, and upcoming features. |

---

## Market Context

Kenyan ISPs operating in residential estates (such as Nairobi's Eastlands, Kasarani, or Roysambu) face high transaction volumes with low average revenue per user (ARPU). Traditional ISP billing suites like Splynx are built for large corporate entities; they are bloated, expensive, and require third-party payment modules to integrate Kenyan payment processors. In contrast, local competitors like Jasiyo charge a revenue-share percentage, which directly eats into the razor-thin margins of small-scale entrepreneurs.

ZealSync solves this by offering a high-performance, flat-rate, multi-tenant billing engine designed natively for Safaricom M-Pesa. It isolates client traffic securely using kernel-level WireGuard tunnels and ensures that webhook dropouts never lead to lost vouchers. This structural reliability allows local operators to grow their networks autonomously without worrying about double-allocating resources or losing track of reseller deposits.

---

## Contributing

Please refer to `CONTRIBUTING.md` for guidelines on submitting pull requests and running test suites. Code contributions must follow the strict TypeScript guidelines for frontend developments and structural boundaries for FastAPI backend packages. All changes to core database logic must go through the SQL migration suite.

---

## License

This project is licensed under the MIT License. See `LICENSE` for details.

---

## Author

**Fredrick Nyangau** -Nairobi, Kenya
* **GitHub**: [@fredrick-nyangau](https://github.com/fredrick-nyangau)
* **LinkedIn**: [Fredrick Nyangau](https://linkedin.com/in/fredrick-nyangau)
* **Portfolio**: [fredricknyangau.dev](https://fredricknyangau.dev)
* **Website**: [zealsync.dev](https://zealsync.dev)
