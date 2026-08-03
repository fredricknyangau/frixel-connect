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
    RouterOnboardingRequest,
    MagicInitRequest,
    MagicInitResponse,
    RouterStatusResponse,
    RouterProvisionRequest,
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
        server_public_key = get_server_public_key()

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
            server_public_key,
        )
        router_id = row["id"]

    return OnboardingInitResponse(
        router_id=router_id,
        frixel_connect_server_endpoint=settings.WIREGUARD_ENDPOINT,
        frixel_connect_public_key=server_public_key,
        assigned_ip=assigned_ip,
        server_wg_ip="10.8.0.1",
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
        
        # Call WireGuard CLI / mock to register the peer on Frixel Connect server
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


@router.post(
    "/onboarding/init-magic",
    response_model=MagicInitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initialize Magic Command router onboarding (admin only)",
)
async def onboarding_init_magic(
    data: MagicInitRequest,
    user: dict = Depends(require_role("admin")),
) -> MagicInitResponse:
    """
    The entry point for the Magic Command onboarding flow.

    Performs ALL setup in a single atomic operation:
      1. Assign next available WireGuard IP from 10.8.0.2-10.8.0.254
      2. Generate WireGuard keypair (private key embedded in .rsc script)
      3. Generate API password (embedded in .rsc script, encrypted in DB)
      4. Generate single-use setup token (43 chars, 256-bit entropy)
      5. INSERT router record (status='pending_setup')
      6. INSERT setup_tokens record (with private key and encrypted password)
      7. Pre-register WireGuard peer on the server side
         WHY PRE-REGISTER: If we can't add the peer now, showing the admin
         the magic command would be pointless-the VPN tunnel won't establish.
         Fail early so we never show an unusable command.
      8. Return the magic_command string ready to paste into MikroTik terminal

    CHR vs Production:
      is_chr=True:  magic_command uses http://192.168.56.1:8000/...
                    No WireGuard commands in the .rsc script
      is_chr=False: magic_command uses https://api.Frixel Connect.dev/...
                    Full WireGuard setup in the .rsc script
    """
    from datetime import datetime, timedelta, timezone
    from app.services.script_generator import (
        generate_wireguard_keypair,
        generate_api_password,
        generate_setup_token,
    )
    from app.core.security import encrypt_secret

    tenant_id = UUID(user["tenant_id"])

    async with get_db() as conn:
        # ── Enforce name uniqueness within the tenant ──────────────────────────
        existing = await conn.fetchval(
            "SELECT id FROM routers WHERE tenant_id = $1 AND name = $2",
            tenant_id,
            data.name,
        )
        if existing:
            raise ConflictException(f"A router with name '{data.name}' already exists.")

        # ── Step 1: Assign WireGuard IP ────────────────────────────────────────
        assigned_ip = await assign_peer_ip(conn)

        # ── Step 2: Generate WireGuard keypair ────────────────────────────────
        # Server generates BOTH keys so the private key can be embedded in the
        # .rsc script. This enables the single-command UX. See script_generator.py
        # for the full security rationale.
        #
        # For CHR mode: we still generate a keypair even though the script won't
        # use it. This keeps the code path consistent and the DB record complete.
        # The wireguard_peer_public_key column will be populated for non-CHR routers.
        wg_private_key, wg_public_key = generate_wireguard_keypair()

        # ── Step 3: Generate API password and setup token ──────────────────────
        api_password_plain = generate_api_password()
        api_password_encrypted = encrypt_secret(api_password_plain)
        setup_token = generate_setup_token()

        # ── Step 4 + 5: INSERT router record ───────────────────────────────────
        # For CHR mode: wireguard_peer_public_key is NULL-no real WG peer.
        # The setup/router.py uses this NULL to infer is_chr when serving the script.
        # For production: the public key is saved and the peer is pre-registered.
        wg_peer_key_to_save = None if data.is_chr else wg_public_key

        router_row = await conn.fetchrow(
            """
            INSERT INTO routers (
                tenant_id, name, site_name, status,
                wireguard_assigned_ip, wireguard_public_key, wireguard_peer_public_key,
                host, port, username, password_encrypted
            )
            VALUES ($1, $2, $3, 'pending_setup', $4::INET, $5, $6, $7, $8, $9, $10)
            RETURNING id
            """,
            tenant_id,
            data.name,
            data.site_name,
            assigned_ip,
            get_server_public_key(),     # server's WG public key (what Frixel Connect_public_key was before)
            wg_peer_key_to_save,         # router's WG public key (NULL for CHR)
            assigned_ip,                 # host = WG assigned IP (how the backend reaches the router)
            80,                          # port = REST API port
            "Frixel Connect-api",              # username (created by the script)
            api_password_encrypted,      # encrypted API password
        )
        router_id = router_row["id"]

        # ── Step 6: INSERT setup_tokens record ────────────────────────────────
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        await conn.execute(
            """
            INSERT INTO setup_tokens (
                tenant_id, router_id, token,
                router_wg_private_key, api_password, expires_at
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            tenant_id,
            router_id,
            setup_token,
            wg_private_key,          # stored temporarily, NULLed on /confirm
            api_password_encrypted,  # Fernet-encrypted, same as routers table
            expires_at,
        )

    # ── Step 7: Pre-register WireGuard peer on server ─────────────────────────
    # Done OUTSIDE the DB transaction because wg CLI is not transactional.
    # If this fails, we raise immediately before showing the admin any command.
    # The router record and token are already in the DB-they'll be cleaned
    # up by the 24-hour expiry. A failed pre-registration means the magic
    # command would produce a router that can't VPN, so we block early.
    #
    # CHR MODE: add_wireguard_peer() is a no-op mock (MOCK_WIREGUARD=True).
    # For physical routers with MOCK_WIREGUARD=False, this actually registers
    # the peer on the wg0 interface.
    if not data.is_chr:
        try:
            add_wireguard_peer(wg_public_key, assigned_ip)
        except Exception as wg_err:
            logger.error(f"Failed to pre-register WireGuard peer for router '{data.name}': {wg_err}")
            # In development (MOCK_WIREGUARD=True), this will never fail.
            # In production, if wg fails, we should not surface the command.
            raise

    # ── Step 8: Build the magic command string ────────────────────────────────
    if data.is_chr:
        # CHR: fetch from Ubuntu host-only IP over plain HTTP
        # The CHR VM can reach 192.168.56.1 (Ubuntu) via the host-only adapter.
        script_url = f"http://{settings.CHR_HOST_IP}:{settings.CHR_BACKEND_PORT}/api/v1/setup/{setup_token}"
        magic_command = (
            f'/tool fetch url="{script_url}" '
            f'dst-path=Frixel Connect-setup.rsc mode=http; '
            f'/import Frixel Connect-setup.rsc'
        )
    else:
        # Production: fetch from public HTTPS API endpoint
        script_url = f"{settings.API_BASE_URL}/api/v1/setup/{setup_token}"
        magic_command = (
            f'/tool fetch url="{script_url}" '
            f'dst-path=Frixel Connect-setup.rsc mode=https; '
            f'/import Frixel Connect-setup.rsc'
        )

    logger.info(
        f"Magic Command generated for router '{data.name}' (CHR: {data.is_chr})",
        extra={"router_id": str(router_id), "token_prefix": setup_token[:8]},
    )

    return MagicInitResponse(
        router_id=router_id,
        setup_token=setup_token,
        magic_command=magic_command,
        expires_at=expires_at.isoformat(),
        is_chr=data.is_chr,
    )


@router.get(
    "/onboarding/status/{router_id}",
    response_model=RouterStatusResponse,
    summary="Poll router onboarding status (admin only)",
)
async def onboarding_status(
    router_id: UUID,
    user: dict = Depends(require_role("admin")),
) -> RouterStatusResponse:
    """
    Returns the current status of a router being onboarded via the Magic Command.

    This endpoint is polled by the frontend every 3 seconds while the ISP admin
    is on the 'command' step of the wizard. When the MikroTik router runs the
    setup script and calls POST /setup/{token}/confirm, the router's status
    changes from 'pending_setup' to 'online'. The next poll of this endpoint
    returns 'online', triggering the frontend to advance to the 'complete' step.

    PARALLEL: This is the same pattern as PaymentStatusPage polling for M-Pesa
    STK push confirmation. The frontend polls a lightweight GET endpoint every
    few seconds until the backend state changes to a terminal state.
    The polling is done with useQuery + refetchInterval in React Query.
    """
    tenant_id = UUID(user["tenant_id"])

    async with get_db() as conn:
        row = await conn.fetchrow(
            "SELECT id, status FROM routers WHERE id = $1 AND tenant_id = $2",
            router_id,
            tenant_id,
        )

    if not row:
        raise NotFoundException("Router", str(router_id))

    return RouterStatusResponse(
        router_id=row["id"],
        status=row["status"],
    )

@router.get(
    "/onboarding/interfaces/{router_id}",
    summary="Get live interfaces from the connected router (Phase 2 onboarding)",
)
async def get_router_interfaces(
    router_id: UUID,
    user: dict = Depends(require_role("admin")),
):
    tenant_id = UUID(user["tenant_id"])

    async with get_db() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM routers WHERE id = $1 AND tenant_id = $2",
            router_id,
            tenant_id,
        )

    if not row:
        raise NotFoundException("Router", str(router_id))

    # Connect to router
    from app.integrations.mikrotik import get_mikrotik_client
    mikrotik = get_mikrotik_client(dict(row))

    try:
        interfaces = await mikrotik.get_interfaces()
        return {"interfaces": interfaces}
    except Exception as e:
        logger.error(f"Failed to fetch interfaces from router '{row['name']}': {e}")
        return {"interfaces": [], "error": str(e)}

import ipaddress

@router.post(
    "/onboarding/provision/{router_id}",
    summary="Provision the router for Hotspot or PPPoE (Phase 2 onboarding)",
)
async def provision_router(
    router_id: UUID,
    data: RouterProvisionRequest,
    user: dict = Depends(require_role("admin")),
):
    tenant_id = UUID(user["tenant_id"])

    async with get_db() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM routers WHERE id = $1 AND tenant_id = $2",
            router_id,
            tenant_id,
        )

    if not row:
        raise NotFoundException("Router", str(router_id))

    try:
        network = ipaddress.IPv4Network(data.ip_range, strict=False)
        hosts = list(network.hosts())
        gateway = str(hosts[0])
        pool_start = str(hosts[1])
        pool_end = str(hosts[-1])
        network_base = str(network.network_address)
    except ValueError as e:
        return {"error": f"Invalid IP range: {e}"}

    from app.integrations.mikrotik import get_mikrotik_client
    mikrotik = get_mikrotik_client(dict(row))

    try:
        if data.service_type == "hotspot":
            frontend_url = getattr(settings, "FRONTEND_URL", "https://portal.Frixel Connect.dev")
            # Determine RADIUS client address: 192.168.56.1 if testing on a VirtualBox
            # host-only subnet, or 10.8.0.1 as default VPN gateway.
            radius_ip = "10.8.0.1"
            is_chr = "192.168.56." in row["host"]
            if is_chr:
                chr_host = getattr(settings, "CHR_HOST_IP", "192.168.56.1")
                frontend_url = getattr(settings, "CHR_FRONTEND_URL", f"http://{chr_host}")
                radius_ip = chr_host
                chr_port = getattr(settings, "CHR_BACKEND_PORT", 8000)
                backend_base = f"http://{chr_host}:{chr_port}"
            else:
                backend_base = settings.API_BASE_URL
                
            radius_secret = settings.RADIUS_COA_SECRET
            
            import urllib.parse
            encoded_frontend_url = urllib.parse.quote(frontend_url, safe="")
            login_html_url = f"{backend_base}/api/v1/hotspot/login.html?tenant_id={tenant_id}&frontend_url={encoded_frontend_url}"
            
            await mikrotik.create_speed_profiles()
            await mikrotik.setup_hotspot_server(
                interface=data.interface,
                gateway=gateway,
                network_base=network_base,
                pool_start=pool_start,
                pool_end=pool_end,
                frontend_url=frontend_url,
                tenant_id=str(tenant_id),
                radius_ip=radius_ip,
                radius_secret=radius_secret,
                login_html_url=login_html_url,
            )
        elif data.service_type == "pppoe":
            await mikrotik.setup_pppoe_server(
                interface=data.interface,
                local_address=gateway,
                pool_start=pool_start,
                pool_end=pool_end,
            )
            
        async with get_db() as conn:
            await conn.execute(
                "UPDATE routers SET status = 'online' WHERE id = $1", router_id
            )

        return {"status": "success", "message": f"{data.service_type.capitalize()} provisioned on {data.interface}"}
    except Exception as e:
        logger.error(f"Failed to provision router '{row['name']}': {e}")
        return {"error": str(e)}
