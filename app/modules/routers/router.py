"""
app/modules/routers/router.py
=============================
HTTP endpoints for managing MikroTik hotspot routers.
All operations are restricted to admin users and scoped to their tenant_id.
"""

import subprocess
import re
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.config import settings
from app.database import get_db
from app.dependencies import require_role
from app.core.exceptions import NotFoundException, ConflictException
from app.core.audit import audit
from app.modules.routers.schemas import (
    RouterCreate,
    RouterUpdate,
    RouterResponse,
    OnboardingInitRequest,
    OnboardingInitResponse,
    RegisterPeerRequest,
    SaveCredentialsRequest,
    SetupProfilesRequest,
    RouterOnboardingRequest
)
from app.modules.routers import service
from app.integrations.wireguard import (
    assign_peer_ip,
    get_server_public_key,
    add_wireguard_peer,
    check_peer_connected
)

logger = logging.getLogger(__name__)

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


@router.post(
    "/onboarding/init",
    response_model=OnboardingInitResponse,
    summary="Initialize router onboarding (admin only)",
)
async def onboarding_init(
    data: OnboardingInitRequest,
    user: dict = Depends(require_role("admin")),
) -> OnboardingInitResponse:
    tenant_id = UUID(user["tenant_id"])
    async with get_db() as conn:
        # Enforce name uniqueness within the tenant
        existing = await conn.fetchval(
            "SELECT id FROM routers WHERE tenant_id = $1 AND name = $2",
            tenant_id,
            data.name,
        )
        if existing:
            raise ConflictException(f"A router with name '{data.name}' already exists.")

        assigned_ip = await assign_peer_ip(conn)
        zealsync_pubkey = get_server_public_key()

        # Insert PENDING router record (no host, port, username, password yet)
        row = await conn.fetchrow(
            """
            INSERT INTO routers (tenant_id, name, site_name, status, wireguard_assigned_ip, wireguard_public_key)
            VALUES ($1, $2, $3, 'pending_setup', $4::INET, $5)
            RETURNING id
            """,
            tenant_id,
            data.name,
            data.site_name,
            assigned_ip,
            zealsync_pubkey,
        )
        router_id = row["id"]

    return OnboardingInitResponse(
        router_id=router_id,
        zealsync_server_endpoint=settings.WIREGUARD_ENDPOINT,
        zealsync_public_key=zealsync_pubkey,
        assigned_ip=assigned_ip,
        server_wg_ip="10.8.0.1"
    )


@router.post(
    "/onboarding/register-peer",
    summary="Register the MikroTik's WireGuard public key (admin only)",
)
async def onboarding_register_peer(
    data: RegisterPeerRequest,
    user: dict = Depends(require_role("admin")),
):
    tenant_id = UUID(user["tenant_id"])
    async with get_db() as conn:
        router_row = await conn.fetchrow(
            "SELECT id, wireguard_assigned_ip FROM routers WHERE id = $1 AND tenant_id = $2",
            data.router_id,
            tenant_id,
        )
        if not router_row:
            raise NotFoundException("Router", str(data.router_id))

        assigned_ip = str(router_row["wireguard_assigned_ip"])
        
        # Call WireGuard CLI / mock to register the peer on ZealSync server
        add_wireguard_peer(data.peer_public_key, assigned_ip)

        # Update the router record with the peer's public key
        await conn.execute(
            """
            UPDATE routers
            SET wireguard_peer_public_key = $1
            WHERE id = $2 AND tenant_id = $3
            """,
            data.peer_public_key,
            data.router_id,
            tenant_id,
        )

    return {"success": True}


