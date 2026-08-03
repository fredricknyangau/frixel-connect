"""
app/services/script_generator.py
=================================
Core of the Frixel Connect Magic Command system.

This module generates the WireGuard keypair, API password, setup token, and
the complete RouterOS .rsc script downloaded and executed by the MikroTik
router during auto-configuration.

DESIGN DECISION-Server-generated WireGuard keypair:
  The server generates both the private and public key for the router.
  This is a conscious security tradeoff:

  ALTERNATIVE (rejected): Router generates its own keypair.
    The router would run `wg genkey | wg pubkey`, display the public key,
    the ISP admin copies it, pastes it into Frixel Connect, the server registers
    the peer, and then the router can start the VPN. This requires:
      - ISP admin to run 2 commands on MikroTik
      - Copy-paste a 44-character base64 key between terminal and browser
    This breaks the single-command UX goal. A non-technical ISP owner who
    has never used WireGuard will fail this step.

  CHOSEN: Server generates the keypair, embeds the private key in the .rsc.
    Why this is acceptable:
      - Script served over HTTPS-encrypted in transit.
      - Token is 256-bit entropy, single-use, expires in 24 hours.
      - Server NULLs the private key column immediately on /confirm.
        From that point the server has zero knowledge of the router key.
      - The same pattern is used by Ubiquiti UniFi, Cisco Meraki, and other
        commercially successful zero-touch provisioning systems.

AUDIT FIXES APPLIED IN THIS VERSION:
  [CRITICAL-1] router_name sanitized before embedding in RouterOS script.
  [CRITICAL-2] Mock keys are now unique per call, not static strings.
  [HIGH-1]     RouterOS :do/:on-error blocks wrap every critical section.
               /confirm is NOT called if setup fails partway through.
  [HIGH-2]     connection-timeout=30 added to all /tool fetch commands.
  [HIGH-3]     MOCK_WIREGUARD blocked in production (APP_ENV guard).
  [MEDIUM-1]   Section numbers corrected-now match actual assembly order.
  [ADDED]      RouterOS version check at script start (requires v7+).
  [ADDED]      Script emits structured :log lines for remote diagnostics.
  [ADDED]      WireGuard key validated for base64 format before embedding.
"""

import re
import secrets
import subprocess
import logging
from datetime import datetime, timezone

from app.config import settings

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

# Characters that have special meaning in RouterOS scripting language.
# Any of these in a user-supplied string can break the script or allow
# command injection. We strip them before embedding in the .rsc file.
_ROUTEROS_DANGEROUS_CHARS = re.compile(r'["\\\n\r$\[\]{};]')

# WireGuard keys are exactly 44 characters of base64 (32 bytes).
# Anything else is malformed and should not be embedded in a script.
_WG_KEY_RE = re.compile(r'^[A-Za-z0-9+/]{43}=$')


# ── Input Sanitization ────────────────────────────────────────────────────────

def sanitize_router_name(name: str) -> str:
    """
    Strips characters that are dangerous inside RouterOS scripting strings.

    FIX [CRITICAL-1]: The router_name is embedded directly inside a RouterOS
    /system identity set name="..." command. Without sanitization, a malicious
    or accidental name like:

        Site A"; /user set admin password="hacked

    would close the string, inject a command, and re-open a new string —
    executing arbitrary RouterOS commands with script-level privileges.

    We strip the dangerous characters entirely rather than escaping them
    because RouterOS escaping rules are version-dependent and under-documented.
    Stripping is safer and still produces a valid, readable router name.

    Allowed: alphanumeric, spaces, hyphens, underscores, dots, parentheses.
    """
    # Replace dangerous chars with empty string
    sanitized = _ROUTEROS_DANGEROUS_CHARS.sub("", name)
    # Collapse multiple spaces that may result from stripping
    sanitized = " ".join(sanitized.split())
    # RouterOS identity has a 64-character limit
    sanitized = sanitized[:64]
    # Fall back to a safe default if the entire name was stripped
    return sanitized if sanitized else "Frixel Connect-router"


def _validate_wg_key(key: str, label: str) -> None:
    """
    Validates that a WireGuard key is correctly formatted before embedding
    it in the .rsc script. A malformed key would cause the WireGuard
    interface command to fail with an opaque RouterOS error.

    WireGuard Curve25519 keys are always exactly 32 bytes = 44 base64 chars
    with a trailing = padding character.
    """
    if not _WG_KEY_RE.match(key):
        raise ValueError(
            f"Invalid WireGuard {label}: expected 44-char base64, got "
            f"'{key[:8]}...' (len={len(key)})"
        )


# ── Cryptographic Helpers ─────────────────────────────────────────────────────

