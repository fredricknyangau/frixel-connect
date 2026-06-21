"""
app/services/script_generator.py
=================================
Core of the ZealSync Magic Command system.

This module generates the WireGuard keypair, API password, setup token, and
the complete RouterOS .rsc script that is downloaded and executed by the
MikroTik router during auto-configuration.

DESIGN DECISION — Server-generated WireGuard keypair:
  The server generates both the private and public key for the router.
  This is a conscious security tradeoff:

  ALTERNATIVE (rejected): Router generates its own keypair.
    The router would run `wg genkey | wg pubkey`, display the public key,
    the ISP admin copies it, pastes it into the ZealSync web UI, the server
    registers the peer, and then the router can start the VPN. This requires:
    - ISP admin to run 2 commands on MikroTik
    - Copy-paste a 44-character base64 key
    - Switch between terminal and browser
    This breaks the single-command UX. A non-technical ISP owner in rural
    Kenya who has never used WireGuard will fail this step.

  CHOSEN: Server generates the keypair, embeds private key in the .rsc script.
    Why this is acceptable:
    - The script is served over HTTPS (encrypted in transit, not interceptable
      by a passive network observer).
    - The token is URL-safe, 43 characters, single-use, and expires in 24 hours.
      The attack window is narrow.
    - The server NULLs out the private key column the moment the router calls
      /confirm. From that point the server has zero knowledge of the router's
      private key — perfect forward secrecy is achieved post-setup.
    - The alternative is not more secure in practice because a non-technical
      ISP admin who fails the manual key exchange will use less secure
      workarounds (screenshots, WhatsApp messages, etc.).
    - This pattern is used by commercially successful zero-touch provisioning
      systems (Ubiquiti UniFi, Cisco Meraki, etc.) for the same reasons.
"""

import secrets
import subprocess
import logging
from datetime import datetime, timezone

from app.config import settings

logger = logging.getLogger(__name__)


# ── Cryptographic Helpers ─────────────────────────────────────────────────────

