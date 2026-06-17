"""
app/modules/users/router.py
============================
HTTP router and controllers for the users module.

This module implements:
  - Customer self-profile retrieval and partial updates.
  - Reseller operations (listing/creating customers under their ID).
  - Admin tools (listing all system accounts).

All routes enforce strict role guards (RBAC) via require_role dependencies.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.database import get_db
from app.dependencies import require_role
from app.modules.users.schemas import UserResponse, UserUpdate, CreateCustomerRequest
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
    """
    Returns the authenticated customer's database profile.
    Includes active status, role, and registered contact information.
    """
    async with get_db() as conn:
        profile = await users_service.get_my_profile(conn, UUID(user["user_id"]))
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
    """
    Allows a customer to update their own phone number.
    Returns the updated profile upon successful validation.
    """
    async with get_db() as conn:
        profile = await users_service.update_my_profile(conn, UUID(user["user_id"]), data)
    return profile


# ── Reseller routes ────────────────────────────────────────────────────────────

@router.get(
    "/reseller/customers",
    response_model=list[UserResponse],
    summary="List customers (admin sees all, reseller sees own)",
)
async def list_customers(
    user: dict = Depends(require_role("admin", "reseller")),
) -> list[UserResponse]:
    """
    Lists customer accounts with role-based partitioning:
      - Admin sees all customers.
      - Reseller sees only customers created under their account.
    """
    async with get_db() as conn:
        customers = await users_service.list_customers(
            conn,
            user["role"],
            UUID(user["user_id"]),
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
    """
    Registers a new customer account.
    
    If the caller is a Reseller:
        - The new customer's `reseller_id` is automatically set to the reseller's user ID.
    If the caller is an Admin:
        - The `reseller_id` is set to None (customer belongs to the parent ISP).
    """
    reseller_id = UUID(user["user_id"]) if user["role"] == "reseller" else None
    async with get_db() as conn:
        customer = await users_service.create_customer(conn, data, reseller_id)
    return customer


# ── Admin routes ───────────────────────────────────────────────────────────────

@router.get(
    "/admin/users",
    response_model=list[UserResponse],
    summary="List all users of any role (admin only)",
)
async def list_all_users(
    user: dict = Depends(require_role("admin")),
) -> list[UserResponse]:
    """
    Admin-only route listing every registered user (admins, resellers, and customers)
    ordered by created date descending.
    """
    async with get_db() as conn:
        users = await users_service.list_all_users(conn)
    return users
