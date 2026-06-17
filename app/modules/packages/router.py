"""
app/modules/packages/router.py
================================
HTTP endpoints for the packages module.

This replaces the stub router from Phase 2.

FastAPI path parameter types:
  {package_id: UUID} in the path tells FastAPI to:
    1. Extract the string from the URL.
    2. Try to parse it as a UUID.
    3. Return 422 if it's not a valid UUID (e.g. /packages/not-a-uuid).
  Without UUID type annotation, FastAPI passes it as a raw string and
  your service layer would fail with a cryptic asyncpg type error instead
  of a clean 422 Unprocessable Entity.

Dependency injection pattern:
  Each route takes `user: dict = Depends(require_role(...))`.
  require_role returns the decoded JWT payload as a dict:
    {"user_id": "...", "role": "admin", "reseller_id": "..."}
  We use user["user_id"] to stamp created_by on new packages.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.database import get_db
from app.dependencies import require_role
from app.modules.packages.schemas import PackageCreate, PackageUpdate, PackageResponse
from app.modules.packages.service import (
    get_all_packages,
    get_package_by_id,
    create_package,
    update_package,
    deactivate_package,
)

router = APIRouter()


@router.get(
    "",
    response_model=list[PackageResponse],
    summary="List all active packages",
)
async def list_packages(
    user: dict = Depends(require_role("admin", "reseller", "customer")),
) -> list[PackageResponse]:
    """Returns all active packages ordered by price ascending."""
    async with get_db() as conn:
        packages = await get_all_packages(conn)
    return packages


@router.get(
    "/{package_id}",
    response_model=PackageResponse,
    summary="Get a package by ID",
)
async def get_package(
    package_id: UUID,
    user: dict = Depends(require_role("admin", "reseller", "customer")),
) -> PackageResponse:
    """Fetches a single active package. Returns 404 if not found or soft-deleted."""
    async with get_db() as conn:
        package = await get_package_by_id(conn, package_id)
    return package


@router.post(
    "",
    response_model=PackageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new package (admin only)",
)
async def create_package_route(
    data: PackageCreate,
    user: dict = Depends(require_role("admin")),
) -> PackageResponse:
    """
    Creates a new WiFi package.

    The created_by field is taken from the authenticated admin's token —
    the client cannot supply it. This is intentional: if the client could
    set created_by, they could claim any admin created the package.
    """
    async with get_db() as conn:
        package = await create_package(conn, data, UUID(user["user_id"]))
    return package


@router.put(
    "/{package_id}",
    response_model=PackageResponse,
    summary="Update a package (admin only)",
)
async def update_package_route(
    package_id: UUID,
    data: PackageUpdate,
    user: dict = Depends(require_role("admin")),
) -> PackageResponse:
    """
    Partially updates a package. Only fields present in the body are updated.
    Returns the full updated package.
    """
    async with get_db() as conn:
        package = await update_package(conn, package_id, data)
    return package


@router.delete(
    "/{package_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a package (admin only)",
)
async def delete_package_route(
    package_id: UUID,
    user: dict = Depends(require_role("admin")),
) -> None:
    """
    Soft-deletes a package (sets is_active=False). Never hard-deletes.

    Returns 204 No Content on success — there's nothing to return because
    the resource is now "gone" from the client's perspective. 204 is the
    correct HTTP status for a successful DELETE that returns no body.

    The package record still exists in the DB to preserve payment history.
    """
    async with get_db() as conn:
        await deactivate_package(conn, package_id)
    # Returning None with status_code=204 makes FastAPI return an empty response body.
