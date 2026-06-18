from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List
from datetime import datetime, timezone
import asyncpg

from app.database import get_db
from app.dependencies import require_role
from app.core.redis import get_redis_pool

router = APIRouter(prefix="/admin/system-health", tags=["System Health"])

class RouterHealth(BaseModel):
    id: str
    name: str
    status: str
    last_seen: str
    uptime_seconds: int
    active_hotspot_users: int

class SystemHealthResponse(BaseModel):
    status: str
    queue_depth: int
    unreconciled_payments: int
    active_routers: int
    total_routers: int
    stuck_payments_count: int
    webhook_success_rate: float
    routers: List[RouterHealth]

@router.get("", response_model=SystemHealthResponse)
async def get_system_health(current_user: dict = Depends(require_role("admin"))):
    tenant_id = UUID(str(current_user["tenant_id"]))
    
    # 1. ARQ Queue Depth
    redis = get_redis_pool()
    # Count pending jobs in arq:queue
    queue_depth = await redis.zcard("arq:queue") or 0
    
    async with get_db() as conn:
        # 2. Unreconciled Payments (pending for > 5 mins)
        unreconciled_payments = await conn.fetchval(
            """
            SELECT COUNT(*) FROM payments 
            WHERE tenant_id = $1 AND status = 'pending' 
            AND created_at < NOW() - INTERVAL '5 minutes'
            """,
            tenant_id
        )
        
        # 3. Stuck Payments (confirmed with no vouchers)
        stuck_payments_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM payments p
            LEFT JOIN vouchers v ON p.id = v.payment_id
            WHERE p.tenant_id = $1 AND p.status = 'confirmed' AND v.id IS NULL
            """,
            tenant_id
        )
        
        # 4. Routers Status
        routers_rows = await conn.fetch(
            "SELECT id, name, last_heartbeat_at FROM routers WHERE tenant_id = $1",
            tenant_id
        )
        
        routers_down = 0
        routers_degraded = 0
        now = datetime.now(timezone.utc)
        total_routers = len(routers_rows)
        active_routers = 0
        routers = []
        
        for r in routers_rows:
            last_seen = r["last_heartbeat_at"]
            status = "offline"
            uptime = 0
            if last_seen and (now - last_seen).total_seconds() < 120:
                status = "online"
                active_routers += 1
                uptime = int((now - last_seen).total_seconds())
                
            routers.append(RouterHealth(
                id=str(r["id"]),
                name=r["name"],
                status=status,
                last_seen=last_seen.isoformat() if last_seen else now.isoformat(),
                uptime_seconds=uptime,
                active_hotspot_users=0 # Mocked for MLP
            ))
            
    # Calculate overall status
    overall_status = "healthy"
    if queue_depth > 50 or stuck_payments_count > 0:
        overall_status = "degraded"
    if active_routers == 0 and total_routers > 0:
        overall_status = "down"

    return SystemHealthResponse(
        status=overall_status,
        queue_depth=queue_depth,
        unreconciled_payments=unreconciled_payments,
        active_routers=active_routers,
        total_routers=total_routers,
        stuck_payments_count=stuck_payments_count,
        webhook_success_rate=99.9, # Mocked for MLP
        routers=routers
    )
