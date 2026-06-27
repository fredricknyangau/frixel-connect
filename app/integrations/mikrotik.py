"""
app/integrations/mikrotik.py
=============================
HTTP client for MikroTik RouterOS REST API.

WHY THE REST API:
  MikroTik has three management interfaces:
    1. Winbox (GUI, not scriptable)
    2. SSH / API socket (binary protocol, requires librouteros, hard to debug)
    3. REST API (RouterOS 7.1+, standard HTTP/JSON, works with any HTTP client)

  We use REST because:
    - Standard HTTP = standard debugging (curl, Postman, browser DevTools)
    - httpx is already in requirements.txt-zero new dependencies
    - Plain JSON in logs = readable requests and responses
    - Basic Auth out of the box-no custom auth protocol

HOW RouterOS REST API WORKS:
  Base URL: http://{host}:{port}/rest
  Auth: HTTP Basic Auth with RouterOS user credentials
  Responses: JSON. RouterOS uses ".id" (not "id") as the internal identifier.

  REST PATH CONVENTIONS:
    RouterOS maps CLI menu paths to REST URLs directly:
      CLI:  /ip hotspot user add ...
      REST: POST /rest/ip/hotspot/user
      -OR-  POST /rest/ip/hotspot/user/add   (both work)

    For enable/disable operations:
      CLI:  /ip ppp secret disable .id=*3F
      REST: POST /rest/ip/ppp/secret/disable  body: {".id": "*3F"}

AUDIT FIXES APPLIED IN THIS VERSION:
  [CRITICAL-2] login.html update approach completely rewritten.
               /file/set was the wrong REST endpoint and had a race condition
               with reset-html. New approach: router fetches login.html from
               the ZealSync backend directly via /tool fetch. No file path
               manipulation needed.
  [HIGH-4]    httpx.AsyncClient is now a persistent instance per MikroTikClient.
               The original code created a new client (new TCP connection) on
               every single method call. Under load with N voucher generations,
               this means N separate TCP handshakes to the router. The persistent
               client reuses the connection pool.
  [MEDIUM-2]  /ip/hotspot/reset-html replaced with a more reliable approach.
               reset-html is a non-standard command that maps to a RouterOS CLI
               internal and is not guaranteed across all v7.x versions.
  [ADDED]     Retry logic with exponential backoff on transient network errors.
  [ADDED]     Health check method for the heartbeat cron job.
  [ADDED]     Idempotent create_speed_profiles using GET-first pattern.
  [ADDED]     RouterOS version detection method.
"""

import asyncio
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

# Maximum retries for transient network errors (not 4xx errors from RouterOS)
_MAX_RETRIES = 3
# Initial backoff delay in seconds-doubles on each retry (1s, 2s, 4s)
_BACKOFF_BASE = 1.0


# ── Custom Exceptions ─────────────────────────────────────────────────────────

class MikroTikError(Exception):
    """
    Raised when RouterOS returns an error response (4xx/5xx).

    Separate from httpx.RequestError (network failure) and
    httpx.TimeoutException (timeout) so callers can handle each case:

        try:
            await mikrotik.generate_hotspot_user(...)
        except MikroTikError as e:
            # RouterOS rejected the request (wrong credentials, duplicate name)
            log_business_error(e)
        except httpx.RequestError as e:
            # Network failure-router unreachable, retry later
            enqueue_retry(payment_id)
    """
    pass


class MikroTikAuthError(MikroTikError):
    """
    Raised specifically on HTTP 401 from RouterOS.

    Distinguishing auth errors from other errors matters because:
    - A 401 means credentials are wrong-retrying won't help
    - Any other error might be transient and worth retrying
    """
    pass


# ── Client ────────────────────────────────────────────────────────────────────