@router.post(
    "/onboarding/test-tunnel",
    summary="Test the WireGuard VPN tunnel connection (admin only)",
)
async def onboarding_test_tunnel(
    data: RouterOnboardingRequest,
    user: dict = Depends(require_role("admin")),
):
    tenant_id = UUID(user["tenant_id"])
    async with get_db() as conn:
        router_row = await conn.fetchrow(
            "SELECT id, wireguard_assigned_ip FROM routers WHERE id = $1 AND tenant_id = $2",
            data.router_id,
            tenant_id,
        )
        if not router_row:
            raise NotFoundException("Router", str(data.router_id))

        assigned_ip = str(router_row["wireguard_assigned_ip"])

    # Check connection handshake elapsed time
    connected = check_peer_connected(assigned_ip)
    latency_ms = None

    if connected:
        if settings.MOCK_WIREGUARD:
            # Return a realistic mock latency
            latency_ms = 15.4
        else:
            try:
                # Run actual ping to ensure IP traffic flows: ping -c 3 -W 2 {assigned_ip}
                res = subprocess.run(
                    ["ping", "-c", "3", "-W", "2", assigned_ip],
                    capture_output=True,
                    text=True,
                    timeout=8
                )
                if res.returncode == 0:
                    # Parse avg latency from summary line: rtt min/avg/max/mdev = min/avg/max/mdev ms
                    match = re.search(r"rtt min/avg/max/mdev = [\d\.]+/(?P<avg>[\d\.]+)/[\d\.]+/", res.stdout)
                    if match:
                        latency_ms = float(match.group("avg"))
                    else:
                        latency_ms = 0.0
                else:
                    connected = False
            except Exception as e:
                logger.error(f"Ping failed for tunnel test to {assigned_ip}: {e}")
                connected = False

    return {"connected": connected, "latency_ms": latency_ms}


@router.post(
    "/onboarding/save-credentials",
    summary="Save API credentials and move router to testing state (admin only)",
)
async def onboarding_save_credentials(
    data: SaveCredentialsRequest,
    user: dict = Depends(require_role("admin")),
):
    tenant_id = UUID(user["tenant_id"])
    async with get_db() as conn:
        router_row = await conn.fetchrow(
            "SELECT id, wireguard_assigned_ip FROM routers WHERE id = $1 AND tenant_id = $2",
            data.router_id,
            tenant_id,
        )
        if not router_row:
            raise NotFoundException("Router", str(data.router_id))

        assigned_ip = str(router_row["wireguard_assigned_ip"])
        
        from app.core.security import encrypt_secret
        encrypted_password = encrypt_secret(data.password)

        await conn.execute(
            """
            UPDATE routers
            SET host = $1, username = $2, password_encrypted = $3, port = $4, status = 'testing'
            WHERE id = $5 AND tenant_id = $6
            """,
            assigned_ip,
            data.username,
            encrypted_password,
            data.port,
            data.router_id,
            tenant_id,
        )

    return {"success": True}


@router.post(
    "/onboarding/test-api",
    summary="Test live connection to MikroTik REST API (admin only)",
)
async def onboarding_test_api(
    data: RouterOnboardingRequest,
    user: dict = Depends(require_role("admin")),
):
    tenant_id = UUID(user["tenant_id"])
    async with get_db() as conn:
        router_row = await conn.fetchrow(
            "SELECT id, host, port, username, password_encrypted FROM routers WHERE id = $1 AND tenant_id = $2",
            data.router_id,
            tenant_id,
        )
        if not router_row:
            raise NotFoundException("Router", str(data.router_id))

    if not router_row["host"] or not router_row["username"] or not router_row["password_encrypted"]:
        return {"connected": False, "error": "Router connection credentials are not configured"}

    try:
        from app.integrations.mikrotik import get_mikrotik_client
        router_dict = dict(router_row)
        if settings.MOCK_WIREGUARD and settings.MIKROTIK_HOST:
            router_dict["host"] = settings.MIKROTIK_HOST
        client = get_mikrotik_client(router_dict)
        profiles = await client.get_user_profile_names()
        return {"connected": True, "profiles": profiles}
    except Exception as e:
        logger.warning(f"Onboarding API connection test failed for router {data.router_id}: {e}")
        return {"connected": False, "error": str(e)}


