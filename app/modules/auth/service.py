"""
app/modules/auth/service.py
============================
Business logic for registration and login.

The service layer sits between the router (HTTP) and the database (SQL).
It knows about domain rules like "email must be unique" but it does NOT
know about HTTP status codes or FastAPI request/response objects.

Why separate layers?
If you later need to trigger registration from a CLI script, a webhook,
or a background job, you call the service function directly — no HTTP
involved. The router is just a thin adapter that calls the service.

asyncpg parameterised queries:
  All SQL in this file uses $1, $2, ... placeholders.
  asyncpg sends the query and parameters SEPARATELY to PostgreSQL over
  the wire — PostgreSQL never concatenates them into a SQL string, so
  SQL injection is structurally impossible.

  This is DIFFERENT from Python's f-strings or % formatting:
    BAD:  f"SELECT * FROM users WHERE email = '{email}'"
          (SQL injection: if email = "' OR 1=1 --", you're done)
    GOOD: "SELECT * FROM users WHERE email = $1", email
          (PostgreSQL receives two separate packets, never joins them)
"""

import asyncpg

from app.core.exceptions import ConflictException, UnauthorisedException
from app.core.security import hash_password, verify_password, create_access_token
from app.modules.auth.schemas import RegisterRequest


async def register_user(conn: asyncpg.Connection, data: RegisterRequest) -> dict:
    """
    Registers a new user.

    Steps:
      1. Check if email or phone is already in the database.
         We check both before hashing the password because bcrypt is
         intentionally slow (100ms+). Failing fast on a conflict saves time.
      2. Hash the password with bcrypt.
      3. INSERT the user row.
      4. Return the full user row so the router can build a token response.

    Why check email AND phone separately instead of relying on the DB
    UNIQUE constraint?
    The DB constraint is the last line of defence. If we let it fail, we get
    a generic asyncpg.UniqueViolationError with a technical message. By
    checking first, we can return a descriptive error: "email already in use"
    vs "phone already in use" — much better UX.
    """

    # ── Check for existing email ───────────────────────────────────────────────
    existing = await conn.fetchrow(
        "SELECT id, email, phone FROM users WHERE email = $1 OR phone = $2",
        data.email,
        data.phone,
    )

    if existing:
        # Tell the client WHICH field conflicts so they can correct it.
        if existing["email"] == data.email:
            raise ConflictException("An account with this email address already exists.")
        else:
            raise ConflictException("An account with this phone number already exists.")

    # ── Hash the password ──────────────────────────────────────────────────────
    # hash_password() calls bcrypt.hashpw() — this takes ~100ms intentionally.
    # bcrypt's slowness is a feature: it makes brute-force attacks 100x slower.
    # Never store plain passwords. Never use MD5 or SHA-256 for passwords.
    hashed = hash_password(data.password)

    # ── Insert the user ────────────────────────────────────────────────────────
    # RETURNING * gives us back the full row including the UUID that PostgreSQL
    # generated — we need the id to create the JWT token.
    user = await conn.fetchrow(
        """
        INSERT INTO users (email, phone, hashed_password, role)
        VALUES ($1, $2, $3, $4)
        RETURNING id, email, phone, role, reseller_id, is_active, created_at
        """,
        data.email,
        data.phone,
        hashed,
        data.role,
    )

    # asyncpg returns a Record object. We convert it to a plain dict so the
    # calling code doesn't need to know about asyncpg internals.
    return dict(user)


async def authenticate_user(
    conn: asyncpg.Connection,
    email: str,
    password: str,
) -> dict:
    """
    Validates credentials and returns the user row.

    Timing attack note:
    If the user doesn't exist, we still call verify_password() against a
    dummy hash. This keeps the response time consistent whether the email
    exists or not — an attacker timing responses can't enumerate valid emails.

    Without this, a non-existent email returns in 0ms (short-circuit) while
    a wrong password for a real email returns in ~100ms (bcrypt). The timing
    difference leaks which emails are registered.
    """

    user = await conn.fetchrow(
        """
        SELECT id, email, phone, role, reseller_id, hashed_password, is_active
        FROM users
        WHERE email = $1
        """,
        email,
    )

    # ── Timing-safe failure path ───────────────────────────────────────────────
    # We always run bcrypt even if the user doesn't exist, using a dummy hash.
    # This prevents email enumeration via timing analysis.
    DUMMY_HASH = "$2b$12$KIXy0z5h5l5z5z5z5z5z5e1234567890123456789012345678901234"

    stored_hash = user["hashed_password"] if user else DUMMY_HASH
    password_ok = verify_password(password, stored_hash)

    if not user or not password_ok:
        # We use the same error message for both "user not found" and "wrong
        # password". Telling the client "user not found" would let an attacker
        # confirm which emails are registered (user enumeration attack).
        raise UnauthorisedException("Invalid email or password.")

    if not user["is_active"]:
        raise UnauthorisedException("This account has been deactivated. Contact support.")

    return dict(user)
