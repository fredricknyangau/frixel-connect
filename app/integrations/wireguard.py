"""
app/integrations/wireguard.py
=============================
Subprocess-based integration with WireGuard CLI (wg and wg-quick).
Includes mock fallbacks when running in development environment without wg command.
"""

import logging
import os
import re
import subprocess
import time
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


def get_server_public_key() -> str:
    """
    Reads the WireGuard server public key.
    Runs `wg show wg0 public-key` or falls back to Settings.
    """
    if settings.MOCK_WIREGUARD:
        return settings.WIREGUARD_SERVER_PUBLIC_KEY or "Frixel ConnectServerPublicKeyWgPlaceholderBase64="

    try:
        result = subprocess.run(
            ["wg", "show", "wg0", "public-key"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except Exception as e:
        logger.warning(f"Failed to get WG public key via command: {e}. Trying file read or settings.")

    # Try file read fallback /etc/wireguard/wg0.conf and derive public key from PrivateKey
    try:
        if os.path.exists("/etc/wireguard/wg0.conf"):
            with open("/etc/wireguard/wg0.conf", "r") as f:
                content = f.read()
            match = re.search(r"PrivateKey\s*=\s*([a-zA-Z0-9+/=]+)", content)
            if match:
                privkey = match.group(1)
                res = subprocess.run(
                    ["wg", "pubkey"],
                    input=privkey,
                    capture_output=True,
                    text=True,
                    check=True
                )
                return res.stdout.strip()
    except Exception as fe:
        logger.error(f"Failed to read/derive public key from wg0.conf: {fe}")

    return settings.WIREGUARD_SERVER_PUBLIC_KEY or "Frixel ConnectServerPublicKeyWgPlaceholderBase64="


async def assign_peer_ip(conn) -> str:
    """
    Queries database for assigned IPs and returns the next available IP in 10.8.0.2-10.8.0.254 range.
    Raises Exception if range is exhausted.
    """
    rows = await conn.fetch(
        "SELECT wireguard_assigned_ip FROM routers WHERE wireguard_assigned_ip IS NOT NULL"
    )
    assigned_ips = {str(row["wireguard_assigned_ip"]) for row in rows}

    for i in range(2, 255):
        ip = f"10.8.0.{i}"
        if ip not in assigned_ips:
            return ip

    raise Exception("WireGuard peer IP range exhausted (>253 routers)")


def add_wireguard_peer(peer_public_key: str, assigned_ip: str) -> None:
    """
    Registers a peer under wg0 and saves configuration via wg-quick.
    """
    if settings.MOCK_WIREGUARD:
        logger.info(f"[MOCK WG] Adding peer {peer_public_key} with allowed-ip {assigned_ip}/32")
        return

    try:
        subprocess.run(
            ["wg", "set", "wg0", "peer", peer_public_key, "allowed-ips", f"{assigned_ip}/32"],
            check=True,
            capture_output=True,
            text=True
        )
        subprocess.run(
            ["wg-quick", "save", "wg0"],
            check=True,
            capture_output=True,
            text=True
        )
        logger.info(f"Successfully added WireGuard peer {peer_public_key} with IP {assigned_ip}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to add WireGuard peer: stdout={e.stdout}, stderr={e.stderr}")
        raise Exception(f"WireGuard CLI error: {e.stderr or e.stdout or str(e)}")


def remove_wireguard_peer(peer_public_key: str) -> None:
    """
    Deregisters a peer from wg0 and saves configuration.
    """
    if settings.MOCK_WIREGUARD:
        logger.info(f"[MOCK WG] Removing peer {peer_public_key}")
        return

    try:
        subprocess.run(
            ["wg", "set", "wg0", "peer", peer_public_key, "remove"],
            check=True,
            capture_output=True,
            text=True
        )
        subprocess.run(
            ["wg-quick", "save", "wg0"],
            check=True,
            capture_output=True,
            text=True
        )
        logger.info(f"Successfully removed WireGuard peer {peer_public_key}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to remove WireGuard peer: stdout={e.stdout}, stderr={e.stderr}")
        raise Exception(f"WireGuard CLI error: {e.stderr or e.stdout or str(e)}")


def check_peer_connected(assigned_ip: str) -> bool:
    """
    Checks if the last handshake for the peer assigned_ip was within 3 minutes (180s).
    """
    if settings.MOCK_WIREGUARD:
        logger.info(f"[MOCK WG] Checking peer connection for IP {assigned_ip}")
        return True

    try:
        # Find public key matching assigned_ip
        allowed_ips_proc = subprocess.run(
            ["wg", "show", "wg0", "allowed-ips"],
            capture_output=True,
            text=True,
            check=True
        )

        peer_pubkey: Optional[str] = None
        for line in allowed_ips_proc.stdout.strip().split("\n"):
            parts = line.split()
            if len(parts) >= 2:
                pubkey = parts[0]
                ips = parts[1:]
                if f"{assigned_ip}/32" in ips or assigned_ip in ips:
                    peer_pubkey = pubkey
                    break

        if not peer_pubkey:
            logger.warning(f"No WireGuard peer found with allowed-IP {assigned_ip}")
            return False

        # Get latest handshake for public key
        handshakes_proc = subprocess.run(
            ["wg", "show", "wg0", "latest-handshakes"],
            capture_output=True,
            text=True,
            check=True
        )

        for line in handshakes_proc.stdout.strip().split("\n"):
            parts = line.split()
            if len(parts) == 2 and parts[0] == peer_pubkey:
                timestamp = int(parts[1])
                if timestamp == 0:
                    return False
                elapsed = int(time.time()) - timestamp
                return elapsed <= 180

    except Exception as e:
        logger.error(f"Error checking WireGuard connection for IP {assigned_ip}: {e}")
        return False

    return False
