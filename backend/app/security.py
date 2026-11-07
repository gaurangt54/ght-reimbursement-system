"""Passwords, access tokens (JWT) and the "who is calling?" dependency.

- Passwords are hashed with bcrypt (the `bcrypt` package directly; passlib is not used).
- Access tokens are short-lived HS256 JWTs with claims sub, iat, exp, jti, type.
  They are decoded with the algorithm pinned, so `alg: none` and algorithm-swap tokens fail.
- The token only says *who* is calling. Role and active status are read from the database
  on every request, so a role change or deactivation applies immediately.
"""
import uuid
from datetime import timedelta

import bcrypt
import jwt
from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app import config
from app.database import get_db
from app.errors import Forbidden, Unauthorized, Unprocessable
from app.models import APPROVER, User, utcnow

# ---------- passwords ----------

def password_problem(password: str) -> str | None:
    """Return why a new password is not acceptable, or None if it is fine."""
    if len(password) < config.PASSWORD_MIN_LENGTH:
        return f"Password must be at least {config.PASSWORD_MIN_LENGTH} characters."
    if len(password.encode("utf-8")) > config.PASSWORD_MAX_BYTES:
        # bcrypt ignores everything after 72 bytes; refuse rather than silently truncate.
        return f"Password must be at most {config.PASSWORD_MAX_BYTES} bytes."
    if not password.strip():
        return "Password cannot be only spaces."
    return None


def validate_new_password(password: str, field: str = "password") -> None:
    problem = password_problem(password)
    if problem:
        raise Unprocessable("Please fix the highlighted fields.", fields={field: problem})


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"),
                         bcrypt.gensalt(rounds=config.BCRYPT_ROUNDS)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    data = password.encode("utf-8")
    if len(data) > config.PASSWORD_MAX_BYTES:  # bcrypt 5 raises on >72 bytes; such a password can't match
        data = data[: config.PASSWORD_MAX_BYTES]
        bcrypt.checkpw(data, password_hash.encode("ascii"))  # keep the timing the same
        return False
    try:
        return bcrypt.checkpw(data, password_hash.encode("ascii"))
    except ValueError:  # malformed hash in the database
        return False


# Used when the email is unknown, so "no such user" takes as long as "wrong password".
_DUMMY_HASH: str | None = None


def burn_password_check(password: str) -> None:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password("dummy-password-for-timing")
    verify_password(password, _DUMMY_HASH)


# ---------- access tokens ----------

def create_access_token(user: User) -> str:
    now = utcnow()
    claims = {
        "sub": str(user.id),
        "iat": now,
        "exp": now + timedelta(minutes=config.ACCESS_TOKEN_MINUTES),
        "jti": uuid.uuid4().hex,
        "type": "access",
    }
    return jwt.encode(claims, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_access_token(token: str) -> int:
    """Return the user id in a valid access token, else raise Unauthorized."""
    try:
        claims = jwt.decode(
            token, config.JWT_SECRET,
            algorithms=[config.JWT_ALGORITHM],  # pinned: never trust the token's own "alg"
            options={"require": ["sub", "iat", "exp", "jti"]},
        )
    except jwt.ExpiredSignatureError:
        raise Unauthorized("Your session has expired.", code="TOKEN_EXPIRED")
    except jwt.PyJWTError:
        raise Unauthorized("Invalid access token.", code="INVALID_TOKEN")
    if claims.get("type") != "access":
        raise Unauthorized("Invalid access token.", code="INVALID_TOKEN")
    try:
        return int(claims["sub"])
    except (TypeError, ValueError):
        raise Unauthorized("Invalid access token.", code="INVALID_TOKEN")


# ---------- request dependencies ----------

def current_user(authorization: str | None = Header(default=None),
                 db: Session = Depends(get_db)) -> User:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise Unauthorized("Please log in.")
    user = db.get(User, decode_access_token(token.strip()))
    if user is None or not user.is_active:
        raise Unauthorized("Your account is not active. Please log in again.", code="INVALID_TOKEN")
    return user


def require_approver(user: User = Depends(current_user)) -> User:
    if user.role != APPROVER:
        raise Forbidden("Only approvers can do this.")
    return user


def require_csrf_header(request: Request) -> None:
    """Cookie-authenticated endpoints (refresh, logout) need a custom header.

    A plain cross-site form or <img> cannot add custom headers, and a cross-origin fetch
    that does needs a CORS preflight, which only the configured frontend origin passes.
    """
    if not request.headers.get(config.CSRF_HEADER):
        raise Forbidden(f"Missing {config.CSRF_HEADER} header.", code="CSRF_CHECK_FAILED")


def client_ip(request: Request) -> str:
    # Not trusting X-Forwarded-For: there is no proxy in front of this app. Behind a proxy,
    # read the address the proxy sets instead.
    return request.client.host if request.client else "unknown"
