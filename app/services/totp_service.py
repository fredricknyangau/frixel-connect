"""
app/services/totp_service.py
=============================
TOTP (Time-based One-Time Password) utilities for super admin MFA.

HOW TOTP WORKS (RFC 6238):
  TOTP generates a 6-digit code that changes every 30 seconds. The code is
  derived from two inputs:
    1. A shared secret (a Base32-encoded random string, e.g. 32 characters).
    2. The current Unix timestamp floored to a 30-second window.

  Both the server and the authenticator app (Google Authenticator, Authy, etc.)
  independently compute HMAC-SHA1(secret, floor(timestamp / 30)). Because they
  share the same secret and use the same clock, they always produce the same
  6-digit output in the same time window-with NO network call required for
  verification.

  The QR code encodes an otpauth:// URI containing the secret, issuer name,
  and the user's email. Scanning it "teaches" the authenticator app the secret
  so it can generate codes forever without contacting the server again.

HOW SETUP WORKS FOR SUPER ADMIN:
  Step 1: Super admin logs in with email + password.
  Step 2: Server generates a TOTP secret, encrypts it, stores it in DB.
  Step 3: Server generates a QR code PNG (base64) and returns it once.
  Step 4: Super admin scans the QR with their authenticator app.
  Step 5: Super admin submits a code from the app to confirm setup.
  Step 6: Server sets totp_verified_at = NOW() on the super_admins row.
          From this point forward, every login requires a TOTP code.

  The QR code is generated server-side and sent ONCE. It is never stored
  in the database or in any persistent medium. After step 6, there is no
  way to retrieve the QR again-the super admin must keep a backup of the
  secret or their device.

RECOVERY (DOCUMENTED BY DESIGN):
  If the authenticator device is lost:
    UPDATE super_admins
    SET totp_secret = NULL, totp_verified_at = NULL
    WHERE email = 'affected@zealsync.dev';
  This restarts the TOTP setup flow on next login.
  Only Fred can perform this operation via direct DB access.
"""

import io
import base64

import pyotp
import qrcode

from app.core.security import encrypt_secret, decrypt_secret

# The issuer name shown in the authenticator app below the account name.
# "ZealSync" will appear as the app label; the user's email as the account.
_ISSUER_NAME = "ZealSync"


def generate_totp_secret() -> str:
    """
    Generates a cryptographically random Base32 TOTP secret.

    pyotp.random_base32() produces a 32-character Base32 string using
    os.urandom() as the entropy source. 32 characters = 160 bits of entropy,
    which is well above the RFC 4226 recommendation of ≥ 128 bits.

    Returns the raw (unencrypted) secret string. The caller is responsible
    for encrypting it before storing in the database. See encrypt_totp_secret().
    """
    return pyotp.random_base32()


def get_totp_uri(secret: str, email: str) -> str:
    """
    Returns the otpauth:// provisioning URI for the given secret and email.

    Format:
        otpauth://totp/ZealSync:email@example.com?secret=BASE32SECRET&issuer=ZealSync

    This URI is what the QR code encodes. Authenticator apps parse it to
    extract the secret, label (email), and issuer name. The QR encoding is
    done separately in generate_qr_code_base64().

    Args:
        secret: The raw (unencrypted) Base32 secret from generate_totp_secret().
        email:  The super admin's email address-used as the account label.
    """
    return pyotp.TOTP(secret).provisioning_uri(
        name=email,
        issuer_name=_ISSUER_NAME,
    )


def generate_qr_code_base64(secret: str, email: str) -> str:
    """
    Generates a QR code PNG for the TOTP provisioning URI and returns it
    as a base64-encoded data URI ready for embedding in an <img> tag:
        data:image/png;base64,iVBORw0K...

    The QR code is generated entirely in memory-no file is written to disk.
    This function should be called ONCE per setup flow. After the super admin
    scans the code and verifies a valid TOTP, this function must not be called
    again for the same account. The setup endpoint enforces this by checking
    that totp_verified_at IS NULL before proceeding.

    Args:
        secret: The raw (unencrypted) Base32 secret.
        email:  The super admin's email address for the QR label.

    Returns:
        A data URI string: "data:image/png;base64,..."
    """
    uri = get_totp_uri(secret, email)

    # qrcode.make() returns a PIL Image. We use error correction level L
    # (lowest, ~7% data recovery) because QR codes for authenticator apps
    # are scanned in controlled environments-high error correction just
    # makes the code denser and harder to scan on small phone screens.
    img = qrcode.make(uri)

    # Serialize the PIL image to PNG bytes in memory.
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    encoded = base64.b64encode(buffer.read()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def verify_totp_code(secret: str, code: str) -> bool:
    """
    Verifies a 6-digit TOTP code against the given secret.

    Args:
        secret: The raw (unencrypted) Base32 secret.
        code:   The 6-digit code from the authenticator app.

    Returns:
        True if the code is valid, False otherwise.
        NEVER raises-all exceptions are caught and return False.
        This prevents timing side channels from exception handling paths.

    CLOCK DRIFT:
        valid_window=1 means pyotp accepts codes from:
          - The PREVIOUS 30-second window (code was valid 30 seconds ago)
          - The CURRENT 30-second window  (the normal case)
          - The NEXT 30-second window     (the phone's clock is slightly ahead)
        This ±30-second tolerance handles minor clock drift between the server
        and the user's phone without meaningfully reducing security.
        A valid_window > 1 is NOT used here-that would expand the attack
        window too much for an operator-level account.
    """
    try:
        return pyotp.TOTP(secret).verify(code, valid_window=1)
    except Exception:
        # Any malformed input (wrong length, non-numeric, etc.) returns False.
        return False


def encrypt_totp_secret(raw_secret: str) -> str:
    """
    Encrypts a raw TOTP secret with Fernet before database storage.

    Delegates to app.core.security.encrypt_secret() which uses the
    FERNET_SECRET_KEY from settings. The same key that protects router
    passwords also protects TOTP secrets-one key to manage, one
    rotation procedure to document.

    Args:
        raw_secret: The Base32 string from generate_totp_secret().

    Returns:
        A Fernet ciphertext string safe to store in TEXT columns.
    """
    return encrypt_secret(raw_secret)


def decrypt_totp_secret(encrypted_secret: str) -> str:
    """
    Decrypts a Fernet-encrypted TOTP secret back to the raw Base32 string.

    Call this ONLY at TOTP verification time-never log or cache the
    decrypted value. The plaintext secret exists in memory only during the
    single verify_totp_code() call.

    Args:
        encrypted_secret: The Fernet ciphertext from the database.

    Raises:
        ValueError: If the ciphertext has been tampered with or if the
                    FERNET_SECRET_KEY has changed since encryption.
                    The caller must handle this as an internal error (500),
                    not an authentication failure (401), since it indicates
                    a configuration or data integrity problem.
    """
    try:
        return decrypt_secret(encrypted_secret)
    except Exception as exc:
        raise ValueError(
            "Failed to decrypt TOTP secret. "
            "This may indicate key rotation without re-encryption or data corruption."
        ) from exc
