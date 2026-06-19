-- =============================================================================
-- Migration: 003_create_payments.sql
-- Creates: payments table
-- Depends on: 001_create_users.sql, 002_create_packages.sql
-- =============================================================================

CREATE TABLE IF NOT EXISTS payments (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Which customer initiated this payment.
    -- ON DELETE RESTRICT: we refuse to delete a customer who has payments.
    -- Financial records are permanent -you cannot delete payment history.
    customer_id           UUID          NOT NULL REFERENCES users(id) ON DELETE RESTRICT,

    -- Which package the customer paid for.
    -- ON DELETE RESTRICT: same reason -package deletion would corrupt payment history.
    -- This is why packages use soft delete instead of hard delete.
    package_id            UUID          NOT NULL REFERENCES packages(id) ON DELETE RESTRICT,

    -- Snapshot of what they paid. We copy this from packages.price_kes at
    -- payment creation time. This is intentional: if the admin later changes
    -- the package price, historical payment records must NOT be affected.
    amount_kes            NUMERIC(10, 2) NOT NULL CHECK (amount_kes > 0),

    -- Payment lifecycle:
    -- pending   → STK push sent to Daraja, waiting for customer PIN
    -- confirmed → M-Pesa webhook arrived with ResultCode=0, receipt number recorded
    -- failed    → M-Pesa webhook arrived with ResultCode != 0
    -- cancelled → customer cancelled on their phone before entering PIN
    status                VARCHAR(20)   NOT NULL DEFAULT 'pending'
                              CHECK (status IN ('pending', 'confirmed', 'failed', 'cancelled')),

    -- THE MOST IMPORTANT CONSTRAINT IN THE ENTIRE DATABASE.
    -- Safaricom's Daraja API can and DOES fire the same webhook multiple times
    -- (network retries, timeout retries). Each webhook carries the same
    -- MpesaReceiptNumber. The UNIQUE constraint here means:
    --   - First webhook arrives → INSERT succeeds → payment confirmed
    --   - Second webhook arrives → INSERT fails with UniqueViolation → we catch it
    --     in the webhook handler, see the payment is already confirmed, return 200.
    -- Without this constraint, duplicate webhooks would create duplicate payments.
    -- The uniqueness is enforced at the database layer, not just application layer,
    -- because application-layer checks have TOCTOU race conditions under concurrent load.
    mpesa_receipt_number  VARCHAR(20)   UNIQUE,

    -- The CheckoutRequestID returned by Daraja when we initiate the STK push.
    -- We use this to match incoming webhooks back to the correct payment record.
    -- e.g. "ws_CO_260620261234567890"
    mpesa_checkout_id     VARCHAR(100),

    -- The phone number the STK push was sent to. We store it here because
    -- the webhook also includes it -useful for cross-referencing / debugging.
    phone_number          VARCHAR(20)   NOT NULL,

    -- Why did the payment fail? Populated from Daraja's ResultDesc on failure.
    -- e.g. "The initiator information is invalid.", "Request cancelled by user."
    failure_reason        TEXT,

    created_at            TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- ── Indexes ───────────────────────────────────────────────────────────────────

-- GET /payments/me -customer fetches their own payment history.
CREATE INDEX IF NOT EXISTS idx_payments_customer_id ON payments (customer_id);

-- Webhook handler: look up payment by CheckoutRequestID to find which payment
-- the incoming callback belongs to. This query runs inside the webhook timeout window.
CREATE INDEX IF NOT EXISTS idx_payments_checkout_id ON payments (mpesa_checkout_id);

-- GET /reseller/payments -resellers look at payments by their customers.
-- This index supports filtering by package_id or joining back to users.
CREATE INDEX IF NOT EXISTS idx_payments_package_id ON payments (package_id);

-- Status filtering for admin dashboard: "show me all pending payments"
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments (status);

-- Partial index: Daraja receipt lookups only happen on confirmed payments.
-- A partial index on confirmed rows is smaller and faster than a full index.
-- Note: IF NOT EXISTS does NOT work on partial index expressions in older PG versions.
-- PostgreSQL 15+ supports it. Since we're on PG 16 (docker-compose.yml), this is safe.
CREATE INDEX IF NOT EXISTS idx_payments_receipt_confirmed
    ON payments (mpesa_receipt_number)
    WHERE status = 'confirmed';