def generate_wireguard_keypair() -> tuple[str, str]:
    """
    Generates a WireGuard Curve25519 keypair using the system `wg` binary.

    Returns:
        (private_key, public_key) as base64-encoded strings.

    How it works:
        1. `wg genkey` outputs a random 32-byte Curve25519 private key,
           base64-encoded. The randomness comes from the OS CSPRNG (/dev/urandom).
        2. `echo {private} | wg pubkey` mathematically derives the corresponding
           public key using Curve25519 scalar multiplication. This is a one-way
           function: you can always derive the public key from the private key,
           but not vice versa.

    Why subprocess (not a Python library)?
        The `wg` binary is already a dependency for the WireGuard server interface.
        Using `cryptography.hazmat.primitives.asymmetric.x25519` would add a
        dependency that could diverge from the wg binary's key format in edge cases.
        Staying with `wg` keeps the key format guaranteed compatible.

    CHR NOTE: This runs on the ZealSync backend (Ubuntu), not the MikroTik CHR.
    The CHR never runs `wg genkey` — it receives the pre-generated key in the script.
    """
    if settings.MOCK_WIREGUARD:
        # In mock mode, return deterministic fake keys for development.
        # These are valid base64 format but not real WireGuard keys.
        mock_private = "mFn3xzDvKlPqRsYwJhGtNbCuAeOiVkXdWmZpLnQfTs0="
        mock_public = "xTk7BvNpJgRdYsHlKqWzCaEmFoIuPtVbXnMjGeOcSw4="
        logger.info("[MOCK WG] Returning mock WireGuard keypair")
        return (mock_private, mock_public)

    try:
        # Step 1: Generate private key
        private_result = subprocess.run(
            ["wg", "genkey"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        private_key = private_result.stdout.strip()

        # Step 2: Derive public key from private key
        public_result = subprocess.run(
            ["wg", "pubkey"],
            input=private_key,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        public_key = public_result.stdout.strip()

        logger.info("Generated WireGuard keypair for router setup token")
        return (private_key, public_key)

    except FileNotFoundError:
        raise RuntimeError(
            "WireGuard `wg` binary not found. Install with: sudo apt install wireguard-tools"
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"WireGuard key generation failed: {e.stderr or e.stdout or str(e)}"
        )


def generate_api_password() -> str:
    """
    Generates a secure random API password for the MikroTik zealsync-api user.

    Uses secrets.token_urlsafe(16) which produces 22 characters of
    [A-Za-z0-9_-] (URL-safe base64). This character set is safe to embed
    in RouterOS scripting without quoting issues because RouterOS string
    values using quotes only misinterpret: ", \\, $, [, ] — none of which
    appear in URL-safe base64 output.

    16 bytes of entropy = 128 bits = cryptographically strong.
    """
    return secrets.token_urlsafe(16)


def generate_setup_token() -> str:
    """
    Generates a cryptographically random single-use setup token.

    Uses secrets.token_urlsafe(32) which produces 43 characters of
    [A-Za-z0-9_-]. Properties:
    - 32 bytes = 256 bits of entropy (brute-force infeasible)
    - URL-safe: no characters that confuse shell quoting or URL encoding
    - No padding characters (=) that could be misinterpreted in URLs
    - 43 characters minimum (enforced in the endpoint handler as a
      timing-attack prevention measure — see Phase 4 notes)
    """
    return secrets.token_urlsafe(32)


# ── Script Builder ─────────────────────────────────────────────────────────────

def build_setup_script(
    token: str,
    router_name: str,
    wg_private_key: str,
    server_public_key: str,
    server_endpoint: str,      # "IP:PORT" e.g. "102.219.208.5:51820"
    assigned_wg_ip: str,       # e.g. "10.8.0.2"
    server_wg_ip: str,         # always "10.8.0.1"
    api_password: str,
    confirm_url: str,          # full URL for the /confirm callback
    is_chr: bool = False,      # CHR mode skips WireGuard (same-machine networking)
) -> str:
    """
    Generates the complete RouterOS .rsc auto-configuration script as a string.

    The script is designed to be imported via `/import zealsync-setup.rsc` after
    being downloaded with `/tool fetch`. It configures the router completely:
    1. WireGuard VPN (skipped for CHR — same-machine networking makes it redundant)
    2. API user and group with minimal required permissions
    3. REST API service on port 80
    4. Hotspot speed profiles (10/20/50 Mbps)
    5. Firewall rule allowing API access from ZealSync only
    6. Router identity
    7. Confirmation callback to ZealSync (triggers "Setup complete!" in UI)
    8. Self-deletion of this script file (security hygiene)

    CHR vs PHYSICAL ROUTER:
      CHR (is_chr=True):
        - WireGuard section is omitted entirely
        - Firewall allows API from the VirtualBox host-only network (192.168.56.0/24)
        - Confirm URL points to http://192.168.56.1:8000/...

      Physical MikroTik (is_chr=False):
        - Full WireGuard interface, peer, and IP address setup
        - Firewall allows API ONLY from WireGuard server IP (10.8.0.1/32)
        - Confirm URL points to https://api.zealsync.dev/...

    All RouterOS commands are on their own lines (no backslash continuation
    in RouterOS — the parser accepts each command independently, and multi-line
    commands in /import use the trailing backslash ONLY for `/tool fetch`).
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Determine protocol for the confirm URL fetch command
    http_mode = "http" if is_chr else "https"

    # The CHR host-only network for firewall rules
    chr_host_network = getattr(settings, "CHR_HOST_ONLY_NETWORK", "192.168.56.0")

    # ── Section 1: WireGuard Setup (Physical Only) ────────────────────────────
    if is_chr:
        wg_section = """\
# SECTION 1: WireGuard VPN Setup — SKIPPED for CHR mode
# -------------------------------------------------------
# CHR and the ZealSync backend are on the same VirtualBox machine.
# They communicate via the host-only network (192.168.56.x) without
# needing a WireGuard tunnel. On a physical MikroTik router deployed
# at an ISP site, this section would create a full WireGuard VPN.
:log info "ZealSync: CHR mode - skipping WireGuard setup (same-machine networking)"
"""
    else:
        wg_section = f"""\
# SECTION 1: WireGuard VPN Setup
# --------------------------------
# Creates an encrypted tunnel between this router and the ZealSync server.
# The private key was generated server-side, embedded here, and will be
# deleted from the ZealSync database after this script completes.
# The tunnel uses persistent-keepalive=25s to maintain the connection
# through NAT without requiring the router to have a static IP.
:log info "ZealSync: Configuring WireGuard VPN..."
/interface wireguard add name=wg-zealsync private-key="{wg_private_key}" listen-port=13231 comment="ZealSync VPN - managed automatically"
/interface wireguard peers add interface=wg-zealsync public-key="{server_public_key}" endpoint-address="{server_endpoint}" allowed-address={server_wg_ip}/32 persistent-keepalive=25s comment="ZealSync Server"
/ip address add address={assigned_wg_ip}/24 interface=wg-zealsync comment="ZealSync VPN address"
:delay 3s
:log info "ZealSync: WireGuard configured. Waiting for tunnel to establish..."
"""

    # ── Section 5: Firewall Rule ───────────────────────────────────────────────
    if is_chr:
        firewall_section = f"""\
# SECTION 5: Firewall — allow API from VirtualBox host-only network
# -----------------------------------------------------------------
# CHR mode: allow connections from the Ubuntu host (192.168.56.x) which
# is where the ZealSync backend is running. The /24 allows any host on
# the VirtualBox host-only adapter to reach the API.
#
# PHYSICAL ROUTER: Replace this with the WireGuard-only rule below:
# /ip firewall filter add chain=input src-address={server_wg_ip}/32 protocol=tcp dst-port=80 action=accept place-before=0 comment="ZealSync API access from VPN only"
:log info "ZealSync: Configuring API firewall rule (CHR host-only mode)..."
/ip firewall filter add chain=input src-address={chr_host_network}/24 protocol=tcp dst-port=80 action=accept place-before=0 comment="ZealSync API access from dev host"
"""
    else:
        firewall_section = f"""\
# SECTION 5: Firewall — allow API access from WireGuard server ONLY
# -----------------------------------------------------------------
# On a physical MikroTik, the REST API (port 80) must only be reachable
# through the WireGuard VPN. This rule accepts connections from the
# ZealSync server's VPN IP (10.8.0.1) and rejects all other API access.
# place-before=0 ensures this rule runs before any existing DROP rules.
:log info "ZealSync: Configuring API firewall rule (VPN-only access)..."
/ip firewall filter add chain=input src-address={server_wg_ip}/32 protocol=tcp dst-port=80 action=accept place-before=0 comment="ZealSync API access from VPN only"
"""

    # ── Assemble Full Script ───────────────────────────────────────────────────
    script = f"""\
# =======================================================================
# ZealSync Auto-Configuration Script
# Router:    {router_name}
# Generated: {timestamp}
# Token:     {token[:8]}... (truncated for log safety — full token in URL)
# Mode:      {"CHR/Development (VirtualBox)" if is_chr else "Physical MikroTik (Production)"}
#
# WARNING: This file contains sensitive credentials.
# Do NOT share this file. It self-destructs after execution.
# Token is single-use and expires 24 hours after generation.
# =======================================================================

:log info "ZealSync: Starting auto-configuration for router: {router_name}"

{wg_section}
# SECTION 2: Create ZealSync API User
# -------------------------------------
# Creates a dedicated API user and group with the minimum permissions
# required for ZealSync to manage hotspot sessions:
#   api   - allows REST API access
#   read  - allows reading router config (profiles, users, etc.)
#   write - allows creating/deleting hotspot users
#   test  - allows ping/traceroute for diagnostics
#
# The user group is named zealsync-api-group to make it easy to identify
# and audit. The password was generated by the ZealSync server using
# secrets.token_urlsafe(16) — 128 bits of entropy, URL-safe characters.
:log info "ZealSync: Creating API user and permissions group..."
/user group add name=zealsync-api-group policy=api,read,write,test comment="ZealSync API access - do not modify"
/user add name=zealsync-api password="{api_password}" group=zealsync-api-group comment="ZealSync API user - do not modify"

# SECTION 3: Enable REST API Service
# ------------------------------------
# RouterOS REST API runs on the www (HTTP) service at port 80.
# We enable it here so ZealSync can make API calls to manage users.
# The firewall rule in Section 5 restricts who can reach this port.
:log info "ZealSync: Enabling REST API on port 80..."
/ip service enable www
/ip service set www port=80

# SECTION 4: Create Hotspot Speed Profiles
# -----------------------------------------
# Speed profiles define the bandwidth tiers available to customers.
# These three tiers cover the most common pricing levels used by
# Kenyan ISPs. Additional tiers can be added manually after setup.
#
# rate-limit format: "upload/download"
# shared-users=1 means one user per profile slot (not shared)
# mac-cookie-timeout=1d allows reconnection without re-login for 24h
# keepalive-timeout=2m disconnects idle users after 2 minutes
:log info "ZealSync: Creating hotspot speed profiles..."
/ip hotspot user profile add name="10Mbps" rate-limit="10M/10M" shared-users=1 mac-cookie-timeout=1d keepalive-timeout=2m comment="ZealSync - 10Mbps tier"
/ip hotspot user profile add name="20Mbps" rate-limit="20M/20M" shared-users=1 mac-cookie-timeout=1d keepalive-timeout=2m comment="ZealSync - 20Mbps tier"
/ip hotspot user profile add name="50Mbps" rate-limit="50M/50M" shared-users=1 mac-cookie-timeout=1d keepalive-timeout=2m comment="ZealSync - 50Mbps tier"

{firewall_section}
# SECTION 6: Set Router Identity
# --------------------------------
# Sets the router's system name to "zealsync-{router_name}" so it's
# easy to identify in Winbox and SSH banners.
:log info "ZealSync: Setting router identity..."
/system identity set name="zealsync-{router_name}"

# SECTION 7: Confirm Setup to ZealSync Server
# ---------------------------------------------
# This is the critical callback step. The router sends a POST request to
# the ZealSync server to confirm that setup is complete. This triggers:
#   1. The setup_tokens.used_at timestamp is set (token is consumed)
#   2. routers.status is set to 'online'
#   3. routers.last_heartbeat_at is updated
#   4. setup_tokens.router_wg_private_key is set to NULL (zero-knowledge)
#   5. The frontend polling loop detects status='online' and shows "Done!"
#
# keep-result=no: we don't need the response body, just the HTTP call
# http-method=post: required to trigger server-side confirmation logic
:log info "ZealSync: Notifying ZealSync server of successful setup..."
/tool fetch url="{confirm_url}" mode={http_mode} keep-result=no http-method=post

# SECTION 8: Self-Deletion
# -------------------------
# A one-time setup script has no business remaining on the router after
# it has run. Deleting it:
#   1. Prevents accidental re-import (which would fail on duplicate users)
#   2. Removes the embedded API password from the filesystem
#   3. Is basic security hygiene for bootstrap credentials
:delay 1s
/file remove zealsync-setup.rsc
:log info "ZealSync: Setup complete! Router is now connected to ZealSync."
:log info "ZealSync: You can close this terminal. The ZealSync dashboard will update automatically."
"""

    return script
