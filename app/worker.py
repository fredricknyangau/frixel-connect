"""
app/worker.py
==============
Entry point for the arq background worker process.
Defines database pool lifecycle hooks, tasks, and cron jobs.
"""

import asyncio
import logging
from arq import Retry, cron
from arq.connections import RedisSettings
import asyncpg

from app.config import settings
from app.modules.vouchers.service import generate_voucher
from app.modules.invoices.service import generate_invoice_for_payment

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars
from app.core.logging import setup_logging

# Configure logging for worker process
setup_logging(json_logs=settings.APP_ENV == "production")
logger = structlog.get_logger(__name__)


async def generate_voucher_task(ctx, payment_id: str, _request_id: str = None) -> str:
    """
    Durable background task to generate a voucher for a confirmed payment.
    Also generates an invoice for the payment.
    Instead of internal sleep loops, uses job-level retries handled by arq.
    
    Retry Policy:
      - Max tries: 4.
      - Backoff schedule: 5s, 15s, 45s.
      - On the 4th (final) attempt, records it as 'pending_provision' in the DB.
    """
    job_try = ctx.get("job_try", 1)
    max_tries = 4
    delays = [5, 15, 45]
    is_final_attempt = (job_try >= max_tries)

    clear_contextvars()
    if _request_id:
        bind_contextvars(request_id=_request_id)
    bind_contextvars(payment_id=payment_id)

    logger.info(
        "processing generate_voucher_task",
        job_try=job_try,
        max_tries=max_tries
    )

    pool = ctx["db_pool"]
    async with pool.acquire() as conn:
        try:
            # We call generate_voucher. If it fails, it bubbles up.
            code = await generate_voucher(conn, payment_id, is_final_attempt=is_final_attempt)
            logger.info(
                "generate_voucher_task succeeded",
                voucher_code=code
            )
            
            # Generate invoice for the payment
            try:
                await generate_invoice_for_payment(conn, payment_id)
            except Exception as e:
                # Invoice generation failure shouldn't fail the voucher, but log it
                logger.error("invoice generation failed", error=str(e), exc_info=True)
                
            return code
        except Exception as e:
            if is_final_attempt:
                logger.error(
                    "final attempt failed, voucher pending_provision",
                    job_try=job_try,
                    error=str(e)
                )
                raise e
            else:
                delay = delays[job_try - 1]
                logger.warning(
                    "attempt failed, retrying",
                    job_try=job_try,
                    delay_seconds=delay,
                    error=str(e)
                )
                raise Retry(defer=delay)


async def reconcile_payments_cron(ctx) -> None:
    """
    Reconciliation cron safety net running every 5 minutes.
    Queries confirmed payments older than 2 minutes that have NO corresponding
    voucher record, and enqueues the generate_voucher_task for them.
    """
    pool = ctx["db_pool"]
    redis = ctx["redis"]

    clear_contextvars()
    bind_contextvars(cron="reconcile_payments_cron")
    logger.info("running payments reconciliation check...")

    async with pool.acquire() as conn:
        stuck_payments = await conn.fetch(
            """
            SELECT id FROM payments p
            WHERE status = 'confirmed'
              AND created_at < NOW() - INTERVAL '2 minutes'
              AND NOT EXISTS (
                  SELECT 1 FROM vouchers v WHERE v.payment_id = p.id
              )
            """
        )

        if stuck_payments:
            logger.info(
                "found confirmed payments without vouchers. Re-enqueueing provisioning tasks...",
                count=len(stuck_payments)
            )
            for p in stuck_payments:
                payment_id = str(p["id"])
                # We do not pass _request_id from cron since it's an internal background event
                await redis.enqueue_job("generate_voucher_task", payment_id)
                logger.info("re-enqueued generate_voucher_task", payment_id=payment_id)
        else:
            logger.info("no stuck payments found")


