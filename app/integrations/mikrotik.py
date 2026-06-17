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

    Example in the voucher background task:
        try:
            await mikrotik.generate_hotspot_user(...)
        except MikroTikError as e:
            # RouterOS rejected the user — log and mark voucher as pending_provision
            logger.error(f"RouterOS error: {e}")
        except httpx.RequestError as e:
            # Network failure — router unreachable — same handling
            logger.error(f"MikroTik unreachable: {e}")
    """
    pass


class MikroTikClient:
    """
    Async client for the MikroTik RouterOS REST API.

    Usage (in a route or background task):
        from app.integrations.mikrotik import MikroTikClient
        mikrotik = MikroTikClient()
        user = await mikrotik.generate_hotspot_user("VOUCHER123", "10Mbps", "1d")

    Thread safety: this client is stateless (no shared mutable state between
    calls) so it's safe to instantiate once and reuse across requests, or
    instantiate per-call. We instantiate per-call in background tasks to keep
    things simple. If performance becomes an issue, move to a module-level
    singleton with connection pooling (httpx.AsyncClient supports this).
    """

    def __init__(self) -> None:
        self.base_url = f"http://{settings.MIKROTIK_HOST}:{settings.MIKROTIK_PORT}/rest"
        # HTTP Basic Auth: RouterOS validates username+password on every request.
        # The tuple (username, password) is what httpx expects for Basic Auth.
        self._auth = (settings.MIKROTIK_USERNAME, settings.MIKROTIK_PASSWORD)
        # Timeout: 10 seconds for connect + read combined.
        # MikroTik CHR on VirtualBox can be slow to respond — 10s is generous.
        # In production on dedicated hardware, 5s is appropriate.
        self._timeout = httpx.Timeout(10.0)

    def _make_client(self) -> httpx.AsyncClient:
        """Creates a new httpx async client with auth and timeout pre-configured."""
        return httpx.AsyncClient(
            base_url=self.base_url,
            auth=self._auth,
            timeout=self._timeout,
            # verify=False would disable TLS verification. We're using HTTP
            # (not HTTPS) for the CHR in this build, so verify is irrelevant.
            # In production with HTTPS on the router, set verify to the
            # router's CA cert path.
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
        In a hotspot login portal, the customer enters a single "voucher code"
        into a form. MikroTik's hotspot login page has TWO fields (username
        and password), but we set them to the same value (the voucher code) so
        the customer only needs to remember ONE thing.

        The voucher code acts as both the identifier (username, which appears
        in MikroTik logs) and the credential (password, which the login page
        validates). This is the standard voucher/prepaid WiFi UX in Kenya.

        An alternative is username=voucher, password="wifi" (fixed password).
        We reject this because it allows username enumeration: if I know your
        voucher code, I know your username, and "wifi" is the password. With
        username=password=voucher, knowing the code is the only way in.

        Args:
            username:   The voucher code (e.g. "ABCD2345EF")
            password:   Same as username (the voucher code)
            profile:    MikroTik hotspot user profile name, which controls
                        speed limits. Must exist on the router. Examples:
                        "10Mbps", "20Mbps", "50Mbps".
            time_limit: Session time limit in RouterOS format.
                        Maps to the RouterOS "limit-uptime" property.
                        "1d" = 1 day, "7d" = 7 days, "30d" = 30 days.
                        Maps from package.duration_days in the service layer:
                          1  day  → "1d"
                          7  days → "7d"
                          30 days → "30d"

        Returns:
            A dict with the created user's details including the RouterOS
            internal ".id" (e.g. "*2"). The ".id" is needed to delete this user.

        Raises:
            MikroTikError: If RouterOS returns an error (e.g. user already
                exists, profile doesn't exist, permission denied).
            httpx.RequestError: If the router is unreachable (network error).
            httpx.TimeoutException: If the router doesn't respond in time.
        """
        async with self._make_client() as client:
            # IMPORTANT: RouterOS REST API uses /add as a sub-path for creating
            # resources. POST to the collection (/ip/hotspot/user) returns
            # '400 no such command'. POST to /ip/hotspot/user/add creates the
            # user and returns {"ret": "*2"} where *2 is the internal .id.
            # This was confirmed by live testing against RouterOS 7.23.1.
            response = await client.post(
                "/ip/hotspot/user/add",
                json={
                    "name":     username,
                    "password": password,
                    "profile":  profile,
                    # RouterOS hotspot user property for time limits is "limit-uptime".
                    # "limit-uptime" sets the TOTAL connected time the voucher allows.
                    # Once reached, MikroTik disconnects and rejects further logins.
                    # Format: "1d" = 1 day, "7d" = 7 days, "00:00:00" = unlimited.
                    "limit-uptime": time_limit,
                    # comment makes the user identifiable in the RouterOS UI
                    # as system-created, not manually added by an admin.
                    "comment":      "zealsync-auto",
                },
            )

        self._check_response(response, context=f"create hotspot user '{username}'")

        # The /add endpoint returns {"ret": "*2"} — just the internal ID.
        # We do a follow-up GET to return the full user object so callers have
        # all fields (name, profile, limit-uptime, .id, etc.) for logging/storage.
        create_result = response.json()
        mikrotik_id = create_result.get("ret")

        logger.info(f"MikroTik: created hotspot user '{username}' id={mikrotik_id} profile='{profile}'")

        # Return a synthetic dict with the key fields so callers don't need
        # to make a second request just to know what was created.
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
        This is intentional because:
          1. Revoke might be called multiple times (admin clicks twice).
          2. The user might have already expired and been cleaned up by
             MikroTik's own expiry mechanism.
          3. A retry after a failed previous delete should not raise an error.

        The lookup-then-delete pattern (two HTTP calls) is necessary because
        RouterOS DELETE requires the internal ".id" (e.g. "*3F"), not the
        human-readable username. We first GET to find the ".id", then DELETE.

        Args:
            username: The voucher code (same as the MikroTik username).

        Raises:
            MikroTikError: Only on unexpected errors, not on "user not found".
            httpx.RequestError: If the router is unreachable.
        """
        async with self._make_client() as client:
            # Step 1: Find the user's internal .id by querying by name.
            # ?name=X is a RouterOS query filter — returns matching users.
            find_response = await client.get(
                "/ip/hotspot/user",
                params={"name": username},
            )
            self._check_response(find_response, context=f"find hotspot user '{username}'")

            users = find_response.json()

            if not users:
                # User doesn't exist — idempotent success.
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

        In RouterOS, an active session means a device is currently connected
        through the hotspot and traffic is flowing. This is different from
        hotspot users (credentials): a user can exist without an active session.

        The returned list can be used for:
          - Counting concurrent users for capacity planning.
          - Syncing session data to the sessions table (future v2 sync job).
          - Admin dashboard: "X customers are online right now."

        Returns:
            List of session dicts. Each dict includes fields like:
              ".id", "user", "address", "mac-address", "bytes-in", "bytes-out",
              "uptime", "server"
            RouterOS hyphenates field names (bytes-in, not bytes_in).

        Raises:
            MikroTikError: If RouterOS returns an error.
            httpx.RequestError: If the router is unreachable.
        """
        async with self._make_client() as client:
            response = await client.get("/ip/hotspot/active")

        self._check_response(response, context="get active sessions")
        sessions = response.json()

        # RouterOS returns an empty list [] when there are no active sessions.
        # It does NOT return 404 — that's a RouterOS quirk. So we don't need
        # to handle a 404 here.
        return sessions if isinstance(sessions, list) else []

    async def get_user_profile_names(self) -> list[str]:
        """
        Returns the names of all hotspot user profiles configured on the router.

        Hotspot user profiles control per-user bandwidth limits, session timeouts,
        and traffic quotas. Each profile must be created manually in MikroTik
        before our API can assign users to it.

        We use this method for:
          1. Health check: confirms the router is reachable and profiles exist.
          2. Validation: before creating a package, we could verify the profile
             name exists (currently not implemented — kept as a v2 feature).

        Expected profiles to exist on your CHR:
          "10Mbps", "20Mbps", "50Mbps"
          Create them in RouterOS: /ip hotspot user profile add name=10Mbps
          rate-limit=10M/10M

        Returns:
            List of profile name strings, e.g. ["default", "10Mbps", "20Mbps"]

        Raises:
            MikroTikError: If RouterOS returns an error.
            httpx.RequestError: If the router is unreachable.
        """
        async with self._make_client() as client:
            response = await client.get("/ip/hotspot/user/profile")

        self._check_response(response, context="get user profiles")
        profiles = response.json()

        # Extract just the "name" field from each profile object.
        return [p.get("name", "") for p in profiles if isinstance(p, dict)]

    def _check_response(self, response: httpx.Response, context: str = "") -> None:
        """
        Checks an httpx response for RouterOS errors and raises MikroTikError.

        RouterOS REST API error format:
          HTTP 400/500 with body: {"detail": "some error message"}
          or: {"error": 400, "message": "Bad Request", "detail": "..."}

        We also treat any non-2xx response as an error, even if the body
        doesn't match the expected format — better to fail loudly than silently
        accept a malformed response.

        Args:
            response: The httpx.Response to check.
            context:  A human-readable description of what we were doing,
                      included in the error message for easier debugging.
                      e.g. "create hotspot user 'VOUCHER123'"

        Raises:
            MikroTikError: If the response indicates an error.
        """
        if response.is_success:
            return  # 2xx — all good

        # Try to extract RouterOS's error detail from the JSON body.
        try:
            body = response.json()
            detail = (
                body.get("detail")
                or body.get("message")
                or str(body)
            )
        except Exception:
            # Response body wasn't JSON — use raw text.
            detail = response.text or f"HTTP {response.status_code}"

        error_msg = f"MikroTik error during [{context}]: {response.status_code} — {detail}"
        logger.error(error_msg)
        raise MikroTikError(error_msg)


# ── Module-level singleton ────────────────────────────────────────────────────
# We create a single MikroTikClient instance at module import time.
# This is safe because MikroTikClient has no shared mutable state — each
# method call creates its own httpx.AsyncClient (see _make_client()).
# Background tasks and route handlers import this singleton:
#   from app.integrations.mikrotik import mikrotik_client
mikrotik_client = MikroTikClient()
