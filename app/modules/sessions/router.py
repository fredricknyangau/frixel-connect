"""
app/modules/sessions/router.py
================================
Router exposing HTTP endpoints for querying client network connection sessions.
"""

from fastapi import APIRouter, Depends, Query, status

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
    """
    Returns the collection of active and closed hotspot sessions associated with
    the authenticated customer's device.
    """
    async with get_db() as conn:
        sessions = await get_customer_sessions(conn, current_user["user_id"])
    return sessions


@router.get(
    "/admin/sessions",
    response_model=list[SessionResponse],
    summary="List all hotspot sessions (admin only)",
)
async def list_all_sessions(
    limit: int = Query(50, ge=1, le=100, description="Number of sessions to return (max 100)"),
    offset: int = Query(0, ge=0, description="Offset index for pagination"),
    _user: dict = Depends(require_role("admin")),
):
    """
    Returns a paginated list of all customer login sessions. Restricted to administrators.
    """
    async with get_db() as conn:
        sessions = await get_all_sessions(conn, limit=limit, offset=offset)
    return sessions
