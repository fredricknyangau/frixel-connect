"""
app/modules/setup/router.py
============================
Public endpoints for the Magic Command router auto-configuration system.

AUTHENTICATION MODEL:
  These endpoints are intentionally public — no JWT is required.
  Authentication is provided by the setup token itself, which is:
  - 43 characters of URL-safe base64 (256-bit entropy)
  - Single-use (used_at column is set on /confirm)
  - Short-lived (expires_at = now + 24 hours)
  - Delivered to the admin over HTTPS in the frontend

  This "token as auth" pattern is identical to password reset links,
  email verification links, and similar single-use bootstrap flows.

SECURITY MODEL:
  1. Token entropy check (len >= 43) prevents timing attacks on short tokens.
     A timing attack: attacker guesses short prefixes; the DB lookup takes
     longer for near-misses than for invalid-length tokens, leaking info.
     We reject short tokens before the DB query to make all invalid requests
     equally fast at the application layer.

  2. expires_at > NOW() is evaluated inside PostgreSQL, not Python.
     If the app server and DB are on separate machines, their clocks may
     drift. Python's datetime.now() might be slightly ahead or behind the
     DB clock. Using NOW() inside the SQL query uses the DB's authoritative
     clock, eliminating the drift risk.

  3. Response headers prevent caching of the script by proxies or browsers.
     A cached script with an expired token would fail silently on the router.

  4. The /confirm endpoint NULLs out router_wg_private_key immediately after
     use, implementing zero-knowledge-after-setup.

  5. Rate limiting per token prevents enumeration attacks. An attacker who
     finds a valid token cannot hammer the endpoint to extract information.
"""

import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import PlainTextResponse

from app.config import settings
from app.core.rate_limit import RateLimiter
from app.database import get_db
from app.services.script_generator import build_setup_script
from app.integrations.wireguard import add_wireguard_peer

logger = logging.getLogger(__name__)

router = APIRouter()

# Rate limiter for the setup endpoint.
# 10 requests per token per hour is generous for legitimate use:
# the script is downloaded once, /confirm is called once.
# More than 10 requests on a single token indicates an attack or
# severe misconfiguration — both should be blocked.
# NOTE: The existing RateLimiter keys by IP+path. For this endpoint we
# want per-token rate limiting. We use the token as part of the path,
# which the RateLimiter already incorporates via request.url.path.
# This works correctly because each token has its own distinct path segment.
setup_rate_limiter = RateLimiter(requests=10, window=3600)


# ── GET /setup/{token} ─────────────────────────────────────────────────────────

