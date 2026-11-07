"""Login, refresh-token rotation, logout and password change.

Refresh tokens are random opaque strings. The browser holds them in an HttpOnly cookie; the
database holds only their SHA-256, so a leaked database cannot be replayed as cookies.
"""
import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import config
from app.errors import TooManyRequests, Unauthorized, Unprocessable
from app.models import RefreshToken, User, utcnow
from app.security import (
    burn_password_check, create_access_token, hash_password, validate_new_password, verify_password,
)
from app.services.throttle import login_throttle

INVALID_CREDENTIALS = "Incorrect email or password."


@dataclass
class IssuedSession:
    user: User
    access_token: str
    refresh_token: str | None  # None = keep the cookie the browser already has (grace-window replay)


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _new_refresh_token(db: Session, user: User, family_id: str) -> tuple[RefreshToken, str]:
    raw = secrets.token_urlsafe(48)
    row = RefreshToken(
        user_id=user.id, token_hash=_hash(raw), family_id=family_id,
        expires_at=utcnow() + timedelta(days=config.REFRESH_TOKEN_DAYS),
    )
    db.add(row)
    db.flush()
    return row, raw


def start_session(db: Session, user: User) -> IssuedSession:
    """A new login: a new token family."""
    _, raw = _new_refresh_token(db, user, uuid.uuid4().hex)
    db.commit()
    return IssuedSession(user, create_access_token(user), raw)


def login(db: Session, email: str, password: str, ip: str) -> IssuedSession:
    email = normalize_email(email)
    wait = login_throttle.retry_after(email, ip)
    if wait:
        raise TooManyRequests(
            "Too many failed sign-in attempts. Please wait a few minutes and try again.",
            headers={"Retry-After": str(wait)},
        )
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not user.password_hash:
        burn_password_check(password)  # same work as a real check, so timing doesn't reveal the email
        ok = False
    else:
        ok = verify_password(password, user.password_hash)
    if not ok or not user.is_active:
        login_throttle.record_failure(email, ip)
        # One message for unknown email, wrong password and deactivated account.
        raise Unauthorized(INVALID_CREDENTIALS, code="INVALID_CREDENTIALS")
    login_throttle.record_success(email, ip)
    return start_session(db, user)


def _revoke_family(db: Session, family_id: str) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


def _session_ended() -> Unauthorized:
    return Unauthorized("Your session has ended. Please log in again.", code="INVALID_REFRESH_TOKEN")


def refresh(db: Session, raw: str | None) -> IssuedSession:
    """Swap a refresh token for a new access token and a new (rotated) refresh token."""
    if not raw:
        raise _session_ended()
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _hash(raw)))
    if token is None:
        raise _session_ended()
    now = utcnow()
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        _revoke_family(db, token.family_id)
        db.commit()
        raise _session_ended()

    if token.revoked_at is None:
        if token.expires_at <= now:
            raise _session_ended()
        # Claim this token with a conditional UPDATE, so two concurrent refreshes can't both
        # rotate it (same idea as the claims' version check).
        claimed = db.execute(
            update(RefreshToken)
            .where(RefreshToken.id == token.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
            .execution_options(synchronize_session=False)
        ).rowcount == 1
        if claimed:
            successor, new_raw = _new_refresh_token(db, user, token.family_id)
            db.execute(update(RefreshToken).where(RefreshToken.id == token.id)
                       .values(replaced_by=successor.id))
            db.commit()
            return IssuedSession(user, create_access_token(user), new_raw)
        db.rollback()
        db.refresh(token)  # lost the race: fall through to the "already rotated" handling

    # The token was already used. Either a harmless race, or someone replaying a stolen token.
    rotated_recently = (
        token.replaced_by is not None
        and token.revoked_at is not None
        and now - token.revoked_at <= timedelta(seconds=config.REFRESH_REUSE_GRACE_SECONDS)
    )
    if rotated_recently and _family_alive(db, token.family_id, now):
        # Two tabs (or StrictMode's double effect) refreshed at the same moment. The other
        # request already set the new cookie, so hand out an access token and leave the cookie.
        return IssuedSession(user, create_access_token(user), None)
    if token.replaced_by is not None:
        _revoke_family(db, token.family_id)  # reuse detected: end this login everywhere
        db.commit()
        raise Unauthorized("This session was ended for your security. Please log in again.",
                           code="REFRESH_TOKEN_REUSED")
    raise _session_ended()


def _family_alive(db: Session, family_id: str, now) -> bool:
    return db.scalar(
        select(RefreshToken.id).where(
            RefreshToken.family_id == family_id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        ).limit(1)
    ) is not None


def logout(db: Session, raw: str | None) -> None:
    """Revoke the whole family of the presented token. Always succeeds (idempotent)."""
    if not raw:
        return
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _hash(raw)))
    if token is not None:
        _revoke_family(db, token.family_id)
        db.commit()


def revoke_all_for_user(db: Session, user_id: int) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


def change_password(db: Session, user: User, current: str, new: str, ip: str) -> IssuedSession:
    """Change the password, sign out every device, and start a fresh session for this one."""
    wait = login_throttle.retry_after(user.email, ip)
    if wait:
        raise TooManyRequests("Too many failed attempts. Please wait a few minutes and try again.",
                              headers={"Retry-After": str(wait)})
    if not user.password_hash or not verify_password(current, user.password_hash):
        login_throttle.record_failure(user.email, ip)
        raise Unprocessable("Please fix the highlighted fields.",
                            fields={"current_password": "Current password is incorrect."})
    validate_new_password(new, "new_password")
    if new == current:
        raise Unprocessable("Please fix the highlighted fields.",
                            fields={"new_password": "New password must be different from the current one."})
    user.password_hash = hash_password(new)
    revoke_all_for_user(db, user.id)
    db.commit()
    return start_session(db, user)
