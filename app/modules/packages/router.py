"""
app/modules/packages/router.py
================================
HTTP endpoints for the packages module — fully tenant-scoped.

Every service call now passes tenant_id extracted from the authenticated
user's JWT. A customer in tenant A cannot see tenant B's packages because
the service scopes every query to tenant_id.
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
    summary="List all active packages in this tenant",
)
async def list_packages(
    user: dict = Depends(require_role("admin", "reseller", "customer")),
) -> list[PackageResponse]:
    """Returns all active packages for the caller's tenant, ordered by price."""
    async with get_db() as conn:
        packages = await get_all_packages(conn, tenant_id=UUID(user["tenant_id"]))
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
    """Fetches a single active package. Returns 404 for cross-tenant UUIDs."""
    async with get_db() as conn:
        package = await get_package_by_id(
            conn,
            tenant_id=UUID(user["tenant_id"]),
            package_id=package_id,
        )
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
    async with get_db() as conn:
        package = await create_package(
            conn,
            tenant_id=UUID(user["tenant_id"]),
            data=data,
            created_by_user_id=UUID(user["user_id"]),
        )
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
    async with get_db() as conn:
        package = await update_package(
            conn,
            tenant_id=UUID(user["tenant_id"]),
            package_id=package_id,
            data=data,
        )
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
    async with get_db() as conn:
        await deactivate_package(
            conn,
            tenant_id=UUID(user["tenant_id"]),
            package_id=package_id,
        )