@router.get(
    "/{token}",
    summary="Download router auto-configuration script (public, token auth)",
    response_class=PlainTextResponse,
)
async def download_setup_script(
    token: str,
    request: Request,
    _rate_limit: None = Depends(setup_rate_limiter),
) -> PlainTextResponse:
    """
    Serves the RouterOS .rsc auto-configuration script for the given token.

    Called by the MikroTik router's `/tool fetch` command as part of the
    Magic Command: `/tool fetch url=".../{token}" dst-path=zealsync-setup.rsc`

    IMPORTANT: This endpoint does NOT mark the token as used on download.
    The token is only consumed when the router calls POST /setup/{token}/confirm.
    Reason: the MikroTik `/tool fetch` command might fail partway through a
    large download (network blip, timeout). The admin should be able to run
    the magic command again without needing a new token.

    ERROR RESPONSES:
    All errors return plain text (not JSON) with a 4xx status code.
    Reason: the router will attempt to `/import` whatever it downloads.
    A JSON error body ({"detail": "..."}) would be treated as invalid RouterOS
    syntax and produce confusing error messages in the MikroTik terminal.
    Plain text starting with # is safe — RouterOS treats lines starting with
    # as comments and skips them.
    """

    # ── Security check 1: Token entropy guard ─────────────────────────────────
    # secrets.token_urlsafe(32) produces exactly 43 characters.
    # Reject anything shorter to prevent timing attacks on short guesses.
    #
    # WHAT IS A TIMING ATTACK?
    # A timing attack exploits the fact that "almost correct" values sometimes
    # take longer to process than "clearly wrong" values. If we checked tokens
    # character-by-character, an attacker could guess tokens one character at a
    # time by measuring response times. By rejecting short tokens BEFORE the
    # DB query (with a fast string length check), all short-token requests fail
    # at identical speed, giving the attacker no timing signal.
    if len(token) < 43:
        return PlainTextResponse(
            "# Error: Invalid setup token.\n# Tokens must be at least 43 characters.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    async with get_db() as conn:
        # ── Fetch token from DB (expiry checked at DB level) ──────────────────
        # IMPORTANT: expires_at > NOW() is evaluated by PostgreSQL using its own
        # clock. This avoids clock skew issues between app server and database.
        token_row = await conn.fetchrow(
            """
            SELECT
                st.id,
                st.router_id,
                st.tenant_id,
                st.token,
                st.router_wg_private_key,
                st.api_password,
                st.expires_at
            FROM setup_tokens st
            WHERE st.token = $1
              AND st.used_at IS NULL
              AND st.expires_at > NOW()
            """,
            token,
        )

        if not token_row:
            logger.warning(
                "Setup script download: token not found, expired, or already used",
                extra={"token_prefix": token[:8]},
            )
            return PlainTextResponse(
                "# Error: Setup token is invalid, expired, or already used.\n"
                "# Please generate a new setup command in the ZealSync admin portal.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        router_id = token_row["router_id"]
        tenant_id = token_row["tenant_id"]

        # ── Fetch router and tenant details ────────────────────────────────────
        router_row = await conn.fetchrow(
            """
            SELECT
                r.name,
                r.site_name,
                r.wireguard_assigned_ip,
                r.wireguard_peer_public_key
            FROM routers r
            WHERE r.id = $1 AND r.tenant_id = $2
            """,
            router_id,
            tenant_id,
        )

        if not router_row:
            logger.error(
                "Setup script download: token is valid but router not found",
                extra={"router_id": str(router_id), "token_prefix": token[:8]},
            )
            return PlainTextResponse(
                "# Error: Router configuration not found.\n"
                "# Please contact ZealSync support.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # ── Determine CHR mode ─────────────────────────────────────────────────
        # We infer is_chr from the wireguard_peer_public_key column.
        # When init-magic is called with is_chr=True, the router is inserted
        # without a wireguard_peer_public_key (no WG peer was pre-registered).
        # When is_chr=False, the peer key was set during init.
        # NOTE: The is_chr flag is not stored separately — we reconstruct it
        # from the absence of the WG peer public key. For CHR, there is no real
        # WG peer to register. If this logic needs to change, add an is_chr
        # column to the routers table.
        #
        # ALTERNATIVE: store is_chr in setup_tokens. We chose not to add a column
        # for a flag that only matters during onboarding (24-hour window).
        # The wireguard_peer_public_key absence is a sufficient signal.
        is_chr = router_row["wireguard_peer_public_key"] is None

        # ── Decrypt API password ───────────────────────────────────────────────
        from app.core.security import decrypt_secret
        api_password = decrypt_secret(token_row["api_password"])

        # ── Build confirm URL ──────────────────────────────────────────────────
        if is_chr:
            chr_host = getattr(settings, "CHR_HOST_IP", "192.168.56.1")
            chr_port = getattr(settings, "CHR_BACKEND_PORT", 8000)
            confirm_url = f"http://{chr_host}:{chr_port}/api/v1/setup/{token}/confirm"
        else:
            confirm_url = f"{settings.API_BASE_URL}/api/v1/setup/{token}/confirm"

        # ── Build the script ───────────────────────────────────────────────────
        assigned_wg_ip = str(router_row["wireguard_assigned_ip"]) if router_row["wireguard_assigned_ip"] else "10.8.0.2"

        script_content = build_setup_script(
            token=token,
            router_name=router_row["name"],
            wg_private_key=token_row["router_wg_private_key"] or "",
            server_public_key=settings.WIREGUARD_SERVER_PUBLIC_KEY or "",
            server_endpoint=settings.WIREGUARD_ENDPOINT,
            assigned_wg_ip=assigned_wg_ip,
            server_wg_ip="10.8.0.1",
            api_password=api_password,
            confirm_url=confirm_url,
            is_chr=is_chr,
        )

        # ── Write audit log entry ──────────────────────────────────────────────
        # NEVER log the full token — only the first 8 characters for correlation.
        # A partial token cannot be used to download the script, so logging it
        # is safe for debugging purposes (e.g., "which download caused the issue?")
        try:
            # Find any admin user in this tenant for the audit log actor.
            # The download is public (no JWT), so we use the tenant's first
            # admin user as a proxy actor. This is a limitation of our audit
            # log schema which requires an actor_user_id.
            actor_row = await conn.fetchrow(
                "SELECT id FROM users WHERE tenant_id = $1 AND role = 'admin' LIMIT 1",
                tenant_id,
            )
            if actor_row:
                await conn.execute(
                    """
                    INSERT INTO audit_log (tenant_id, actor_user_id, action, target_type, target_id, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    tenant_id,
                    actor_row["id"],
                    "router_setup_script_downloaded",
                    "router",
                    router_id,
                    json.dumps({
                        "token_prefix": token[:8],
                        "is_chr": is_chr,
                        "client_ip": request.client.host if request.client else "unknown",
                    }),
                )
        except Exception as audit_err:
            # Audit logging must never block the script from being served.
            logger.warning(f"Audit log write failed for setup download: {audit_err}")

    # ── Build response with security headers ───────────────────────────────────
    response = PlainTextResponse(
        content=script_content,
        status_code=status.HTTP_200_OK,
    )

    # Cache-Control: no-store — do not cache this response anywhere.
    # The script contains credentials (API password, WG private key).
    # A cached copy could be replayed after the token is consumed.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"

    # Pragma: no-cache — legacy HTTP/1.0 cache directive for older proxies.
    response.headers["Pragma"] = "no-cache"

    # Content-Disposition: attachment — tells browsers to download, not display.
    # Not strictly necessary (routers don't use browsers), but belt-and-suspenders.
    response.headers["Content-Disposition"] = 'attachment; filename="zealsync-setup.rsc"'

    # X-Content-Type-Options: nosniff — prevents MIME-type sniffing.
    # Without this, some proxies might re-interpret the text/plain response
    # as something else (e.g., HTML) and corrupt the script content.
    response.headers["X-Content-Type-Options"] = "nosniff"

    logger.info(
        "Setup script served",
        extra={
            "token_prefix": token[:8],
            "router_id": str(router_id),
            "is_chr": is_chr,
        },
    )

    return response


# ── POST /setup/{token}/confirm ────────────────────────────────────────────────

@router.post(
    "/{token}/confirm",
    summary="Confirm router setup is complete (called by the router itself)",
)
async def confirm_setup(
    token: str,
    _rate_limit: None = Depends(setup_rate_limiter),
) -> dict:
    """
    Called by the MikroTik router at the end of the setup script via:
        /tool fetch url="{confirm_url}" mode=http keep-result=no http-method=post

    This endpoint:
    1. Validates the token (same checks as the download endpoint)
    2. In a single transaction:
       - Marks used_at = NOW() on setup_tokens (token consumed, single-use enforced)
       - Sets routers.status = 'online'
       - Updates routers.last_heartbeat_at
       - NULLs out setup_tokens.router_wg_private_key (zero-knowledge after setup)
    3. Returns {"status": "confirmed", "router_id": "..."}

    The frontend is polling GET /admin/routers/onboarding/status/{router_id} every 3
    seconds. When this endpoint sets status='online', the next poll returns 'online'
    and the wizard advances to the "Setup complete!" screen.

    NOTE: The router does not check the response body — it uses keep-result=no.
    The HTTP 200 response is sufficient. We return JSON anyway for debugging.
    """

    if len(token) < 43:
        return PlainTextResponse(
            "# Error: Invalid token length.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    async with get_db() as conn:
        # Validate token — same DB-level expiry check as the download endpoint
        token_row = await conn.fetchrow(
            """
            SELECT id, router_id, tenant_id, router_wg_private_key
            FROM setup_tokens
            WHERE token = $1
              AND used_at IS NULL
              AND expires_at > NOW()
            """,
            token,
        )

        if not token_row:
            logger.warning(
                "Setup confirm: token not found, expired, or already used",
                extra={"token_prefix": token[:8]},
            )
            # Return 200 even for invalid tokens here — the router's /tool fetch
            # doesn't check the status code when keep-result=no, but returning
            # 4xx could cause the /tool fetch command to report an error in the
            # RouterOS log, confusing the ISP admin.
            # The damage is already done if we reach here — the script ran and
            # the router is already configured. We just can't mark it confirmed.
            return {
                "status": "token_invalid",
                "message": "Token not found or already used. Router may already be confirmed.",
            }

        router_id = token_row["router_id"]
        tenant_id = token_row["tenant_id"]

        # ── Atomic transaction: confirm setup ──────────────────────────────────
        # All three updates happen in one transaction. If any fails, none apply.
        # This prevents partial states like "token consumed but router still pending".
        async with conn.transaction():
            # 1. Consume the token — set used_at
            await conn.execute(
                "UPDATE setup_tokens SET used_at = NOW() WHERE id = $1",
                token_row["id"],
            )

            # 2. Zero out the private key — zero-knowledge after confirmation
            # From this point, the server has no knowledge of the router's WG private key.
            await conn.execute(
                "UPDATE setup_tokens SET router_wg_private_key = NULL WHERE id = $1",
                token_row["id"],
            )

            # 3. Mark router as online and update heartbeat timestamp
            await conn.execute(
                """
                UPDATE routers
                SET status = 'online',
                    last_heartbeat_at = NOW()
                WHERE id = $1 AND tenant_id = $2
                """,
                router_id,
                tenant_id,
            )

        # ── Safety net: ensure WireGuard peer is registered ───────────────────
        # The peer was pre-registered during /init-magic. If that call succeeded
        # but the peer wasn't saved (e.g., wg-quick save failed silently), this
        # re-registers it. For CHR (no real WG peer), this is a no-op mock call.
        router_row = await conn.fetchrow(
            "SELECT wireguard_peer_public_key, wireguard_assigned_ip FROM routers WHERE id = $1",
            router_id,
        )
        if router_row and router_row["wireguard_peer_public_key"] and router_row["wireguard_assigned_ip"]:
            try:
                add_wireguard_peer(
                    router_row["wireguard_peer_public_key"],
                    str(router_row["wireguard_assigned_ip"]),
                )
            except Exception as wg_err:
                # Don't fail the confirmation if WG peer re-registration fails.
                # The router is configured and calling us — the VPN might already
                # be working. Log for investigation but don't block the response.
                logger.error(
                    f"WG peer re-registration failed during confirm (non-fatal): {wg_err}",
                    extra={"router_id": str(router_id)},
                )

    logger.info(
        "Router setup confirmed",
        extra={"router_id": str(router_id), "token_prefix": token[:8]},
    )

    return {
        "status": "confirmed",
        "router_id": str(router_id),
        "message": "Router is now online. ZealSync dashboard will update shortly.",
    }
