from datetime import datetime, timedelta, timezone

import bcrypt
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
    reseller_id: str | None = None,
) -> str:
    """
    Creates a signed JWT access token.

    Payload:
        sub         — user UUID
        role        — admin | reseller | customer
        reseller_id — UUID of the parent reseller (customers only), or None
        exp         — expiry timestamp
        iat         — issued-at timestamp
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": user_id,
        "role": role,
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