"""
app/modules/packages/router.py
==============================
Stub router for the packages module — role guards wired, handlers not yet
implemented (Phase 3 completes them).

WHY add role guards NOW even though handlers return placeholder responses?
Because it's trivially easy to add a guard to a stub route but very easy
to FORGET to add it later when you're deep in service logic. If we ship
Phase 3 with a route that accidentally has no guard, any logged-in user
(or unauthenticated attacker with a stolen token) can call admin routes.

"Secure by default" means every route must opt IN to being public, not
opt IN to being protected. Adding the guard now locks the door. Phase 3
just fills in the room behind it.
"""

from fastapi import APIRouter, Depends

from app.dependencies import require_role

router = APIRouter()


# ── Public-ish (any authenticated user) ──────────────────────────────────────

@router.get(
    "",
    summary="List all active packages",
    dependencies=[Depends(require_role("admin", "reseller", "customer"))],
)
async def list_packages(
    _user: dict = Depends(require_role("admin", "reseller", "customer")),
):
    # Phase 3 will replace this with the real service call.
    return {"message": "not yet implemented — Phase 3"}


@router.get(
    "/{package_id}",
    summary="Get a package by ID",
)
async def get_package(
    package_id: str,
    _user: dict = Depends(require_role("admin", "reseller", "customer")),
):
    return {"message": "not yet implemented — Phase 3"}


# ── Admin only ────────────────────────────────────────────────────────────────

@router.post(
    "",
    status_code=201,
    summary="Create a new package (admin only)",
)
async def create_package(
    _user: dict = Depends(require_role("admin")),
):
    return {"message": "not yet implemented — Phase 3"}


@router.put(
    "/{package_id}",
    summary="Update a package (admin only)",
)
async def update_package(
    package_id: str,
    _user: dict = Depends(require_role("admin")),
):
    return {"message": "not yet implemented — Phase 3"}


@router.delete(
    "/{package_id}",
    summary="Soft-delete a package (admin only)",
)
async def delete_package(
    package_id: str,
    _user: dict = Depends(require_role("admin")),
):
    return {"message": "not yet implemented — Phase 3"}
