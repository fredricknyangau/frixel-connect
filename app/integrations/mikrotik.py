"""
app/integrations/mikrotik.py
=============================
HTTP client for MikroTik RouterOS REST API.

WHY THE REST API INSTEAD OF SSH OR MIKROTIK API LIBRARY?
  MikroTik has three management interfaces:
    1. Winbox (GUI, not scriptable)
    2. SSH / API socket (binary protocol, requires a special library like
       librouteros, hard to debug, library maintenance uncertain)
    3. REST API (RouterOS v7.1+, standard HTTP/JSON, works with any HTTP client)

  We use REST because:
    - Standard HTTP means standard debugging: curl, Postman, browser DevTools.
    - httpx is already in requirements.txt — zero new dependencies.
    - The request/response format is plain JSON — readable in logs.
    - REST API supports Basic Auth out of the box — no custom auth protocol.

  Your MikroTik CHR is running RouterOS v7+, so REST is available.
  Older v6 routers would need the API socket approach.

HOW THE RouterOS REST API WORKS:
  Base URL: http://{host}:{port}/rest
  Auth: HTTP Basic Auth with RouterOS credentials
  All endpoints return JSON. The key quirk: RouterOS adds a ".id" field to
  every created object. This ".id" (not "id") is the internal identifier
  used for subsequent GET/DELETE operations on that object.

  Example — create a hotspot user:
    POST /rest/ip/hotspot/user
    Body: {"name": "ABC123", "password": "ABC123", "profile": "10Mbps"}
    Response: {".id": "*3F", "name": "ABC123", ...}

  Example — delete it:
    DELETE /rest/ip/hotspot/user/*3F   ← uses the .id from the create response

HTTPX VS REQUESTS:
  requests is synchronous — calling requests.post() blocks the Python thread
  until the HTTP response arrives. In an async FastAPI app, one blocked thread
  means one fewer concurrent request handler. Under load, this compounds.
  httpx is async — httpx.AsyncClient with await doesn't block the event loop.
  Other requests are handled while waiting for MikroTik to respond.
"""

import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class MikroTikError(Exception):
    """
    Raised when RouterOS returns an error response.

    We use a specific exception class instead of a generic Exception so
    callers can catch MikroTikError specifically and handle it differently
    from network errors (httpx.RequestError) or timeouts (httpx.TimeoutException).
    """
    pass


class MikroTikClient:
    """
    Async client for the MikroTik RouterOS REST API.

    Usage (in a route or background task):
        from app.integrations.mikrotik import MikroTikClient
        mikrotik = MikroTikClient(host, port, username, password)
        user = await mikrotik.generate_hotspot_user("VOUCHER123", "10Mbps", "1d")
    """

    def __init__(self, host: str, port: int, username: str, password: str) -> None:
        """
        Initializes the client with dynamic connection parameters.
        No longer reads global settings directly to support multi-router/multi-tenant sites.
        """
        self.base_url = f"http://{host}:{port}/rest"
        # HTTP Basic Auth: RouterOS validates username+password on every request.
        self._auth = (username, password)
        # Timeout: 10 seconds for connect + read combined.
        self._timeout = httpx.Timeout(10.0)

    def _make_client(self) -> httpx.AsyncClient:
        """Creates a new httpx async client with auth and timeout pre-configured."""
        return httpx.AsyncClient(
            base_url=self.base_url,
            auth=self._auth,
            timeout=self._timeout,
        )

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
        In a hotspot login portal, the customer enters a single "voucher code".
        MikroTik's hotspot login page has TWO fields (username and password),
        but we set them to the same value so the customer only needs to enter one code.
        """
        async with self._make_client() as client:
            response = await client.post(
                "/ip/hotspot/user/add",
                json={
                    "name":     username,
                    "password": password,
                    "profile":  profile,
                    "limit-uptime": time_limit,
                    "comment":      "zealsync-auto",
                },
            )

        self._check_response(response, context=f"create hotspot user '{username}'")

        create_result = response.json()
        mikrotik_id = create_result.get("ret")

        logger.info(f"MikroTik: created hotspot user '{username}' id={mikrotik_id} profile='{profile}'")

        return {
            ".id":          mikrotik_id,
            "name":         username,
            "profile":      profile,
            "limit-uptime": time_limit,
            "comment":      "zealsync-auto",
        }

    async def remove_hotspot_user(self, username: str) -> None:
        """
        Deletes a hotspot user from the router by username.
        IDEMPOTENT: If the user doesn't exist, this method returns silently.
        """
        async with self._make_client() as client:
            # Step 1: Find the user's internal .id by querying by name.
            find_response = await client.get(
                "/ip/hotspot/user",
                params={"name": username},
            )
            self._check_response(find_response, context=f"find hotspot user '{username}'")

            users = find_response.json()

            if not users:
                logger.info(f"MikroTik: user '{username}' not found — nothing to delete")
                return

            # RouterOS returns a list even for a single match. Take the first.
            mikrotik_id = users[0].get(".id")
            if not mikrotik_id:
                logger.warning(f"MikroTik: user '{username}' found but has no .id — skipping delete")
                return

            # Step 2: Delete by the internal .id.
            delete_response = await client.delete(f"/ip/hotspot/user/{mikrotik_id}")
            self._check_response(delete_response, context=f"delete hotspot user '{username}'")

        logger.info(f"MikroTik: deleted hotspot user '{username}' (id={mikrotik_id})")

    async def get_active_sessions(self) -> list[dict]:
        """
        Returns all currently active hotspot sessions.
        """
        async with self._make_client() as client:
            response = await client.get("/ip/hotspot/active")

        self._check_response(response, context="get active sessions")
        sessions = response.json()
        return sessions if isinstance(sessions, list) else []

    async def get_user_profile_names(self) -> list[str]:
        """
        Returns the names of all hotspot user profiles configured on the router.
        """
        async with self._make_client() as client:
            response = await client.get("/ip/hotspot/user/profile")

        self._check_response(response, context="get user profiles")
        profiles = response.json()
        return [p.get("name", "") for p in profiles if isinstance(p, dict)]

    def _check_response(self, response: httpx.Response, context: str = "") -> None:
        """
        Checks an httpx response for RouterOS errors and raises MikroTikError.
        """
        if response.is_success:
            return

        try:
            body = response.json()
            detail = (
                body.get("detail")
                or body.get("message")
                or str(body)
            )
        except Exception:
            detail = response.text or f"HTTP {response.status_code}"

        error_msg = f"MikroTik error during [{context}]: {response.status_code} — {detail}"
        logger.error(error_msg)
        raise MikroTikError(error_msg)


# ── Factory function ─────────────────────────────────────────────────────────

def get_mikrotik_client(router: Optional[dict] = None) -> MikroTikClient:
    """
    Factory function that decrypts the router password and returns
    a configured MikroTikClient instance.

    Decrypts the password only at the moment of use, never logging or returning it.
    If no router is provided, falls back to the global settings.
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


# ── Module-level singleton fallback ──────────────────────────────────────────
# Redefined using the factory to maintain backward compatibility.
mikrotik_client = get_mikrotik_client()
