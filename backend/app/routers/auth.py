from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy.orm import Session

from app import config
from app.database import get_db
from app.errors import ApiError
from app.models import User
from app.schemas import ChangePasswordIn, LoginIn, TokenOut, UserOut
from app.security import client_ip, current_user, require_csrf_header
from app.serializers import user_out
from app.services import auth as auth_svc

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_refresh_cookie(response: Response, raw: str) -> None:
    response.set_cookie(
        config.REFRESH_COOKIE_NAME, raw,
        max_age=config.REFRESH_TOKEN_DAYS * 24 * 3600,
        path=config.REFRESH_COOKIE_PATH,  # only sent to /api/auth/*, never to the claims API
        httponly=True,                    # JavaScript cannot read it
        samesite="lax",
        secure=config.COOKIE_SECURE,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(config.REFRESH_COOKIE_NAME, path=config.REFRESH_COOKIE_PATH,
                           httponly=True, samesite="lax", secure=config.COOKIE_SECURE)


def _token_body(session: auth_svc.IssuedSession) -> dict:
    return {"access_token": session.access_token, "token_type": "bearer",
            "expires_in": config.ACCESS_TOKEN_MINUTES * 60, "user": user_out(session.user, full=True)}


def _respond(response: Response, session: auth_svc.IssuedSession) -> dict:
    if session.refresh_token is not None:
        _set_refresh_cookie(response, session.refresh_token)
    response.headers["Cache-Control"] = "no-store"
    return _token_body(session)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    return _respond(response, auth_svc.login(db, body.email, body.password, client_ip(request)))


@router.post("/refresh", response_model=TokenOut, dependencies=[Depends(require_csrf_header)])
def refresh(response: Response, db: Session = Depends(get_db),
            refresh_token: str | None = Cookie(default=None, alias=config.REFRESH_COOKIE_NAME)):
    try:
        session = auth_svc.refresh(db, refresh_token)
    except ApiError as err:
        # The cookie is useless now; tell the browser to drop it.
        err.headers.setdefault("Set-Cookie", _expired_cookie_header())
        raise
    return _respond(response, session)


def _expired_cookie_header() -> str:
    tmp = Response()
    _clear_refresh_cookie(tmp)
    return tmp.headers["set-cookie"]


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf_header)])
def logout(response: Response, db: Session = Depends(get_db),
           refresh_token: str | None = Cookie(default=None, alias=config.REFRESH_COOKIE_NAME)):
    """Works without a valid access token, so an expired session can still sign out."""
    auth_svc.logout(db, refresh_token)
    _clear_refresh_cookie(response)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user_out(user, full=True)


@router.post("/change-password", response_model=TokenOut)
def change_password(body: ChangePasswordIn, request: Request, response: Response,
                    user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Signs out every other device (all refresh tokens revoked) and starts a new session here."""
    session = auth_svc.change_password(db, user, body.current_password, body.new_password,
                                       client_ip(request))
    return _respond(response, session)
