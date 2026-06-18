import asyncio
import asyncpg
from app.config import settings
from app.worker import tenant_billing_cron

async def run_cron():
    pool = await asyncpg.create_pool(settings.DATABASE_URL)
    
    # First, let's update all tenants next_billing_date to today
    async with pool.acquire() as conn:
        await conn.execute("UPDATE tenants SET next_billing_date = NOW(), status = 'active' WHERE business_name LIKE 'Test%' OR id IS NOT NULL")
    
    # Run cron
    ctx = {"db_pool": pool}
    await tenant_billing_cron(ctx)
    
    await pool.close()

if __name__ == "__main__":
    asyncio.run(run_cron())