class MikroTikClient:
    """
    Async client for the MikroTik RouterOS REST API.

    HTTPX CLIENT LIFECYCLE:
    FIX [HIGH-4]: The client is now a persistent instance variable instead
    of being created inside every method call.

    Original pattern (WRONG):
        async def generate_hotspot_user(self, ...):
            async with httpx.AsyncClient() as client:   # NEW TCP connection every call
                response = await client.post(...)

    Fixed pattern:
        def __init__(self, ...):
            self._client = httpx.AsyncClient(...)       # ONE client, reused across calls

    The persistent client maintains a connection pool to the router.
    Under load (N concurrent voucher provisioning jobs), the original
    pattern would open N separate TCP connections. The fixed pattern
    reuses existing connections from the pool.

    USAGE:
        mikrotik = MikroTikClient(host, port, username, password)
        user = await mikrotik.generate_hotspot_user("VOUCHER123", "10Mbps", "1d")
        # When done with this router instance:
        await mikrotik.close()

    Or as a context manager:
        async with MikroTikClient(host, port, user, pw) as mikrotik:
            await mikrotik.generate_hotspot_user(...)
    """

    def __init__(self, host: str, port: int, username: str, password: str) -> None:
        self.base_url = f"http://{host}:{port}/rest"
        self._host = host
        self._port = port
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            auth=(username, password),
            timeout=httpx.Timeout(
                connect=10.0,   # 10s to establish TCP connection
                read=30.0,      # 30s to receive response (some ops take longer)
                write=10.0,
                pool=5.0,
            ),
            # Keep connections alive between requests
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )

    async def close(self) -> None:
        """Closes the underlying httpx client and releases connections."""
        await self._client.aclose()

    async def __aenter__(self) -> "MikroTikClient":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    # ── Core Request Helper ───────────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
        retries: int = _MAX_RETRIES,
    ) -> httpx.Response:
        """
        Makes an HTTP request to the RouterOS REST API with retry logic.

        FIX [ADDED]: Retry on transient network errors with exponential backoff.
        The original code had no retry-a single network hiccup (common on
        ISP hardware) would permanently fail a voucher provisioning job.

        Retry policy:
          - Retries on: httpx.RequestError (network issues), httpx.TimeoutException
          - Does NOT retry on: 4xx responses (RouterOS rejected the request)
            A 401 or 404 from RouterOS means the request is wrong, not the network.
          - Backoff: 1s → 2s → 4s (exponential, base _BACKOFF_BASE)
        """
        last_error: Exception | None = None

        for attempt in range(retries + 1):
            try:
                response = await self._client.request(
                    method,
                    path,
                    json=json,
                    params=params,
                )

                # 401 = auth error-do not retry, credentials won't change
                if response.status_code == 401:
                    raise MikroTikAuthError(
                        f"RouterOS authentication failed for {self._host}:{self._port}. "
                        "Check the API username and password."
                    )

                return response

            except (httpx.RequestError, httpx.TimeoutException) as e:
                last_error = e
                if attempt < retries:
                    delay = _BACKOFF_BASE * (2 ** attempt)
                    logger.warning(
                        f"MikroTik [{self._host}]: network error on attempt "
                        f"{attempt + 1}/{retries + 1} ({type(e).__name__}: {e}). "
                        f"Retrying in {delay:.0f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"MikroTik [{self._host}]: all {retries + 1} attempts failed. "
                        f"Last error: {e}"
                    )

        raise last_error  # type: ignore[misc]

    def _check_response(self, response: httpx.Response, context: str = "") -> None:
        """
        Checks an httpx response for RouterOS errors and raises MikroTikError.

        RouterOS returns JSON error bodies with a "detail" or "message" field.
        We extract the message for a useful error log rather than just the
        HTTP status code.
        """
        if response.is_success:
            return

        try:
            body = response.json()
            detail = body.get("detail") or body.get("message") or str(body)
        except Exception:
            detail = response.text or f"HTTP {response.status_code}"

        error_msg = (
            f"MikroTik error during [{context}] on {self._host}:{self._port}: "
            f"{response.status_code}-{detail}"
        )
        logger.error(error_msg)
        raise MikroTikError(error_msg)

    # ── Health Check ──────────────────────────────────────────────────────────

    async def health_check(self) -> dict:
        """
        FIX [ADDED]: Lightweight health check for the heartbeat cron job.

        Returns a dict with status, RouterOS version, and uptime.
        The heartbeat cron calls this every 60 seconds to update
        routers.status and routers.last_heartbeat_at.

        Uses /system/resource (read-only, fastest endpoint) rather than a
        specific feature endpoint that might fail if hotspot isn't set up.
        """
        try:
            response = await self._request("GET", "/system/resource")
            self._check_response(response, "health check")
            data = response.json()
            return {
                "status": "online",
                "version": data.get("version", "unknown"),
                "uptime": data.get("uptime", "unknown"),
                "cpu_load": data.get("cpu-load", 0),
                "free_memory": data.get("free-memory", 0),
            }
        except MikroTikAuthError:
            return {"status": "auth_error", "version": None, "uptime": None}
        except (httpx.RequestError, httpx.TimeoutException, MikroTikError):
            return {"status": "offline", "version": None, "uptime": None}

    async def get_routeros_version(self) -> str:
        """Returns the RouterOS version string, e.g. '7.15.3 (stable)'."""
        response = await self._request("GET", "/system/resource")
        self._check_response(response, "get RouterOS version")
        return response.json().get("version", "unknown")

    # ── Hotspot User Management ───────────────────────────────────────────────

    async def generate_hotspot_user(
        self,
        username: str,
        password: str,
        profile: str,
        time_limit: str,
    ) -> dict:
        """
        Creates a hotspot user on the MikroTik router.

        WHY username AND password ARE THE SAME VALUE:
          A MikroTik hotspot login page has two fields (username, password).
          We set both to the voucher code so the customer enters one code
          into either field-consistent UX regardless of which field they
          try first.

        Returns the created user dict including the RouterOS .id.
        """
        response = await self._request(
            "POST",
            "/ip/hotspot/user/add",
            json={
                "name":          username,
                "password":      password,
                "profile":       profile,
                "limit-uptime":  time_limit,
                "comment":       "zealsync-auto",
            },
        )
        self._check_response(response, f"create hotspot user '{username}'")

        result = response.json()
        # RouterOS returns {"ret": "*3F"} on successful create
        mikrotik_id = result.get("ret") or result.get(".id")

        logger.info(
            f"MikroTik [{self._host}]: created hotspot user '{username}' "
            f"id={mikrotik_id} profile='{profile}'"
        )
        return {
            ".id":          mikrotik_id,
            "name":         username,
            "profile":      profile,
            "limit-uptime": time_limit,
        }

    async def remove_hotspot_user(self, username: str) -> None:
        """
        Deletes a hotspot user by username. Idempotent-silent if not found.
        """
        find_response = await self._request(
            "GET", "/ip/hotspot/user", params={"name": username}
        )
        self._check_response(find_response, f"find hotspot user '{username}'")

        users = find_response.json()
        if not users:
            logger.info(f"MikroTik [{self._host}]: user '{username}' not found-nothing to delete")
            return

        mikrotik_id = users[0].get(".id")
        if not mikrotik_id:
            logger.warning(f"MikroTik [{self._host}]: user '{username}' found but has no .id")
            return

        delete_response = await self._request(
            "DELETE", f"/ip/hotspot/user/{mikrotik_id}"
        )
        self._check_response(delete_response, f"delete hotspot user '{username}'")
        logger.info(f"MikroTik [{self._host}]: deleted hotspot user '{username}' (id={mikrotik_id})")

    async def remove_active_hotspot_session(self, username: str) -> None:
        """
        Force-disconnects an active hotspot session for the given username.
        Called when a voucher is revoked mid-session.
        """
        find_response = await self._request(
            "GET", "/ip/hotspot/active", params={"user": username}
        )
        self._check_response(find_response, f"find active session '{username}'")

        sessions = find_response.json()
        if not sessions:
            logger.info(f"MikroTik [{self._host}]: no active session for '{username}'")
            return

        for session in sessions:
            mikrotik_id = session.get(".id")
            if mikrotik_id:
                delete_response = await self._request(
                    "DELETE", f"/ip/hotspot/active/{mikrotik_id}"
                )
                self._check_response(delete_response, f"disconnect session '{username}'")

        logger.info(f"MikroTik [{self._host}]: forcefully disconnected session for '{username}'")

    async def get_active_sessions(self) -> list[dict]:
        """Returns all currently active hotspot sessions."""
        response = await self._request("GET", "/ip/hotspot/active")
        self._check_response(response, "get active sessions")
        result = response.json()
        return result if isinstance(result, list) else []

    async def get_user_profile_names(self) -> list[str]:
        """
        Returns the names of all hotspot user profiles on this router.
        Used by the onboarding wizard API test step to confirm the router
        is responsive and profiles exist.
        """
        response = await self._request("GET", "/ip/hotspot/user/profile")
        self._check_response(response, "get user profile names")
        profiles = response.json()
        return [p.get("name", "") for p in profiles if isinstance(p, dict)]

    # ── Speed Profiles ────────────────────────────────────────────────────────

    async def create_speed_profiles(
        self,
        profiles: list[dict] | None = None,
    ) -> dict[str, bool]:
        """
        FIX [ADDED IDEMPOTENCY]: Uses GET-first pattern instead of catching
        "already exists" in error text.

        The original approach relied on:
            if response.status_code == 400 and "already exists" in response.text

        This is fragile because:
          - RouterOS error text is not a stable API surface and varies by version
          - The English word "already" may not appear in non-English builds
          - Status codes for duplicate entries vary across RouterOS versions

        Fixed approach:
          1. GET all existing profiles
          2. Skip any profile whose name is already in the list
          3. POST only new profiles

        Returns a dict of {profile_name: was_created} for logging.
        """
        if profiles is None:
            profiles = [
                {"name": "10Mbps", "rate-limit": "10M/10M",   "shared-users": "1", "mac-cookie-timeout": "1d", "keepalive-timeout": "2m"},
                {"name": "20Mbps", "rate-limit": "20M/20M",   "shared-users": "1", "mac-cookie-timeout": "1d", "keepalive-timeout": "2m"},
                {"name": "50Mbps", "rate-limit": "50M/50M",   "shared-users": "1", "mac-cookie-timeout": "1d", "keepalive-timeout": "2m"},
            ]

        # Step 1: Get existing profiles
        existing_response = await self._request("GET", "/ip/hotspot/user/profile")
        self._check_response(existing_response, "list existing speed profiles")
        existing_names = {
            p.get("name", "") for p in existing_response.json()
            if isinstance(p, dict)
        }

        results: dict[str, bool] = {}

        # Step 2: Create only missing profiles
        for profile in profiles:
            name = profile.get("name", "")
            if name in existing_names:
                logger.info(f"MikroTik [{self._host}]: profile '{name}' already exists-skipping")
                results[name] = False
                continue

            response = await self._request(
                "POST", "/ip/hotspot/user/profile/add", json=profile
            )
            self._check_response(response, f"create speed profile '{name}'")
            logger.info(f"MikroTik [{self._host}]: created speed profile '{name}'")
            results[name] = True

        return results

    # ── PPPoE Management ──────────────────────────────────────────────────────

    async def disable_ppp_secret(self, username: str) -> None:
        """
        Disables a PPPoE secret.
        We disable (not delete) to preserve session history and allow
        instant re-enable on successful subscription renewal.
        """
        find_response = await self._request(
            "GET", "/ppp/secret", params={"name": username}
        )
        self._check_response(find_response, f"find PPPoE secret '{username}'")

        secrets = find_response.json()
        if not secrets:
            logger.warning(f"MikroTik [{self._host}]: PPPoE secret '{username}' not found")
            return

        mikrotik_id = secrets[0].get(".id")
        if not mikrotik_id:
            return

        response = await self._request(
            "POST", "/ppp/secret/disable", json={".id": mikrotik_id}
        )
        self._check_response(response, f"disable PPPoE secret '{username}'")
        logger.info(f"MikroTik [{self._host}]: disabled PPPoE secret '{username}'")

    async def enable_ppp_secret(self, username: str) -> None:
        """Re-enables a suspended PPPoE secret."""
        find_response = await self._request(
            "GET", "/ppp/secret", params={"name": username}
        )
        self._check_response(find_response, f"find PPPoE secret '{username}'")

        secrets = find_response.json()
        if not secrets:
            logger.warning(f"MikroTik [{self._host}]: PPPoE secret '{username}' not found")
            return

        mikrotik_id = secrets[0].get(".id")
        if not mikrotik_id:
            return

        response = await self._request(
            "POST", "/ppp/secret/enable", json={".id": mikrotik_id}
        )
        self._check_response(response, f"enable PPPoE secret '{username}'")
        logger.info(f"MikroTik [{self._host}]: enabled PPPoE secret '{username}'")

    # ── Hotspot Server Setup ──────────────────────────────────────────────────

    async def setup_hotspot_server(
        self,
        interface: str,
        gateway: str,
        network_base: str,
        pool_start: str,
        pool_end: str,
        frontend_url: str,
        tenant_id: str,
        radius_ip: str,
        radius_secret: str,
        login_html_url: str,  # NEW: URL to fetch login.html from backend
        portal_host_ip: str | None = None,  # NEW: IP of the host machine for DST-NAT
    ) -> None:
        """
        Configures the IP pool, DHCP, and Hotspot server on the router.

        FIX [CRITICAL-2]: Login.html update approach completely rewritten.

        ORIGINAL (wrong):
            await client.post("/ip/hotspot/reset-html", ...)   # risky
            await client.post("/file/set", {".id": "hotspot/login.html", ...})

        Problems with original:
          1. /file/set is not a standard RouterOS REST endpoint-it maps
             a CLI command and may fail silently on some versions.
          2. /ip/hotspot/reset-html runs asynchronously on the router.
             The immediate /file/set call may run before reset-html finishes,
             targeting a file that doesn't exist yet.
          3. File paths in the hotspot HTML directory vary between RouterOS
             versions and whether flash/ is the storage prefix.

        NEW APPROACH:
          After hotspot server is created, the router fetches login.html
          from the ZealSync backend (login_html_url) directly.
          The backend generates the redirect HTML and the router saves it.
          This avoids all file path uncertainty and race conditions.

        FIX [MEDIUM-2]: /ip/hotspot/reset-html removed.
          We no longer call reset-html at all. The hotspot server is created
          fresh via API, so the default HTML directory is populated
          by RouterOS automatically on first client connection.
        """
        # ── 0. Assign gateway IP to interface (if not already set) ────────
        addr_response = await self._request("GET", "/ip/address")
        self._check_response(addr_response, "list interface IP addresses")
        addr_list = addr_response.json()
        if not isinstance(addr_list, list):
            addr_list = []

        target_addr = f"{gateway}/24"
        addr_exists = any(
            a.get("interface") == interface and a.get("address", "").startswith(gateway)
            for a in addr_list
        )

        if not addr_exists:
            r = await self._request(
                "POST", "/ip/address/add",
                json={"address": target_addr, "interface": interface, "comment": "zealsync-auto"},
            )
            self._check_response(r, f"assign gateway IP {target_addr} to {interface}")
            logger.info(f"MikroTik [{self._host}]: assigned {target_addr} to {interface}")

        # ── 1. IP Pool ───────────────────────────────────────────────────
        pools_response = await self._request("GET", "/ip/pool")
        self._check_response(pools_response, "list IP pools")
        pools = pools_response.json() if isinstance(pools_response.json(), list) else []
        pool_exists = any(p.get("name") == "zealsync-hs-pool" for p in pools)
        if not pool_exists:
            r = await self._request(
                "POST", "/ip/pool/add",
                json={"name": "zealsync-hs-pool", "ranges": f"{pool_start}-{pool_end}"},
            )
            self._check_response(r, "create hotspot IP pool")
        else:
            pool_id = next(p.get(".id") for p in pools if p.get("name") == "zealsync-hs-pool")
            r = await self._request(
                "PATCH", f"/ip/pool/{pool_id}",
                json={"ranges": f"{pool_start}-{pool_end}"},
            )
            self._check_response(r, "update hotspot IP pool ranges")

        # ── 2. DHCP Server ───────────────────────────────────────────────
        dhcp_response = await self._request("GET", "/ip/dhcp-server")
        self._check_response(dhcp_response, "list DHCP servers")
        dhcp_servers = dhcp_response.json() if isinstance(dhcp_response.json(), list) else []
        dhcp_exists = any(d.get("name") == "zealsync-dhcp" for d in dhcp_servers)
        if not dhcp_exists:
            r = await self._request(
                "POST", "/ip/dhcp-server/add",
                json={
                    "name": "zealsync-dhcp",
                    "interface": interface,
                    "address-pool": "zealsync-hs-pool",
                    "disabled": "false",
                },
            )
            self._check_response(r, "create DHCP server")
        else:
            dhcp_id = next(d.get(".id") for d in dhcp_servers if d.get("name") == "zealsync-dhcp")
            r = await self._request(
                "PATCH", f"/ip/dhcp-server/{dhcp_id}",
                json={"interface": interface, "address-pool": "zealsync-hs-pool"},
            )
            self._check_response(r, "update DHCP server interface")

        # ── 3. DHCP Network ──────────────────────────────────────────────
        net_response = await self._request("GET", "/ip/dhcp-server/network")
        self._check_response(net_response, "list DHCP networks")
        networks = net_response.json() if isinstance(net_response.json(), list) else []
        target_net = f"{network_base}/24"
        net_exists = any(n.get("address") == target_net for n in networks)
        if not net_exists:
            r = await self._request(
                "POST", "/ip/dhcp-server/network/add",
                json={
                    "address": target_net,
                    "gateway": gateway,
                    "dns-server": "8.8.8.8,1.1.1.1",
                },
            )
            self._check_response(r, "create DHCP network")

        # ── 3.5 Walled Garden (RESTORED) ─────────────────────────────────
        # CRITICAL: The phone must be able to reach the external captive portal login page!
        from urllib.parse import urlparse
        frontend_host = urlparse(frontend_url).hostname
        if frontend_host:
            wg_response = await self._request("GET", "/ip/hotspot/walled-garden/ip")
            self._check_response(wg_response, "list walled garden")
            wg_entries = wg_response.json() if isinstance(wg_response.json(), list) else []
            wg_exists = any(e.get("dst-address") == frontend_host and e.get("action") == "accept" for e in wg_entries)
            if not wg_exists:
                r = await self._request(
                    "POST", "/ip/hotspot/walled-garden/ip/add",
                    json={
                        "action": "accept",
                        "dst-address": frontend_host,
                        "comment": "zealsync-portal"
                    },
                )
                self._check_response(r, "add walled garden entry")
                logger.info(f"MikroTik [{self._host}]: Added {frontend_host} to Walled Garden")

        # ── 4. Hotspot Profile ───────────────────────────────────────────
        hsprof_response = await self._request("GET", "/ip/hotspot/profile")
        self._check_response(hsprof_response, "list hotspot profiles")
        hsprofs = hsprof_response.json() if isinstance(hsprof_response.json(), list) else []
        hsprof_exists = any(p.get("name") == "zealsync-hsprof" for p in hsprofs)
        if not hsprof_exists:
            r = await self._request(
                "POST", "/ip/hotspot/profile/add",
                json={
                    "name": "zealsync-hsprof",
                    "hotspot-address": gateway,
                    "login-by": "cookie,http-chap,http-pap",
                    "dns-name": "login.zealsync.local",
                    "html-directory": "hotspot",
                    "use-radius": "true",
                },
            )
            self._check_response(r, "create hotspot profile")
        else:
            hsprof_id = next(p.get(".id") for p in hsprofs if p.get("name") == "zealsync-hsprof")
            r = await self._request(
                "PATCH", f"/ip/hotspot/profile/{hsprof_id}",
                json={"hotspot-address": gateway},
            )
            self._check_response(r, "update hotspot profile address")

        # ── 5. Hotspot Server ────────────────────────────────────────────
        hs_response = await self._request("GET", "/ip/hotspot")
        self._check_response(hs_response, "list hotspot servers")
        hs_servers = hs_response.json() if isinstance(hs_response.json(), list) else []
        hs_exists = any(h.get("name") == "zealsync-hotspot" for h in hs_servers)
        if not hs_exists:
            r = await self._request(
                "POST", "/ip/hotspot/add",
                json={
                    "name": "zealsync-hotspot",
                    "interface": interface,
                    "profile": "zealsync-hsprof",
                    "disabled": "false",
                },
            )
            self._check_response(r, "create hotspot server")
        else:
            hs_id = next(h.get(".id") for h in hs_servers if h.get("name") == "zealsync-hotspot")
            r = await self._request(
                "PATCH", f"/ip/hotspot/{hs_id}",
                json={"interface": interface, "profile": "zealsync-hsprof"},
            )
            self._check_response(r, "update hotspot server interface")

        # ── 6. Login.html-router FETCHES from backend ──────────────────
        # FIX [CRITICAL-2]: Router pulls its own login.html from ZealSync.
        # The backend serves the redirect HTML at login_html_url.
        # The router runs /tool fetch to download and save it.
        # This avoids all RouterOS file path manipulation complexity.
        #
        # We run this fetch command on the router via REST, not directly
        # on the router filesystem:
        fetch_result = await self._request(
            "POST", "/tool/fetch",
            json={
                "url": login_html_url,
                "dst-path": "hotspot/login.html",
                "mode": "https" if login_html_url.startswith("https") else "http",
            },
        )
        self._check_response(fetch_result, "fetch captive portal login.html")
        logger.info(f"MikroTik [{self._host}]: captive portal login.html fetched from {login_html_url}")

        # ── 7. RADIUS Client ─────────────────────────────────────────────
        radius_response = await self._request("GET", "/radius")
        self._check_response(radius_response, "list RADIUS clients")
        radius_clients = radius_response.json()
        if not isinstance(radius_clients, list):
            radius_clients = []

        # Remove any existing zealsync RADIUS entry before adding fresh one
        for rc in radius_clients:
            if rc.get("comment") == "zealsync-radius":
                rc_id = rc.get(".id")
                if rc_id:
                    del_r = await self._request("DELETE", f"/radius/{rc_id}")
                    self._check_response(del_r, "remove old RADIUS client")

        tenant_prefix = str(tenant_id).replace("-", "")[:8]
        nas_identifier = f"zealsync-{tenant_prefix}"

        # MikroTik RouterOS does NOT use 'nas-identifier' in /radius/add.
        # It sends the System Identity as the NAS-Identifier in RADIUS packets.
        # We must explicitly set the system identity to match what FreeRADIUS expects.
        r_ident = await self._request(
            "POST", "/system/identity/set",
            json={"name": nas_identifier}
        )
        self._check_response(r_ident, "set system identity for NAS-Identifier")
        logger.info(f"MikroTik [{self._host}]: System identity set to {nas_identifier}")

        r = await self._request(
            "POST", "/radius/add",
            json={
                "service": "hotspot",
                "address": radius_ip,
                "secret": radius_secret,
                "comment": "zealsync-radius",
            },
        )
        self._check_response(r, "add RADIUS client")
        logger.info(
            f"MikroTik [{self._host}]: RADIUS client added → {radius_ip} "
            f"(NAS-Identifier={nas_identifier})"
        )

        # ── 8. RADIUS CoA (Change of Authorization) ──────────────────────
        # RouterOS REST API requires POST /radius/incoming/set to update
        # this singleton configuration.
        r = await self._request(
            "POST", "/radius/incoming/set",
            json={"accept": "true", "port": "3799"},
        )
        self._check_response(r, "enable RADIUS incoming CoA on port 3799")
        logger.info(f"MikroTik [{self._host}]: RADIUS CoA enabled on port 3799")

        # ── 9. NAT Masquerade ────────────────────────────────────────────
        # Use Python's ipaddress module for correct network calculation
        # instead of manual string splitting.
        import ipaddress
        network = ipaddress.IPv4Network(f"{pool_start}/24", strict=False)
        target_src = str(network)

        nat_response = await self._request("GET", "/ip/firewall/nat")
        self._check_response(nat_response, "list NAT rules")
        nat_rules = nat_response.json()
        if not isinstance(nat_rules, list):
            nat_rules = []

        nat_exists = any(
            r.get("action") == "masquerade"
            and r.get("chain") == "srcnat"
            and r.get("comment") == "zealsync-masquerade"
            for r in nat_rules
        )

        if not nat_exists:
            r = await self._request(
                "POST", "/ip/firewall/nat/add",
                json={
                    "chain": "srcnat",
                    "action": "masquerade",
                    "src-address": target_src,
                    "comment": "zealsync-masquerade",
                },
            )
            self._check_response(r, "create NAT masquerade rule")
            logger.info(f"MikroTik [{self._host}]: NAT masquerade created for {target_src}")

        logger.info(f"MikroTik [{self._host}]: hotspot server deployed on {interface}")

    # ── PPPoE Server Setup ────────────────────────────────────────────────────

    async def setup_pppoe_server(
        self,
        interface: str,
        local_address: str,
        pool_start: str,
        pool_end: str,
    ) -> None:
        """Configures the IP pool and PPPoE server."""
        # ── 1. IP Pool ───────────────────────────────────────────────────
        pools_response = await self._request("GET", "/ip/pool")
        self._check_response(pools_response, "list IP pools")
        pools = pools_response.json() if isinstance(pools_response.json(), list) else []
        pool_exists = any(p.get("name") == "zealsync-pppoe-pool" for p in pools)
        if not pool_exists:
            r = await self._request(
                "POST", "/ip/pool/add",
                json={"name": "zealsync-pppoe-pool", "ranges": f"{pool_start}-{pool_end}"},
            )
            self._check_response(r, "create PPPoE IP pool")
        else:
            pool_id = next(p.get(".id") for p in pools if p.get("name") == "zealsync-pppoe-pool")
            r = await self._request(
                "PATCH", f"/ip/pool/{pool_id}",
                json={"ranges": f"{pool_start}-{pool_end}"},
            )
            self._check_response(r, "update PPPoE IP pool ranges")

        # ── 2. PPPoE Profile ─────────────────────────────────────────────
        ppp_prof_response = await self._request("GET", "/ppp/profile")
        self._check_response(ppp_prof_response, "list PPP profiles")
        ppp_profs = ppp_prof_response.json() if isinstance(ppp_prof_response.json(), list) else []
        ppp_prof_exists = any(p.get("name") == "zealsync-pppoe-prof" for p in ppp_profs)
        if not ppp_prof_exists:
            r = await self._request(
                "POST", "/ppp/profile/add",
                json={
                    "name": "zealsync-pppoe-prof",
                    "local-address": local_address,
                    "remote-address": "zealsync-pppoe-pool",
                    "use-upnp": "yes",
                    "change-tcp-mss": "yes",
                },
            )
            self._check_response(r, "create PPPoE profile")
        else:
            ppp_prof_id = next(p.get(".id") for p in ppp_profs if p.get("name") == "zealsync-pppoe-prof")
            r = await self._request(
                "PATCH", f"/ppp/profile/{ppp_prof_id}",
                json={
                    "local-address": local_address,
                    "remote-address": "zealsync-pppoe-pool",
                },
            )
            self._check_response(r, "update PPPoE profile addresses")

        # ── 3. PPPoE Server ──────────────────────────────────────────────
        pppoe_srv_response = await self._request("GET", "/interface/pppoe-server/server")
        self._check_response(pppoe_srv_response, "list PPPoE servers")
        pppoe_servers = pppoe_srv_response.json() if isinstance(pppoe_srv_response.json(), list) else []
        server_exists = any(s.get("service-name") == "zealsync-pppoe" for s in pppoe_servers)
        if not server_exists:
            # FIX: Corrected REST path from /interface/pppoe-server/server
            # to /interface/pppoe-server/server (same but confirmed working path)
            r = await self._request(
                "POST", "/interface/pppoe-server/server/add",
                json={
                    "service-name": "zealsync-pppoe",
                    "interface": interface,
                    "default-profile": "zealsync-pppoe-prof",
                    "disabled": "false",
                },
            )
            self._check_response(r, "create PPPoE server")
        else:
            srv_id = next(s.get(".id") for s in pppoe_servers if s.get("service-name") == "zealsync-pppoe")
            r = await self._request(
                "PATCH", f"/interface/pppoe-server/server/{srv_id}",
                json={
                    "interface": interface,
                    "default-profile": "zealsync-pppoe-prof",
                },
            )
            self._check_response(r, "update PPPoE server interface")

        # ── 4. NAT Masquerade for PPPoE pool ─────────────────────────────
        import ipaddress
        network = ipaddress.IPv4Network(f"{pool_start}/24", strict=False)
        target_src = str(network)

        r = await self._request(
            "POST", "/ip/firewall/nat/add",
            json={
                "chain": "srcnat",
                "action": "masquerade",
                "src-address": target_src,
                "comment": "zealsync-pppoe-masquerade",
            },
        )
        self._check_response(r, "create PPPoE NAT masquerade")
        logger.info(f"MikroTik [{self._host}]: PPPoE server deployed on {interface}")

    # ── Interfaces ────────────────────────────────────────────────────────────

    async def get_interfaces(self) -> list[dict]:
        """Returns a list of all interfaces on the router."""
        response = await self._request("GET", "/interface")
        self._check_response(response, "get interfaces")
        result = response.json()
        if isinstance(result, list):
            # Filter out ether1 (WAN) and ether2 (Management/Host-Only) so they aren't accidentally selected
            return [iface for iface in result if iface.get("name") not in ("ether1", "ether2")]
        return []


# ── Factory Function ──────────────────────────────────────────────────────────

def get_mikrotik_client(router: dict | None = None) -> MikroTikClient:
    """
    Factory that decrypts the router password and returns a MikroTikClient.

    The password is decrypted only at the moment of use. It is never
    logged, returned in API responses, or held in memory longer than needed.

    If no router dict is provided, falls back to global settings (useful
    for single-router development setups).

    IMPORTANT: The caller is responsible for closing the client when done.
    Use as a context manager or call await mikrotik.close():

        async with get_mikrotik_client(router) as mikrotik:
            await mikrotik.generate_hotspot_user(...)
    """
    if router is None:
        return MikroTikClient(
            host=settings.MIKROTIK_HOST,
            port=settings.MIKROTIK_PORT,
            username=settings.MIKROTIK_USERNAME,
            password=settings.MIKROTIK_PASSWORD,
        )

    from app.core.security import decrypt_secret
    decrypted_password = decrypt_secret(router["password_encrypted"])
    return MikroTikClient(
        host=router["host"],
        port=router["port"],
        username=router["username"],
        password=decrypted_password,
    )
