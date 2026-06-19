"""
app/modules/sessions/router.py
================================
Router for session queries -fully tenant-scoped.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.database import get_db
from app.dependencies import require_role
from app.modules.sessions.schemas import SessionResponse
from app.modules.sessions.service import get_customer_sessions, get_all_sessions

router = APIRouter()


@router.get(
    "/sessions/me",
    response_model=list[SessionResponse],
    summary="Get own hotspot sessions (customer only)",
)
async def get_my_sessions(
    current_user: dict = Depends(require_role("customer")),
):
    async with get_db() as conn:
        sessions = await get_customer_sessions(
            conn,
            tenant_id=UUID(current_user["tenant_id"]),
            customer_id=current_user["user_id"],
        )
    return sessions


@router.get(
    "/admin/sessions",
    response_model=list[SessionResponse],
    summary="List all hotspot sessions in this tenant (admin only)",
)
async def list_all_sessions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(require_role("admin")),
):
    async with get_db() as conn:
        sessions = await get_all_sessions(
            conn,
            tenant_id=UUID(current_user["tenant_id"]),
            limit=limit,
            offset=offset,
        )
    return sessions
