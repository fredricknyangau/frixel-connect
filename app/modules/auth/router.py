"""
app/modules/auth/router.py
==========================
HTTP endpoints for authentication.

FastAPI's APIRouter is a mini-application: it groups related routes,
applies shared prefixes/tags, and gets mounted onto the main app in main.py.

Route handler anatomy:
  @router.post("/register", status_code=201)
   │             │               └── Default HTTP status on success.
   │             └── Path relative to this router's prefix.
   └── HTTP method.

  async def register(data: RegisterRequest = Body(...), ...)
   │                  └── Pydantic model — FastAPI parses and validates the
   │                        JSON body, returns 422 automatically if invalid.
   └── async def because we're using async I/O (asyncpg, not blocking psql).

Why 201 for register and 200 for login?
  201 Created: a new resource (user) was created in the database.
  200 OK: we validated credentials and returned a token — no new resource.
  HTTP semantics matter: they tell API consumers what happened without
  reading the body. GET/200, POST new resource/201, POST action/200.
"""

from fastapi import APIRouter, status

from app.database import get_db
from app.core.security import create_access_token
from app.modules.auth.schemas import RegisterRequest, LoginRequest, TokenResponse
from app.modules.auth.service import register_user, authenticate_user

router = APIRouter()


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(data: RegisterRequest) -> TokenResponse:
    """
    Creates a new user account and returns an access token.

    Auto-login on register: the response is a TokenResponse identical to
    the login response. The client stores the token and is immediately
    authenticated — no second request needed.
    """
    async with get_db() as conn:
        # register_user raises ConflictException (409) if email/phone exists.
        # FastAPI catches HTTPException subclasses automatically and returns
        # the correct HTTP response — we don't need a try/except here.
        user = await register_user(conn, data)

    # Build the JWT. The token contains user_id, role, and reseller_id so
    # that every subsequent request can be authorised WITHOUT a database
    # lookup — the token is self-contained.
    token = create_access_token(
        user_id=str(user["id"]),
        role=user["role"],
        reseller_id=str(user["reseller_id"]) if user["reseller_id"] else None,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user["role"],
        user_id=user["id"],
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Login and obtain an access token",
)
async def login(data: LoginRequest) -> TokenResponse:
    """
    Validates credentials and returns an access token.

    The token is stateless — we don't store sessions in the database.
    Logout is handled client-side by discarding the token.

    Trade-off of stateless JWTs vs session tokens:
    - JWT CANNOT be invalidated before expiry without a token blacklist.
    - Session tokens can be revoked instantly (delete from DB), but require
      a DB lookup on EVERY request.
    For a WiFi billing system where tokens expire in 30 minutes, the
    simplicity of JWTs outweighs the limitation. If we need instant
    revocation later (e.g. emergency account lockout), we add Redis.
    """
    async with get_db() as conn:
        # authenticate_user raises UnauthorisedException (401) on bad creds.
        user = await authenticate_user(conn, data.email, data.password)

    token = create_access_token(
        user_id=str(user["id"]),
        role=user["role"],
        reseller_id=str(user["reseller_id"]) if user["reseller_id"] else None,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user["role"],
        user_id=user["id"],
    )
