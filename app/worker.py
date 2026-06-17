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

# Configure logging for worker process
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def generate_voucher_task(ctx, payment_id: str) -> str:
    """
    Durable background task to generate a voucher for a confirmed payment.
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
        cron(reconcile_payments_cron, minute=set(range(0, 60, 5)))
    ]