async def sync_radius_sessions_cron(ctx) -> None:
    """
    Background cron running every 10 seconds.
    Syncs active and recently closed accounting records from FreeRADIUS radacct
    into our local sessions table.
    """
    pool = ctx["db_pool"]
    clear_contextvars()
    bind_contextvars(cron="sync_radius_sessions_cron")
    logger.info("running RADIUS sessions synchronization...")

    async with pool.acquire() as conn:
        try:
            result = await conn.execute(
                """
                INSERT INTO sessions (
                    voucher_id, customer_id, tenant_id, mac_address, ip_address, 
                    bytes_uploaded, bytes_downloaded, started_at, ended_at, acct_unique_id
                )
                SELECT 
                    v.id AS voucher_id,
                    v.customer_id,
                    v.tenant_id,
                    r.callingstationid AS mac_address,
                    r.framedipaddress AS ip_address,
                    COALESCE(r.acctinputoctets, 0) AS bytes_uploaded,
                    COALESCE(r.acctoutputoctets, 0) AS bytes_downloaded,
                    r.acctstarttime AS started_at,
                    r.acctstoptime AS ended_at,
                    r.acctuniqueid AS acct_unique_id
                FROM radacct r
                JOIN vouchers v ON r.username = v.code
                WHERE r.acctstoptime IS NULL 
                   OR r.acctstoptime > NOW() - INTERVAL '1 hour'
                ON CONFLICT (acct_unique_id) 
                DO UPDATE SET
                    bytes_uploaded = EXCLUDED.bytes_uploaded,
                    bytes_downloaded = EXCLUDED.bytes_downloaded,
                    ended_at = EXCLUDED.ended_at,
                    ip_address = EXCLUDED.ip_address,
                    mac_address = EXCLUDED.mac_address
                """
            )
            
            # Sync live bytes from MikroTik routers for active sessions
            from app.integrations.mikrotik import get_mikrotik_client
            routers = await conn.fetch("SELECT * FROM routers")
            for router_row in routers:
                try:
                    mikrotik = get_mikrotik_client(dict(router_row))
                    active_sessions = await mikrotik.get_active_sessions()
                    
                    for s_mk in active_sessions:
                        voucher_code = s_mk.get("user")
                        bytes_in = int(s_mk.get("bytes-in", 0))
                        bytes_out = int(s_mk.get("bytes-out", 0))
                        
                        if not voucher_code or (bytes_in == 0 and bytes_out == 0):
                            continue
                            
                        voucher_id = await conn.fetchval("SELECT id FROM vouchers WHERE code = $1", voucher_code)
                        if not voucher_id:
                            continue
                            
                        await conn.execute(
                            """
                            UPDATE sessions
                            SET 
                                bytes_uploaded = GREATEST(bytes_uploaded, $1),
                                bytes_downloaded = GREATEST(bytes_downloaded, $2)
                            WHERE voucher_id = $3 AND ended_at IS NULL
                            """,
                            bytes_in, bytes_out, voucher_id
                        )
                except Exception as e:
                    logger.error(f"Failed to sync live sessions from router {router_row['id']}", error=str(e))
            
            # Update vouchers with their activation and expiry times based on first session
            await conn.execute(
                """
                UPDATE vouchers v
                SET 
                    activated_at = s.first_start,
                    expires_at = s.first_start + (p.duration_minutes || ' minutes')::interval
                FROM (
                    SELECT voucher_id, MIN(started_at) as first_start
                    FROM sessions
                    GROUP BY voucher_id
                ) s, packages p
                WHERE v.id = s.voucher_id
                  AND v.package_id = p.id
                  AND v.activated_at IS NULL
                """
            )
            
            # Mark expired vouchers as 'expired' and forcefully disconnect them
            expired_vouchers = await conn.fetch(
                """
                UPDATE vouchers
                SET status = 'expired'
                WHERE status IN ('active', 'used') 
                  AND expires_at IS NOT NULL 
                  AND expires_at <= NOW()
                RETURNING id, code, router_id
                """
            )
            
            if expired_vouchers:
                for v in expired_vouchers:
                    # Remove from RADIUS to prevent reconnect
                    await conn.execute("DELETE FROM radcheck WHERE username = $1", v["code"])
                    await conn.execute("DELETE FROM radreply WHERE username = $1", v["code"])
                    
                    logger.info("Voucher expired. Revoking RADIUS credentials and disconnecting.", voucher=v["code"])
                    
                    # Forcefully disconnect active session
                    active_session = await conn.fetchrow(
                        """
                        SELECT HOST(nasipaddress) AS router_ip, acctsessionid
                        FROM radacct
                        WHERE username = $1 AND acctstoptime IS NULL
                        ORDER BY acctstarttime DESC
                        LIMIT 1
                        """,
                        v["code"]
                    )
                    
                    from app.integrations.mikrotik import get_mikrotik_client
                    
                    if active_session:
                        from app.integrations.radius_coa import send_coa_disconnect
                        # Attempt CoA disconnect
                        coa_success = await asyncio.to_thread(
                            send_coa_disconnect,
                            active_session["router_ip"],
                            v["code"],
                            active_session["acctsessionid"]
                        )
                        
                        if not coa_success:
                            logger.info("CoA disconnect failed for expired voucher. Falling back to MikroTik REST API.", voucher=v["code"])
                            router_dict = None
                            if v["router_id"]:
                                router_row = await conn.fetchrow("SELECT * FROM routers WHERE id = $1", v["router_id"])
                                if router_row:
                                    router_dict = dict(router_row)
                            
                            try:
                                mikrotik = get_mikrotik_client(router_dict)
                                await mikrotik.remove_active_hotspot_session(v["code"])
                            except Exception as e:
                                logger.error(f"Fallback disconnect via REST API failed for expired {v['code']}: {e}", exc_info=True)
                    else:
                        # Fallback directly to mikrotik API just in case
                        router_dict = None
                        if v["router_id"]:
                            router_row = await conn.fetchrow("SELECT * FROM routers WHERE id = $1", v["router_id"])
                            if router_row:
                                router_dict = dict(router_row)
                        
                        try:
                            mikrotik = get_mikrotik_client(router_dict)
                            await mikrotik.remove_active_hotspot_session(v["code"])
                        except Exception as e:
                            pass

            logger.info("RADIUS session sync completed", result=result)
        except Exception as e:
            logger.error("RADIUS session sync failed", error=str(e), exc_info=True)


