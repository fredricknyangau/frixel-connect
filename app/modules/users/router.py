"""
app/modules/users/router.py
============================
Stub router for the users module — role guards wired, handlers not yet
implemented (Phase 6 completes them).

Route-to-role mapping:
  GET  /customers/me         → customer only
  PUT  /customers/me         → customer only
  GET  /reseller/customers   → admin, reseller
  POST /reseller/customers   → admin, reseller
  GET  /admin/users          → admin only

Note on the prefix: this router is mounted at /api/v1 (no sub-prefix)
in main.py, so the full paths are exactly as listed above. The
/customers/, /reseller/, and /admin/ distinctions are in the path itself,
not in separate routers. This is intentional — it keeps the role
semantics visible in the URL, which makes nginx access log auditing easy.
"""

from fastapi import APIRouter, Depends

from app.dependencies import require_role

router = APIRouter()


# ── Customer routes ────────────────────────────────────────────────────────────

@router.get(
    "/customers/me",
    summary="Get own profile (customer only)",
)
async def get_my_profile(
    _user: dict = Depends(require_role("customer")),
):
    return {"message": "not yet implemented — Phase 6"}


@router.put(
    "/customers/me",
    summary="Update own contact info (customer only)",
)
async def update_my_profile(
    _user: dict = Depends(require_role("customer")),
):
    return {"message": "not yet implemented — Phase 6"}


# ── Reseller routes ────────────────────────────────────────────────────────────

@router.get(
    "/reseller/customers",
    summary="List customers (admin sees all, reseller sees own)",
)
async def list_customers(
    _user: dict = Depends(require_role("admin", "reseller")),
):
    return {"message": "not yet implemented — Phase 6"}


@router.post(
    "/reseller/customers",
    status_code=201,
    summary="Create a customer under this reseller",
)
async def create_customer(
    _user: dict = Depends(require_role("admin", "reseller")),
):
    return {"message": "not yet implemented — Phase 6"}


# ── Admin routes ───────────────────────────────────────────────────────────────

@router.get(
    "/admin/users",
    summary="List all users of any role (admin only)",
)
async def list_all_users(
    _user: dict = Depends(require_role("admin")),
):
    return {"message": "not yet implemented — Phase 6"}
