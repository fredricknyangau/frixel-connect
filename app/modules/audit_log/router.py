from uuid import UUID
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
import asyncpg
from datetime import datetime

from app.database import get_db
from app.dependencies import require_role

router = APIRouter(prefix="/admin/audit-log", tags=["Audit Log"])

class ActorInfo(BaseModel):
    id: str
    email: str
    phone: str

class AuditLogEntry(BaseModel):
    id: str
    tenant_id: str
    actor_user_id: str
    action: str
    target_type: str
    target_id: Optional[str]
    metadata: Dict[str, Any]
    created_at: datetime
    actor: Optional[ActorInfo]

class AuditLogResponse(BaseModel):
    items: List[AuditLogEntry]
    total: int

@router.get("", response_model=AuditLogResponse)
async def get_audit_logs(
    action: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(require_role("admin"))
):
    tenant_id = UUID(str(current_user["tenant_id"]))
    
    async with get_db() as conn:
        # Build query
        base_query = """
            FROM audit_log a
            LEFT JOIN users u ON a.actor_user_id = u.id
            WHERE a.tenant_id = $1
        """
        args = [tenant_id]
        
        if action:
            base_query += " AND a.action = $2"
            args.append(action)
            
        # Count total
        count_query = f"SELECT COUNT(*) {base_query}"
        total = await conn.fetchval(count_query, *args)
        
        # Fetch items
        data_query = f"""
            SELECT 
                a.*,
                u.email as actor_email,
                u.phone as actor_phone
            {base_query}
            ORDER BY a.created_at DESC
            LIMIT ${len(args) + 1} OFFSET ${len(args) + 2}
        """
        args.extend([limit, offset])
        
        rows = await conn.fetch(data_query, *args)
        
        items = []
        for r in rows:
            actor = None
            if r["actor_user_id"]:
                actor = ActorInfo(
                    id=str(r["actor_user_id"]),
                    email=r["actor_email"] or "",
                    phone=r["actor_phone"] or ""
                )
                
            # metadata in DB is JSONB, asyncpg returns string or dict.
            import json
            meta = r["metadata"]
            if isinstance(meta, str):
                meta = json.loads(meta)
                
            items.append(AuditLogEntry(
                id=str(r["id"]),
                tenant_id=str(r["tenant_id"]),
                actor_user_id=str(r["actor_user_id"]),
                action=r["action"],
                target_type=r["target_type"],
                target_id=str(r["target_id"]) if r["target_id"] else None,
                metadata=meta or {},
                created_at=r["created_at"],
                actor=actor
            ))
            
        return AuditLogResponse(items=items, total=total)
