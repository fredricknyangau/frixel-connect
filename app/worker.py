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

# Configure logging for worker process
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def generate_voucher_task(ctx, payment_id: str) -> str:
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

    logger.info(
        f"Worker: processing generate_voucher_task for payment '{payment_id}' "
        f"(attempt {job_try}/{max_tries})"
    )

    pool = ctx["db_pool"]
    async with pool.acquire() as conn:
        try:
            # We call generate_voucher. If it fails, it bubbles up.
            code = await generate_voucher(conn, payment_id, is_final_attempt=is_final_attempt)
            logger.info(
                f"Worker: generate_voucher_task succeeded for payment '{payment_id}' "
                f"-> voucher '{code}'"
            )
            
            # Generate invoice for the payment
            try:
                await generate_invoice_for_payment(conn, payment_id)
            except Exception as e:
                # Invoice generation failure shouldn't fail the voucher, but log it
                logger.error(f"Worker: invoice generation failed for payment '{payment_id}': {e}", exc_info=True)
                
            return code
        except Exception as e:
            if is_final_attempt:
                logger.error(
                    f"Worker: final attempt {job_try} failed for payment '{payment_id}'. "
                    f"Voucher marked as pending_provision: {e}"
                )
                raise e
            else:
                delay = delays[job_try - 1]
                logger.warning(
                    f"Worker: attempt {job_try} failed for payment '{payment_id}'. "
                    f"Retrying in {delay}s: {e}"
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

    logger.info("Cron: running payments reconciliation check...")

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
                f"Cron: found {len(stuck_payments)} confirmed payments without vouchers. "
                "Re-enqueueing provisioning tasks..."
            )
            for p in stuck_payments:
                payment_id = str(p["id"])
                await redis.enqueue_job("generate_voucher_task", payment_id)
                logger.info(f"Cron: re-enqueued generate_voucher_task for payment '{payment_id}'")
        else:
            logger.info("Cron: no stuck payments found.")


async def sync_radius_sessions_cron(ctx) -> None:
    """
    Background cron running every 10 seconds.
    Syncs active and recently closed accounting records from FreeRADIUS radacct
    into our local sessions table.
    """
    pool = ctx["db_pool"]
    logger.info("Cron: running RADIUS sessions synchronization...")

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
            logger.info(f"Cron: RADIUS session sync completed: {result}")
        except Exception as e:
            logger.error(f"Cron: RADIUS session sync failed: {e}", exc_info=True)


async def pppoe_billing_cron(ctx) -> None:
    """
    Daily cron running at midnight to process PPPoE subscriptions.
    - Sends T-3, T-1, T+0 reminders
    - Suspends PPPoE secrets past grace period
    """
    pool = ctx["db_pool"]
    logger.info("Cron: running PPPoE billing check...")
    
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

            logger.info("Cron: PPPoE billing check completed.")
        except Exception as e:
            logger.error(f"Cron: PPPoE billing check failed: {e}", exc_info=True)



async def on_startup(ctx):
    """arq lifecycle hook triggered on worker container startup."""
    logger.info("Worker: initialising database connection pool...")
    # Initialize the database pool and bind to worker context
    pool = await asyncpg.create_pool(
        dsn=settings.DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    ctx["db_pool"] = pool
    logger.info("Worker: database connection pool created.")


async def on_shutdown(ctx):
    """arq lifecycle hook triggered on worker container shutdown."""
    logger.info("Worker: closing database connection pool...")
    pool = ctx.get("db_pool")
    if pool:
        await pool.close()
        logger.info("Worker: database connection pool closed.")


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
    ]

