"""Mocked authentication: bearer token -> user. (No passwords, by design.)"""
import secrets
from datetime import timedelta

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app import config
from app.database import get_db
from app.errors import Unauthorized
from app.models import AuthSession, User, utcnow


def create_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(
        token=token, user_id=user.id,
        expires_at=utcnow() + timedelta(hours=config.SESSION_TTL_HOURS),
    ))
    db.commit()
    return token


def current_user(authorization: str | None = Header(default=None),
                 db: Session = Depends(get_db)) -> User:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise Unauthorized("Please log in.")
    session = db.get(AuthSession, token)
    if session is None or session.expires_at <= utcnow():
        raise Unauthorized("Your session has expired. Please log in again.")
    return session.user