async def pppoe_billing_cron(ctx) -> None:
    """
    Daily cron running at midnight to process PPPoE subscriptions.
    - Sends T-3, T-1, T+0 reminders
    - Suspends PPPoE secrets past grace period
    """
    pool = ctx["db_pool"]
    clear_contextvars()
    bind_contextvars(cron="pppoe_billing_cron")
    logger.info("running PPPoE billing check...")
    
    from app.integrations.africastalking import send_sms
    from app.integrations.mikrotik import get_mikrotik_client

    async with pool.acquire() as conn:
        try:
            # We need to find subscriptions and their customer's phone
            subs = await conn.fetch(
                """
                SELECT s.id, s.tenant_id, s.customer_id, s.status, s.current_period_end, s.auto_renew,
                       u.phone, u.router_id
                FROM subscriptions s
                JOIN users u ON s.customer_id = u.id
                WHERE s.status IN ('active', 'grace')
                """
            )

            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            
            for s in subs:
                days_left = (s["current_period_end"] - now).days
                phone = s["phone"]
                
                # T-3 reminder
                if days_left == 3 and s["auto_renew"]:
                    await send_sms(phone, "Your ZealSync WiFi subscription expires in 3 days. Please ensure you have sufficient funds to renew.")
                
                # T-1 reminder
                elif days_left == 1 and s["auto_renew"]:
                    await send_sms(phone, "Your ZealSync WiFi subscription expires tomorrow. Please renew to avoid disconnection.")
                
                # T+0 (entering grace)
                elif days_left == 0 and s["status"] == "active":
                    await conn.execute("UPDATE subscriptions SET status = 'grace', updated_at = NOW() WHERE id = $1", s["id"])
                    await send_sms(phone, "Your WiFi subscription has expired. You are now in a 24-hour grace period.")
                
                # Past grace (e.g. days_left < 0 or <= -1) -> Suspend
                elif days_left < 0 and s["status"] in ("active", "grace"):
                    # Suspend
                    await conn.execute("UPDATE subscriptions SET status = 'suspended', updated_at = NOW() WHERE id = $1", s["id"])
                    
                    # Disable PPPoE
                    if s["router_id"]:
                        router_row = await conn.fetchrow(
                            "SELECT host, port, username, password_encrypted FROM routers WHERE id = $1", s["router_id"]
                        )
                        if router_row:
                            client = get_mikrotik_client(dict(router_row))
                            # Using phone as PPPoE username
                            await client.disable_ppp_secret(phone)
                            
                    await send_sms(phone, "Your WiFi subscription has been suspended due to non-payment. Please pay to reconnect.")

            logger.info("PPPoE billing check completed")
        except Exception as e:
            logger.error("PPPoE billing check failed", error=str(e), exc_info=True)


