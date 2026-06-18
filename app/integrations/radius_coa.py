"""
app/integrations/radius_coa.py
==============================
Centralised client for sending RADIUS Change of Authorization (CoA) Disconnect-Requests.
Uses the pyrad library to construct and send UDP disconnect packets to the NAS (router).
"""

import logging
import os
from pyrad.client import Client
from pyrad import dictionary, packet

from app.config import settings

logger = logging.getLogger(__name__)

# Dynamically locate the minimal RADIUS dictionary file
DICTIONARY_PATH = os.path.join(os.path.dirname(__file__), "radius_dictionary")


def send_coa_disconnect(
    router_ip: str,
    username: str,
    session_id: str | None = None,
) -> bool:
    """
    Sends a RADIUS Disconnect-Request CoA packet (RFC 3576 / RFC 5176) to the router
    on its CoA port (UDP port 3799) using the global shared CoA secret.

    RADIUS CoA PACKETS EXPLAINED:
      - CoA (Change of Authorization) is a push-based mechanism where the RADIUS server
        (or API backend) sends a packet to the NAS (Router) requesting a change in session state.
      - Disconnect-Request (Code 40) asks the router to terminate the active user session.
      - To match and terminate the session, the router requires session identification
        attributes. We send 'User-Name' (the voucher code) and optionally 'Acct-Session-Id'.
      - The router responds with Disconnect-ACK (Code 41) on success, or Disconnect-NAK (Code 42)
        if the session cannot be found or matched.

    Args:
        router_ip:  The host/IP address of the router.
        username:   The username (voucher code) to terminate.
        session_id: The unique accounting session ID to terminate, if active.

    Returns:
        True if the router successfully acknowledged the disconnection (DisconnectACK),
        otherwise False.
    """
    secret = settings.RADIUS_COA_SECRET.encode()
    logger.info(
        f"CoA: Preparing Disconnect-Request for user '{username}' on router {router_ip} "
        f"(Session ID: {session_id or 'none'})"
    )

    try:
        # Load the minimal dictionary defining attributes User-Name and Acct-Session-Id
        rad_dict = dictionary.Dictionary(DICTIONARY_PATH)

        # Initialize pyrad client pointing to the router's IP and CoA port (3799)
        client = Client(
            server=router_ip,
            secret=secret,
            dict=rad_dict,
        )
        # CoA port is traditionally 3799 (some NAS legacy defaults use 1700)
        client.coaport = 3799
        client.timeout = 5  # CoA responses are usually instant

        # Define attributes to uniquely target the session on the NAS
        attrs = {
            "User-Name": username,
        }
        if session_id:
            attrs["Acct-Session-Id"] = session_id

        # Convert dictionary keys for pyrad compatibility (replacing hyphens with underscores)
        pyrad_attrs = {k.replace("-", "_"): v for k, v in attrs.items()}

        # Create Disconnect-Request packet (Code 40)
        request_packet = client.CreateCoAPacket(
            code=packet.DisconnectRequest,
            **pyrad_attrs,
        )

        # Send the UDP packet and wait for response
        response = client.SendPacket(request_packet)

        logger.info(f"CoA: Received response code {response.code} from {router_ip}")

        if response.code == packet.DisconnectACK:
            logger.info(f"CoA: Session terminated successfully for user '{username}' on {router_ip}.")
            return True
        elif response.code == packet.DisconnectNAK:
            logger.warning(
                f"CoA: Router {router_ip} returned Disconnect-NAK. "
                f"Session might have already ended or attributes did not match."
            )
            return False
        else:
            logger.error(f"CoA: Unexpected response code {response.code} from router {router_ip}.")
            return False

    except Exception as e:
        logger.error(
            f"CoA: Failed to send Disconnect-Request to router '{router_ip}' for user '{username}': {e}",
            exc_info=True,
        )
        return False
