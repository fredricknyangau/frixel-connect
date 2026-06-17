from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.core.exceptions import UnauthorisedException, ForbiddenException
from app.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Decodes the JWT and returns the current user's identity dict.
    Raises 401 if the token is missing, expired, or invalid.
    """
    payload = decode_access_token(token)
    if payload is None:
        raise UnauthorisedException()

    user_id: str | None = payload.get("sub")
    role: str | None = payload.get("role")

    if user_id is None or role is None:
        raise UnauthorisedException()

    return {
        "user_id": user_id,
        "role": role,
        "reseller_id": payload.get("reseller_id"),
    }


def require_role(*allowed_roles: str):
    """
    Dependency factory. Enforces role-based access at the route level.

    Usage:
        @router.get("/admin/users")
        async def list_users(user=Depends(require_role("admin"))):
            ...

        @router.get("/reseller/customers")
        async def list_customers(user=Depends(require_role("admin", "reseller"))):
            ...
    """
    async def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in allowed_roles:
            raise ForbiddenException(
                detail=f"Required role: {allowed_roles}. Your role: {current_user['role']}"
            )
        return current_user

    return role_checker