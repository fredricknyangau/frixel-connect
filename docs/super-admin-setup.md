# Frixel Connect Super Admin Setup and Operations Guide

This guide describes how to initialize, configure, recover, and operate the Frixel Connect Super Admin portal.

The super admin account operates outside and above all standard tenants. This role is meant exclusively for Frixel Labs (Fredrick Nyangau) to manage ISP tenants, view system-wide metrics, and perform billing operations.

---

## 1. Creating the First Super Admin Account

Because the super admin portal is completely separate from regular tenant portals and does not share the same user tables, the first account must be seeded directly from the command line on the host system.

### Seeding Command

Run the interactive python seeder script within the API container:

```bash
docker compose exec api python scripts/seed_super_admin.py
```

### What It Prompts For

When you run this script, it will interactively prompt you for:

1. **Email address**: The email used to log into the super admin portal (must contain `@`).
2. **Full name**: The display name for this super admin user.
3. **Password**: A password of **at least 12 characters**. For security, the input will be hidden as you type (using `getpass`).
4. **Confirm Password**: Re-enter the password to ensure there are no typos.

### What It Creates

Under the hood, the seeder:
- Connects to the PostgreSQL database.
- Checks if a super admin with the given email already exists (the operation is fully idempotent).
- Hashes the password using **bcrypt** (with a secure cost factor of 12).
- Creates a new record in the `super_admins` table with `totp_secret = NULL` and `totp_verified_at = NULL`.

Once completed, the script prints the newly created account ID and creation timestamp.

---

## 2. First Login and TOTP Setup

MFA (Multi-Factor Authentication) using Time-Based One-Time Passwords (TOTP) is **mandatory** for all super admin accounts. There is no password-only bypass.

### Step-by-Step Initialization

1. **Navigate to the Login Page**  
   Open your browser and navigate to the super admin login portal:
   * Local development: `http://localhost/super-admin/login`
   * Production: `https://your-domain.com/super-admin/login`

2. **Enter Email and Password**  
   Fill in the credentials you configured during the seeding step and click **Continue**.

3. **Scan the QR Code**  
   The application will detect that TOTP is not yet set up for this account. It will display a screen with a dynamically generated QR code.  
   * Open your authenticator application (e.g., Google Authenticator, Authy, or Bitwarden) on your mobile device.
   * Scan the QR code.
   * If your camera fails, use the manual entry key shown on the screen (the first few characters of the secret).

4. **Verify the 6-Digit Code**  
   * Enter the current 6-digit verification code from your authenticator app.
   * Upon entering the 6th digit, the page will auto-submit (with a 30-second security countdown).
   * After verification succeeds, the database updates `totp_verified_at = NOW()` and issues a 15-minute JWT access token.
   * You are redirected to the Super Admin Dashboard.

---

## 3. TOTP Recovery Procedure

If a super admin loses their authenticator device or deletes the account from their authenticator app, they will be locked out.

### Why No Self-Service Reset?

> [!IMPORTANT]
> **No self-service TOTP reset is implemented by design.**
> Any automated recovery channel (such as email link, SMS, or security questions) introduces an attack vector. An attacker who compromises the super admin's email account could bypass MFA. By requiring direct database and host SSH access, we ensure that recovery relies on a completely separate and highly secure security boundary.

### Database Recovery Steps

To reset MFA and force a new setup flow, you must clear the encrypted TOTP secret in the database:

1. **SSH into your hosting server** (e.g., the Oracle VPS).
2. **Access the database CLI** by executing `psql` within the database Docker container:
   ```bash
   docker compose exec db psql -U wifi_user -d wifi_billing
   ```
3. **Run the reset SQL command**:
   ```sql
   UPDATE super_admins 
   SET totp_secret = NULL, totp_verified_at = NULL 
   WHERE email = 'your@email.com';
   ```
   *(Replace `your@email.com` with the email of the locked-out super admin)*
4. **Exit the database CLI**:
   ```sql
   \q
   ```
5. **Log in normally**: The next login attempt will detect that TOTP is not configured and will prompt the user with a fresh QR code screen to set up a new authenticator device.

---

## 4. Adding a Second Super Admin

Once you are logged into the portal, you can provision additional super admin accounts for other system operators.

1. In the Super Admin sidebar, navigate to the **Accounts** page (`/super-admin/accounts`).
2. Click the **Add Super Admin** button.
3. Provide the new operator's **Email**, **Full Name**, and set a temporary password.
4. Click **Create Account**.
5. The new super admin will go through the exact same **First Login and TOTP Setup** flow when they log in for the first time.

---

## 5. Daily Operational Use

As a super admin, your daily workflow should involve checking system health and tenant behavior:

* **Monitor the Dashboard**: Check for unusual spikes in tenant activity, active sessions, or system-wide revenue anomalies.
* **Review Audit Logs**: Navigate to the **Audit Logs** page (`/super-admin/audit-log`) regularly to ensure no unauthorized page reads or tenant impersonation sessions have occurred.
* **Grace Billing Reviews**: Track tenants whose subscriptions are in a 'grace' period to prompt them for payments before suspension occurs.
* **Alert Resolution**: If system health monitoring triggers alerts, inspect the active routers and API latency metrics on the health dashboard.