async def tenant_billing_cron(ctx) -> None:
    """
    Daily cron running at midnight to process ZealSync's own platform billing.
    - Meters active customers vs max_customers.
    - Sends Daraja STK Push to tenant owner for their platform fee if next_billing_date is due.
    - Suspends tenants whose next_billing_date is past the 7-day grace period.
    """
    pool = ctx["db_pool"]
    clear_contextvars()
    bind_contextvars(cron="tenant_billing_cron")
    logger.info("running tenant metering and billing check...")

    from app.integrations.daraja import daraja_client
    
    TIER_PRICING = {
        "starter": 1000,
        "growth": 5000,
        "scale": 15000,
        "enterprise": 50000,
    }

    async with pool.acquire() as conn:
        try:
            tenants = await conn.fetch("SELECT id, business_name, owner_phone, subscription_tier, max_customers, status, next_billing_date FROM tenants")
            
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            
            for t in tenants:
                tenant_id = t["id"]
                
                # 1. Metering
                active_customers_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM users WHERE tenant_id = $1 AND role = 'customer' AND is_active = TRUE",
                    tenant_id
                )
                if active_customers_count > t["max_customers"]:
                    logger.warning(
                        "tenant exceeded max_customers limit",
                        tenant_id=str(tenant_id),
                        business_name=t["business_name"],
                        active_customers=active_customers_count,
                        max_customers=t["max_customers"],
                        subscription_tier=t["subscription_tier"]
                    )
            
                # 2. Billing & Suspension
                if t["status"] != "active":
                    continue
                
                next_billing_date = t["next_billing_date"]
                days_overdue = (now - next_billing_date).days
                
                if next_billing_date <= now:
                    if days_overdue > 7:
                        # Suspend
                        logger.warning("suspending tenant due to non-payment past grace period", tenant_id=str(tenant_id))
                        await conn.execute("UPDATE tenants SET status = 'suspended', updated_at = NOW() WHERE id = $1", tenant_id)
                    else:
                        # Bill
                        recent_push = await conn.fetchval(
                            """
                            SELECT COUNT(*) FROM platform_payments 
                            WHERE tenant_id = $1 
                              AND created_at > NOW() - INTERVAL '24 hours'
                              AND status IN ('pending', 'confirmed')
                            """, tenant_id
                        )
                        if recent_push == 0:
                            amount = TIER_PRICING.get(t["subscription_tier"], 1000)
                            phone = t["owner_phone"]
                            logger.info("initiating STK push for platform fee", tenant_id=str(tenant_id), amount=amount, phone=phone)
                            try:
                                result = await daraja_client.stk_push(
                                    phone=phone,
                                    amount=amount,
                                    account_reference=f"ZEALSYNC",
                                    description="ZealSync Platform"
                                )
                                await conn.execute(
                                    """
                                    INSERT INTO platform_payments (tenant_id, amount_kes, mpesa_checkout_id, phone_number, status)
                                    VALUES ($1, $2, $3, $4, 'pending')
                                    """,
                                    tenant_id, amount, result["CheckoutRequestID"], phone
                                )
                            except Exception as e:
                                logger.error("failed to initiate Daraja STK push for platform fee", tenant_id=str(tenant_id), error=str(e))

            logger.info("tenant billing check completed")
        except Exception as e:
            logger.error("tenant billing check failed", error=str(e), exc_info=True)




async def on_startup(ctx):
    """arq lifecycle hook triggered on worker container startup."""
    clear_contextvars()
    logger.info("initialising database connection pool...")
    # Initialize the database pool and bind to worker context
    pool = await asyncpg.create_pool(
        dsn=settings.DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    ctx["db_pool"] = pool
    logger.info("database connection pool created")


async def on_shutdown(ctx):
    """arq lifecycle hook triggered on worker container shutdown."""
    clear_contextvars()
    logger.info("closing database connection pool...")
    pool = ctx.get("db_pool")
    if pool:
        await pool.close()
        logger.info("database connection pool closed")


class WorkerSettings:
    """arq WorkerSettings configuration class."""
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    on_startup = on_startup
    on_shutdown = on_shutdown
    functions = [generate_voucher_task]
    cron_jobs = [
        cron(reconcile_payments_cron, minute=set(range(0, 60, 5))),
        cron(sync_radius_sessions_cron, second=set(range(0, 60, 10))),
        cron(pppoe_billing_cron, hour={0}, minute={0}),  # Run at midnight
        cron(tenant_billing_cron, hour={0}, minute={0}),  # Run at midnight
    ]