@router.post(
    "/onboarding/setup-profiles",
    summary="Create speed tier hotspot user profiles on MikroTik (admin only)",
)
async def onboarding_setup_profiles(
    data: SetupProfilesRequest,
    user: dict = Depends(require_role("admin")),
):
    tenant_id = UUID(user["tenant_id"])
    async with get_db() as conn:
        router_row = await conn.fetchrow(
            "SELECT id, host, port, username, password_encrypted FROM routers WHERE id = $1 AND tenant_id = $2",
            data.router_id,
            tenant_id,
        )
        if not router_row:
            raise NotFoundException("Router", str(data.router_id))

    router_dict = dict(router_row)
    if settings.MOCK_WIREGUARD and settings.MIKROTIK_HOST:
        router_dict["host"] = settings.MIKROTIK_HOST

    from app.integrations.mikrotik import get_mikrotik_client
    client = get_mikrotik_client(router_dict)

    created = []
    failed = []

    # 1. Fetch existing profiles to check for duplicates and get their internal .ids
    existing_map = {}
    try:
        async with client._make_client() as http_client:
            get_resp = await http_client.get("/ip/hotspot/user/profile")
            if get_resp.is_success:
                profiles_data = get_resp.json()
                if isinstance(profiles_data, list):
                    for p in profiles_data:
                        if isinstance(p, dict) and "name" in p:
                            existing_map[p["name"]] = p.get(".id")
    except Exception as e:
        logger.warning(f"Failed to fetch existing user profiles from router {data.router_id}: {e}")

    # 2. Update existing profiles (PATCH) or create new ones (POST)
    async with client._make_client() as http_client:
        for profile in data.profiles:
            try:
                if profile.name in existing_map:
                    # Profile already exists. Update it using PATCH (without comment parameter)
                    internal_id = existing_map[profile.name]
                    response = await http_client.patch(
                        f"/ip/hotspot/user/profile/{internal_id}",
                        json={
                            "rate-limit": profile.rate_limit
                        }
                    )
                    if response.is_success:
                        created.append(profile.name)
                    else:
                        error_msg = response.text
                        try:
                            body = response.json()
                            error_msg = body.get("detail") or body.get("message") or error_msg
                        except:
                            pass
                        failed.append(f"{profile.name} (failed: {error_msg})")
                else:
                    # Profile does not exist. Create new using /add suffix (without comment parameter)
                    response = await http_client.post(
                        "/ip/hotspot/user/profile/add",
                        json={
                            "name": profile.name,
                            "rate-limit": profile.rate_limit
                        }
                    )
                    if response.is_success:
                        created.append(profile.name)
                    else:
                        error_msg = response.text
                        try:
                            body = response.json()
                            error_msg = body.get("detail") or body.get("message") or error_msg
                        except:
                            pass
                        failed.append(f"{profile.name} (failed: {error_msg})")
            except Exception as e:
                failed.append(f"{profile.name} (error: {str(e)})")

    return {"created": created, "failed": failed}


@router.post(
    "/onboarding/complete",
    summary="Complete onboarding wizard and activate router (admin only)",
)
async def onboarding_complete(
    data: RouterOnboardingRequest,
    user: dict = Depends(require_role("admin")),
):
    tenant_id = UUID(user["tenant_id"])
    async with get_db() as conn:
        router_row = await conn.fetchrow(
            "SELECT id FROM routers WHERE id = $1 AND tenant_id = $2",
            data.router_id,
            tenant_id,
        )
        if not router_row:
            raise NotFoundException("Router", str(data.router_id))

        await conn.execute(
            """
            UPDATE routers
            SET status = 'online'
            WHERE id = $1 AND tenant_id = $2
            """,
            data.router_id,
            tenant_id,
        )

    return {"router_id": str(data.router_id), "status": "online"}

