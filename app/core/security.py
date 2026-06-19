from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from cryptography.fernet import Fernet
from jose import JWTError, jwt

from app.config import settings


# ── Password hashing ──────────────────────────────────────────────────────────

def hash_password(plain_password: str) -> str:
    """Returns a bcrypt hash of the given password."""
    return bcrypt.hashpw(
        plain_password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Returns True if the password matches the stored hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )


# ── JWT tokens ────────────────────────────────────────────────────────────────

def create_access_token(
    user_id: str,
    role: str,
    tenant_id: str,
    reseller_id: Optional[str] = None,
) -> str:
    """
    Creates a signed JWT access token.

    Payload:
        sub         -user UUID
        role        -admin | reseller | customer
        tenant_id   -UUID of the tenant this user belongs to.
                      Every subsequent request uses this to scope database
                      queries. By embedding it in the token we avoid a
                      database lookup on every request just to find tenant_id.
        reseller_id -UUID of the parent reseller (customers only), or None
        exp         -expiry timestamp
        iat         -issued-at timestamp
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": user_id,
        "role": role,
        "tenant_id": tenant_id,      # NEW: injected into every token
        "reseller_id": reseller_id,
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict | None:
    """
    Decodes a JWT access token.
    Returns the payload dict, or None if the token is invalid or expired.
    """
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError:
        return None


# ── Phone Number Normalisation ────────────────────────────────────────────────

def normalise_phone(phone: str) -> str:
    """
    Normalises Kenyan phone numbers to the Safaricom Daraja format: 2547XXXXXXXX or 2541XXXXXXXX.

    Accepts formats:
      - 0712345678 or 0112345678
      - +254712345678 or +25412345678
      - 254712345678 or 25412345678

    Raises:
        ValueError: If the number does not match a valid Kenyan mobile format.
    """
    # Remove leading '+', spaces, or dashes
    cleaned = phone.strip().replace("+", "").replace(" ", "").replace("-", "")

    if not cleaned.isdigit():
        raise ValueError("Phone number must contain digits only.")

    # Format: 07XXXXXXXX or 01XXXXXXXX (10 digits)
    if cleaned.startswith("0") and len(cleaned) == 10:
        # Check if the next character is 7 or 1 (standard Kenyan prefixes)
        if cleaned[1] in ("7", "1"):
            return f"254{cleaned[1:]}"

    # Format: 2547XXXXXXXX or 2541XXXXXXXX (12 digits)
    if cleaned.startswith("254") and len(cleaned) == 12:
        if cleaned[3] in ("7", "1"):
            return cleaned

    # Format: 7XXXXXXXX or 1XXXXXXXX (9 digits)
    if len(cleaned) == 9 and cleaned[0] in ("7", "1"):
        return f"254{cleaned}"

    raise ValueError(
        f"Invalid Kenyan phone number: '{phone}'. Must be a valid 07... or 01... number."
    )


# ── Symmetric encryption for router credentials (Phase 2) ────────────────────
# Router passwords must not sit in plaintext in the database. We use Fernet
# (AES-128-CBC + HMAC-SHA256) with a key read from settings at startup.
#
# WHY FERNET AND NOT bcrypt?
#   bcrypt is a one-way hash -you can never recover the original value.
#   Router passwords must be decrypted at the moment of use so we can pass
#   them to MikroTik's REST API. Fernet is a symmetric cipher: encrypt at
#   write time, decrypt only when the plaintext is needed for the API call.
#
# KEY MANAGEMENT:
#   The key is a URL-safe base64-encoded 32-byte secret stored in
#   settings.FERNET_SECRET_KEY. It must NEVER be committed to git.
#   In production it is injected via Docker secrets or the hosting platform's
#   secret manager. See Phase 8 for the docker-compose.yml changes.
#
# IMPORTANT: if the key changes, all previously encrypted values become
#   undecryptable. Key rotation requires decrypting all records with the old
#   key and re-encrypting with the new one in a coordinated migration.

def _get_fernet() -> Fernet:
    """
    Returns a Fernet cipher initialised with the configured secret key.
    Called at the moment of use rather than at import time so that the
    key can be loaded from environment variables (not committed constants).
    """
    key = settings.FERNET_SECRET_KEY
    if not key:
        raise RuntimeError(
            "FERNET_SECRET_KEY is not set. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secret(plaintext: str) -> str:
    """
    Encrypts a plaintext string and returns a URL-safe base64 ciphertext.
    Use this when storing router passwords in the database.
    """
    f = _get_fernet()
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    """
    Decrypts a Fernet-encrypted ciphertext back to plaintext.
    Call this only at the moment of use (e.g., inside get_mikrotik_client).
    Never log or return the decrypted value.
    """
    f = _get_fernet()
    return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")