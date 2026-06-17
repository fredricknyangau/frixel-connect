"""
app/modules/sessions/router.py
================================
Stub router for the sessions module — role guards wired, handlers not yet
implemented (Phase 8 completes them).

Mounted at /api/v1 in main.py. Full paths defined here.

Route-to-role mapping (full paths):
  GET /api/v1/sessions/me     → customer only
  GET /api/v1/admin/sessions  → admin only

Note: sessions are written by MikroTik accounting, not by this API.
This router only reads them. Phase 8 explains the full design.
"""

from fastapi import APIRouter, Depends

from app.dependencies import require_role

router = APIRouter()


@router.get(
    "/sessions/me",
    summary="Get own session history (customer only)",
)
async def get_my_sessions(
    _user: dict = Depends(require_role("customer")),
):
    return {"message": "not yet implemented — Phase 8"}


@router.get(
    "/admin/sessions",
    summary="List all sessions with pagination (admin only)",
)
async def list_all_sessions(
    _user: dict = Depends(require_role("admin")),
):
    return {"message": "not yet implemented — Phase 8"}