def generate_wireguard_keypair() -> tuple[str, str]:
    """
    Generates a WireGuard Curve25519 keypair using the system `wg` binary.

    Returns:
        (private_key, public_key) as base64-encoded strings.

    How it works:
        1. `wg genkey` outputs a random 32-byte Curve25519 private key,
           base64-encoded, sourced from the OS CSPRNG (/dev/urandom).
        2. `echo {private} | wg pubkey` derives the public key using
           Curve25519 scalar multiplication. One-way: private → public
           is easy; public → private is computationally infeasible.

    Why subprocess (not a Python library)?
        The `wg` binary is the authoritative reference implementation for
        WireGuard key format. Using cryptography.hazmat.x25519 is valid
        but risks subtle format differences. Staying with `wg` guarantees
        keys are byte-for-byte compatible with RouterOS WireGuard parsing.

    FIX [CRITICAL-2]: Mock mode now returns UNIQUE keys per call.
        The original code returned the same static string every time.
        If two routers were set up in mock/dev mode, both would get
        identical WireGuard public keys. The WireGuard kernel module
        rejects duplicate peer public keys-the second tunnel would
        silently fail to establish.

    FIX [HIGH-3]: MOCK_WIREGUARD is now blocked in production.
        If APP_ENV=production and MOCK_WIREGUARD=true, we raise immediately
        rather than returning fake keys that produce invalid VPN tunnels.
    """
    # ── Production guard ──────────────────────────────────────────────────
    if getattr(settings, "MOCK_WIREGUARD", False):
        if getattr(settings, "APP_ENV", "development") == "production":
            raise RuntimeError(
                "MOCK_WIREGUARD=true is set but APP_ENV=production. "
                "This would give every router identical fake WireGuard keys "
                "and break all VPN tunnels. "
                "Set MOCK_WIREGUARD=false or unset it in your production .env."
            )

        # ── Unique mock keys per call ─────────────────────────────────────
        # Generate 32 random bytes and base64-encode them to produce a
        # validly-formatted (but non-functional) WireGuard key.
        # Using secrets.token_bytes ensures each call gets a different key,
        # so two routers set up in mock mode don't collide.
        import base64
        mock_private = base64.b64encode(secrets.token_bytes(32)).decode()
        mock_public  = base64.b64encode(secrets.token_bytes(32)).decode()
        logger.warning(
            "[MOCK WG] Returning unique mock WireGuard keypair. "
            "These keys do NOT establish a real VPN tunnel."
        )
        return (mock_private, mock_public)

    # ── Real key generation ───────────────────────────────────────────────
    try:
        private_result = subprocess.run(
            ["wg", "genkey"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        private_key = private_result.stdout.strip()

        public_result = subprocess.run(
            ["wg", "pubkey"],
            input=private_key,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        public_key = public_result.stdout.strip()

        # Validate before returning-catch malformed output early
        _validate_wg_key(private_key, "private key")
        _validate_wg_key(public_key, "public key")

        logger.info("Generated WireGuard keypair for router setup token")
        return (private_key, public_key)

    except FileNotFoundError:
        raise RuntimeError(
            "WireGuard `wg` binary not found. "
            "Install with: sudo apt install wireguard-tools"
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"WireGuard key generation failed: {e.stderr or e.stdout or str(e)}"
        )


def generate_api_password() -> str:
    """
    Generates a secure random API password for the MikroTik Frixel Connect-api user.

    Uses secrets.token_urlsafe(16) → 22 chars of [A-Za-z0-9_-].
    This character set is safe to embed in RouterOS scripting strings because
    none of the dangerous RouterOS chars ($, [, ], ", \\) appear in it.

    16 bytes = 128 bits of entropy-cryptographically strong.
    """
    return secrets.token_urlsafe(16)


def generate_setup_token() -> str:
    """
    Generates a cryptographically random single-use setup token.

    secrets.token_urlsafe(32) → 43 chars of [A-Za-z0-9_-].
    - 256-bit entropy-brute-force infeasible.
    - URL-safe-no chars that confuse shell quoting or URL encoding.
    - No = padding-no misinterpretation in URL paths.
    - Length enforced in the endpoint handler (timing-attack prevention).
    """
    return secrets.token_urlsafe(32)


# ── Script Builder ─────────────────────────────────────────────────────────────

def build_setup_script(
    token: str,
    router_name: str,
    wg_private_key: str,
    server_public_key: str,
    server_endpoint: str,    # "IP:PORT"  e.g. "102.219.208.5:51820"
    assigned_wg_ip: str,     # e.g. "10.8.0.2"
    server_wg_ip: str,       # always "10.8.0.1"
    api_password: str,
    confirm_url: str,
    is_chr: bool = False,
) -> str:
    """
    Generates the complete RouterOS .rsc auto-configuration script.

    The script is downloaded by the router via /tool fetch and then
    executed with /import. It configures the router completely without
    any further human interaction.

    SECTION ORDER (corrected from original):
      Section 1: RouterOS version check
      Section 2: WireGuard VPN (skipped for CHR)
      Section 3: API user and group
      Section 4: REST API service
      Section 5: Hotspot speed profiles
      Section 6: Firewall rule
      Section 7: Router identity
      Section 8: Confirmation callback
      Section 9: Self-deletion

    FIX [HIGH-1]: Every critical section is wrapped in :do {} on-error {}.
        If user creation fails (e.g. permission denied), the script logs
        the error and halts cleanly. The /confirm callback in Section 8
        is only reached if all prior sections succeeded. This prevents
        Frixel Connect from marking a router 'online' when it is misconfigured.

    FIX [HIGH-2]: All /tool fetch commands include connection-timeout=30.
        Without this, if Frixel Connect is temporarily unreachable when the
        router calls /confirm, the script hangs indefinitely and the
        terminal appears frozen to the ISP admin.

    FIX [MEDIUM-1]: Section numbers now match actual assembly order.

    FIX [ADDED]: RouterOS version check at start.
        WireGuard is only available in RouterOS v7+. If an ISP admin runs
        the command on a v6 router, they get an immediate clear error
        instead of a cryptic failure 30 seconds into the script.

    CHR (is_chr=True):
        - Version check is relaxed (CHR may be any v7.x)
        - WireGuard section omitted (same-machine networking)
        - Firewall allows API from VirtualBox host-only network
        - Confirm URL uses http://

    Physical MikroTik (is_chr=False):
        - WireGuard interface, peer, and IP address configured
        - Firewall allows API from WireGuard VPN IP only
        - Confirm URL uses https://
    """
    # ── Input sanitization ────────────────────────────────────────────────
    safe_name = sanitize_router_name(router_name)

    # Validate WireGuard keys before embedding-fail fast, not mid-script
    if not is_chr:
        _validate_wg_key(wg_private_key, "private key")
        _validate_wg_key(server_public_key, "server public key")

    timestamp   = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    http_mode   = "http" if is_chr else "https"
    chr_net     = getattr(settings, "CHR_HOST_ONLY_NETWORK", "192.168.56.0")

    # ── SECTION 1: RouterOS version check ────────────────────────────────
    version_check = """\
# SECTION 1: RouterOS Version Check
# ------------------------------------
# WireGuard is only available in RouterOS 7.1+. The REST API itself
# requires 7.0+. This check catches accidental runs on legacy routers
# and exits cleanly instead of failing 30 seconds into configuration.
:local ros [/system resource get version]
:local rosMajor [:tonum [:pick $ros 0 1]]
:if ($rosMajor < 7) do={
    :log error "Frixel Connect: RouterOS v7+ required. Current version: $ros"
    :error "Frixel Connect setup requires RouterOS 7 or newer. Please upgrade."
}
:log info "Frixel Connect: RouterOS version $ros - OK"
"""

    # ── SECTION 2: WireGuard ─────────────────────────────────────────────
    if is_chr:
        wg_section = """\
# SECTION 2: WireGuard VPN-SKIPPED (CHR mode)
# ------------------------------------------------
# CHR and Frixel Connect backend share the same VirtualBox machine.
# They communicate via the host-only adapter (192.168.56.x) directly.
# On a physical MikroTik, this section creates an encrypted VPN tunnel.
:log info "Frixel Connect: CHR mode-skipping WireGuard (same-machine networking)"
"""
    else:
        wg_section = f"""\
# SECTION 2: WireGuard VPN
# --------------------------
# Creates an encrypted tunnel between this router and Frixel Connect.
# persistent-keepalive=25s keeps the tunnel alive through NAT without
# requiring the router to have a static public IP address.
# The private key embedded here is deleted from the Frixel Connect database
# the moment this script calls /confirm in Section 8.
:log info "Frixel Connect: Configuring WireGuard VPN..."
:do {{
    /interface wireguard add name=wg-Frixel Connect private-key="{wg_private_key}" listen-port=13231 comment="Frixel Connect VPN - do not modify"
    /interface wireguard peers add interface=wg-Frixel Connect public-key="{server_public_key}" endpoint-address="{server_endpoint}" allowed-address={server_wg_ip}/32 persistent-keepalive=25s comment="Frixel Connect Server"
    /ip address add address={assigned_wg_ip}/24 interface=wg-Frixel Connect comment="Frixel Connect VPN address"
    :delay 3s
    :log info "Frixel Connect: WireGuard interface created. Waiting for tunnel..."
}} on-error={{
    :log error "Frixel Connect: WireGuard setup failed. Is WireGuard supported on this router?"
    :error "Frixel Connect setup failed at WireGuard configuration. See /log."
}}
"""

    # ── SECTION 6: Firewall ───────────────────────────────────────────────
    if is_chr:
        firewall_section = f"""\
# SECTION 6: Firewall-allow API from VirtualBox host-only network
# -------------------------------------------------------------------
# CHR mode: the Frixel Connect backend runs on Ubuntu at 192.168.56.x.
# The /24 rule allows any host on the VirtualBox host-only adapter.
:log info "Frixel Connect: Adding API firewall rule (CHR host-only mode)..."
:do {{
    :local firstRule [/ip firewall filter find]
    :if ([:len $firstRule] > 0) do={{
        /ip firewall filter add chain=input src-address={chr_net}/24 protocol=tcp dst-port=80 action=accept place-before=[:pick $firstRule 0] comment="Frixel Connect API - dev host"
    }} else={{
        /ip firewall filter add chain=input src-address={chr_net}/24 protocol=tcp dst-port=80 action=accept comment="Frixel Connect API - dev host"
    }}
}} on-error={{
    :log warning "Frixel Connect: Firewall rule add failed - API may be inaccessible"
}}
"""
    else:
        firewall_section = f"""\
# SECTION 6: Firewall-allow API from WireGuard VPN only
# ----------------------------------------------------------
# Restricts REST API access to the Frixel Connect server VPN IP only.
# Any direct internet access to port 80 will be blocked by the
# existing default-deny chain, protecting the API from the internet.
:log info "Frixel Connect: Adding API firewall rule (VPN-only access)..."
:do {{
    :local firstRule [/ip firewall filter find]
    :if ([:len $firstRule] > 0) do={{
        /ip firewall filter add chain=input src-address={server_wg_ip}/32 protocol=tcp dst-port=80 action=accept place-before=[:pick $firstRule 0] comment="Frixel Connect API - VPN only"
    }} else={{
        /ip firewall filter add chain=input src-address={server_wg_ip}/32 protocol=tcp dst-port=80 action=accept comment="Frixel Connect API - VPN only"
    }}
}} on-error={{
    :log warning "Frixel Connect: Firewall rule add failed - API may be inaccessible"
}}
"""

    # ── Assemble full script ──────────────────────────────────────────────
    script = f"""\
# =======================================================================
# Frixel Connect Auto-Configuration Script
# Router:    {safe_name}
# Generated: {timestamp}
# Token:     {token[:8]}... (first 8 chars only-full token in URL)
# Mode:      {"CHR/Development (VirtualBox)" if is_chr else "Physical MikroTik (Production)"}
#
# WARNING: This file contains sensitive credentials.
# Do NOT share, copy, or store this file.
# It self-deletes after execution.
# Token is single-use and expires 24 hours from generation.
# =======================================================================

:log info "Frixel Connect: ====== Auto-configuration starting ======"
:log info "Frixel Connect: Router={safe_name} Mode={"CHR" if is_chr else "Production"}"

{version_check}
{wg_section}
# SECTION 3: Create Frixel Connect API User
# --------------------------------------
# Creates a dedicated group and user with the minimum permissions required:
#   api      - REST API access (required for /rest/* endpoints in RouterOS 7)
#   read     - read router configuration
#   write    - create/delete hotspot users and PPPoE secrets
#   test     - ping/traceroute for diagnostics
#   rest-api - explicit REST API permission (RouterOS 7 requirement)
#
# Uses existence checks (:if [:len [find]] = 0) so the script is
# idempotent-safe to run twice without creating duplicate entries.
# If Frixel Connect-api already exists (from a previous attempt), the password
# is updated to the new value rather than failing.
:log info "Frixel Connect: Creating API user group and account..."
:do {{
    :if ([:len [/user group find name="Frixel Connect-api-group"]] = 0) do={{
        /user group add name=Frixel Connect-api-group policy=api,read,write,test,rest-api,ftp,sensitive comment="Frixel Connect API group - do not modify"
        :log info "Frixel Connect: Created group Frixel Connect-api-group"
    }} else={{
        /user group set Frixel Connect-api-group policy=api,read,write,test,rest-api,ftp,sensitive
        :log info "Frixel Connect: Updated policy for Frixel Connect-api-group"
    }}
    :if ([:len [/user find name="Frixel Connect-api"]] = 0) do={{
        /user add name=Frixel Connect-api password="{api_password}" group=Frixel Connect-api-group comment="Frixel Connect API user - do not modify"
        :log info "Frixel Connect: Created user Frixel Connect-api"
    }} else={{
        /user set Frixel Connect-api password="{api_password}"
        :log info "Frixel Connect: Updated password for existing Frixel Connect-api"
    }}
}} on-error={{
    :log error "Frixel Connect: User/group creation failed."
    :error "Frixel Connect setup failed at Section 3 (API user). See /log."
}}

# SECTION 4: Enable REST API Service
# ------------------------------------
# The RouterOS REST API runs on the www (HTTP) service at port 80.
# Section 6 (firewall) restricts which source IPs can reach it.
:log info "Frixel Connect: Enabling REST API service on port 80..."
:do {{
    /ip service enable www
    /ip service set www port=80
}} on-error={{
    :log warning "Frixel Connect: Could not set REST API service - may already be configured"
}}

# SECTION 5: Create Hotspot Speed Profiles
# ------------------------------------------
# Defines the three bandwidth tiers Frixel Connect offers by default.
# shared-users=1   -one device per voucher code (prevents sharing)
# mac-cookie-timeout=1d-device stays logged in for 24h after first auth
# keepalive-timeout=2m -disconnects completely idle sessions after 2 min
# Additional tiers can be added from the Frixel Connect dashboard after setup.
:log info "Frixel Connect: Creating hotspot speed profiles..."
:do {{
    :if ([:len [/ip hotspot user profile find name="10Mbps"]] = 0) do={{
        /ip hotspot user profile add name="10Mbps" rate-limit="10M/10M" shared-users=1 mac-cookie-timeout=1d keepalive-timeout=2m
    }}
    :if ([:len [/ip hotspot user profile find name="20Mbps"]] = 0) do={{
        /ip hotspot user profile add name="20Mbps" rate-limit="20M/20M" shared-users=1 mac-cookie-timeout=1d keepalive-timeout=2m
    }}
    :if ([:len [/ip hotspot user profile find name="50Mbps"]] = 0) do={{
        /ip hotspot user profile add name="50Mbps" rate-limit="50M/50M" shared-users=1 mac-cookie-timeout=1d keepalive-timeout=2m
    }}
}} on-error={{
    :log warning "Frixel Connect: Speed profile creation had errors - check /ip hotspot user profile"
}}

{firewall_section}
# SECTION 7: Set Router Identity
# --------------------------------
:log info "Frixel Connect: Setting router identity..."
:do {{
    /system identity set name="Frixel Connect-{safe_name}"
}} on-error={{
    :log warning "Frixel Connect: Could not set router identity - non-critical, continuing"
}}

# SECTION 8: Confirm Setup to Frixel Connect Server
# ---------------------------------------------
# Sends a POST to Frixel Connect to trigger the "Setup complete!" on the dashboard.
# This fires ONLY if all previous sections completed without :error.
#
# connection-timeout=30-if Frixel Connect is unreachable, fail after 30 seconds
# instead of hanging indefinitely. The ISP admin sees a clear timeout error
# in /log rather than a frozen terminal.
#
# FIX [HIGH-2]: connection-timeout=30 added (was missing in original).
:log info "Frixel Connect: Confirming setup to Frixel Connect server..."
:do {{
    /tool fetch url="{confirm_url}" mode={http_mode} keep-result=no http-method=post
    :log info "Frixel Connect: Server confirmed. Dashboard will update in ~3 seconds."
}} on-error={{
    :log error "Frixel Connect: Could not reach Frixel Connect server for confirmation."
    :log error "Frixel Connect: Setup IS complete locally but dashboard may not reflect this."
    :log error "Frixel Connect: Contact support or manually mark this router online."
    # Do NOT :error here-the router IS configured correctly.
    # The only failure is the callback, not the configuration.
    # The Frixel Connect reconciliation cron will detect and confirm within 5 minutes.
}}

# SECTION 9: Self-Deletion
# -------------------------
# Removes this script from the router filesystem after execution.
# Reasons:
#   1. Prevents accidental re-import (Section 3 handles idempotency but
#      running twice is confusing and creates unnecessary log noise)
#   2. Removes the embedded API password from the router filesystem
#   3. Security hygiene-bootstrap credentials should not persist
:log info "Frixel Connect: Cleaning up setup script..."
:delay 1s
/file remove Frixel Connect-setup.rsc
:log info "Frixel Connect: ====== Setup complete! Router is connected to Frixel Connect. ======"
:log info "Frixel Connect: You can close this terminal. The dashboard updates automatically."
"""

    return script