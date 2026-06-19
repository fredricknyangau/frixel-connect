"""
app/modules/users/router.py
============================
HTTP router for users module — fully tenant-scoped.

Every route extracts tenant_id from current_user["tenant_id"] and passes it
to the service layer. Routes never accept tenant_id as a query parameter or
path variable — it comes exclusively from the authenticated JWT, preventing
cross-tenant access at the transport layer.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.database import get_db
from app.dependencies import require_role
from app.modules.users.schemas import (
    UserResponse,
    UserUpdate,
    CreateCustomerRequest,
    AdminUserCreate,
    AdminResellerCreate,
    AdminUserUpdate,
)
from app.modules.users import service as users_service

router = APIRouter()


# ── Customer routes ────────────────────────────────────────────────────────────

@router.get(
    "/customers/me",
    response_model=UserResponse,
    summary="Get own profile (customer only)",
)
async def get_my_profile(
    user: dict = Depends(require_role("customer")),
) -> UserResponse:
    async with get_db() as conn:
        profile = await users_service.get_my_profile(
            conn,
            user_id=UUID(user["user_id"]),
            tenant_id=UUID(user["tenant_id"]),
        )
    return profile


@router.put(
    "/customers/me",
    response_model=UserResponse,
    summary="Update own contact info (customer only)",
)
async def update_my_profile(
    data: UserUpdate,
    user: dict = Depends(require_role("customer")),
) -> UserResponse:
    async with get_db() as conn:
        profile = await users_service.update_my_profile(
            conn,
            user_id=UUID(user["user_id"]),
            tenant_id=UUID(user["tenant_id"]),
            data=data,
        )
    return profile


@router.get(
    "/customers/me/export",
    summary="Export all personal data (customer only)",
)
async def export_my_data(
    user: dict = Depends(require_role("customer")),
):
    """
    Returns all PII tied to the customer as a structured JSON download.
    Provides data portability compliance under the Data Protection Act.
    """
    async with get_db() as conn:
        data = await users_service.export_customer_data(
            conn,
            tenant_id=UUID(user["tenant_id"]),
            user_id=UUID(user["user_id"]),
        )
    return data


@router.delete(
    "/customers/me",
    summary="Anonymize personal data (customer only)",
)
async def delete_my_account(
    user: dict = Depends(require_role("customer")),
):
    """
    Anonymizes PII fields (email, phone, name) while preserving financial records.
    We cannot hard-delete the user because payments and vouchers reference customer_id 
    by foreign key, and financial records cannot disappear.
    This fulfills the Right to Erasure by destroying identifiers but leaving the mathematical financial trail intact.
    """
    async with get_db() as conn:
        await users_service.anonymize_customer(
            conn,
            tenant_id=UUID(user["tenant_id"]),
            user_id=UUID(user["user_id"]),
        )
    return {"message": "Your personal identifiers have been erased successfully. Transactional history is preserved for compliance."}


# ── Reseller routes ────────────────────────────────────────────────────────────

@router.get(
    "/reseller/customers",
    response_model=list[UserResponse],
    summary="List customers (admin sees all, reseller sees own)",
)
async def list_customers(
    user: dict = Depends(require_role("admin", "reseller")),
) -> list[UserResponse]:
    async with get_db() as conn:
        customers = await users_service.list_customers(
            conn,
            tenant_id=UUID(user["tenant_id"]),
            caller_role=user["role"],
            caller_id=UUID(user["user_id"]),
        )
    return customers


@router.post(
    "/reseller/customers",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a customer under this reseller",
)
async def create_customer(
    data: CreateCustomerRequest,
    user: dict = Depends(require_role("admin", "reseller")),
) -> UserResponse:
    reseller_id = UUID(user["user_id"]) if user["role"] == "reseller" else None
    async with get_db() as conn:
        customer = await users_service.create_customer(
            conn,
            tenant_id=UUID(user["tenant_id"]),
            data=data,
            reseller_id=reseller_id,
        )
    return customer


# ── Admin routes ───────────────────────────────────────────────────────────────

@router.get(
    "/admin/users",
    response_model=list[UserResponse],
    summary="List all users in this tenant (admin only)",
)
async def list_all_users(
    user: dict = Depends(require_role("admin")),
) -> list[UserResponse]:
    async with get_db() as conn:
        users = await users_service.list_all_users(
            conn,
            tenant_id=UUID(user["tenant_id"]),
        )
    return users


@router.post(
    "/admin/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user of any role (admin only)",
)
async def create_user_admin(
    data: AdminUserCreate,
    user: dict = Depends(require_role("admin")),
) -> UserResponse:
    async with get_db() as conn:
        new_user = await users_service.admin_create_user(
            conn,
            tenant_id=UUID(user["tenant_id"]),
            data=data,
        )
    return new_user


@router.post(
    "/admin/resellers",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a reseller in this tenant (admin only)",
)
async def create_reseller_admin(
    data: AdminResellerCreate,
    user: dict = Depends(require_role("admin")),
) -> UserResponse:
    reseller_data = AdminUserCreate(
        email=data.email,
        phone=data.phone,
        password=data.password,
        role="reseller",
        reseller_id=None,
    )
    async with get_db() as conn:
        reseller = await users_service.admin_create_user(
            conn,
            tenant_id=UUID(user["tenant_id"]),
            data=reseller_data,
        )
    return reseller


@router.put(
    "/admin/users/{user_id}",
    response_model=UserResponse,
    summary="Update any user in this tenant (admin only)",
)
async def update_user_admin(
    user_id: UUID,
    data: AdminUserUpdate,
    user: dict = Depends(require_role("admin")),
) -> UserResponse:
    async with get_db() as conn:
        updated_user = await users_service.admin_update_user(
            conn,
            tenant_id=UUID(user["tenant_id"]),
            user_id=user_id,
            data=data,
        )
    return updated_user


@router.delete(
    "/admin/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate any user in this tenant (admin only)",
)
async def deactivate_user_admin(
    user_id: UUID,
    user: dict = Depends(require_role("admin")),
) -> None:
    async with get_db() as conn:
        await users_service.admin_deactivate_user(
            conn,
            tenant_id=UUID(user["tenant_id"]),
            user_id=user_id,
        )
