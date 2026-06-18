"""
app/modules/routers/router.py
=============================
HTTP endpoints for managing MikroTik hotspot routers.
All operations are restricted to admin users and scoped to their tenant_id.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.database import get_db
from app.dependencies import require_role
from app.core.exceptions import NotFoundException
from app.core.audit import audit
from app.modules.routers.schemas import RouterCreate, RouterUpdate, RouterResponse
from app.modules.routers import service

router = APIRouter()


@router.post(
    "",
    response_model=RouterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new MikroTik router (admin only)",
)
@audit(action="create_router", target_type="router")
async def create_router(
    data: RouterCreate,
    user: dict = Depends(require_role("admin")),
) -> RouterResponse:
    tenant_id = UUID(user["tenant_id"])
    async with get_db() as conn:
        new_router = await service.create_router(conn, tenant_id, data)
    return RouterResponse.model_validate(new_router)


@router.get(
    "",
    response_model=list[RouterResponse],
    summary="List all registered routers (admin only)",
)
async def list_routers(
    user: dict = Depends(require_role("admin")),
) -> list[RouterResponse]:
    tenant_id = UUID(user["tenant_id"])
    async with get_db() as conn:
        routers = await service.get_routers(conn, tenant_id)
    return [RouterResponse.model_validate(r) for r in routers]


@router.get(
    "/{router_id}",
    response_model=RouterResponse,
    summary="Get details of a specific router (admin only)",
)
async def get_router(
    router_id: UUID,
    user: dict = Depends(require_role("admin")),
) -> RouterResponse:
    tenant_id = UUID(user["tenant_id"])
    async with get_db() as conn:
        router_device = await service.get_router_by_id(conn, tenant_id, router_id)
    if not router_device:
        raise NotFoundException("Router", str(router_id))
    return RouterResponse.model_validate(router_device)


@router.put(
    "/{router_id}",
    response_model=RouterResponse,
    summary="Update router details (admin only)",
)
@audit(action="update_router", target_type="router")
async def update_router(
    router_id: UUID,
    data: RouterUpdate,
    user: dict = Depends(require_role("admin")),
) -> RouterResponse:
    tenant_id = UUID(user["tenant_id"])
    async with get_db() as conn:
        updated_router = await service.update_router(conn, tenant_id, router_id, data)
    return RouterResponse.model_validate(updated_router)


@router.delete(
    "/{router_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a router configuration (admin only)",
)
@audit(action="delete_router", target_type="router")
async def delete_router(
    router_id: UUID,
    user: dict = Depends(require_role("admin")),
) -> None:
    tenant_id = UUID(user["tenant_id"])
    async with get_db() as conn:
        await service.delete_router(conn, tenant_id, router_id)
