from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import NotFound
from app.models import AuthSession, User
from app.schemas import LoginIn, LoginOut, UserOut
from app.security import create_session, current_user
from app.serializers import user_out

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    """Public on purpose: powers the mocked 'pick a user' login screen."""
    return [user_out(u, full=True) for u in db.scalars(select(User).order_by(User.role, User.name))]


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.get(User, body.user_id)
    if user is None:
        raise NotFound("User not found.")
    return {"token": create_session(db, user), "user": user_out(user, full=True)}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user_out(user, full=True)


@router.post("/logout", status_code=204)
def logout(authorization: str = Header(default=""), user: User = Depends(current_user),
           db: Session = Depends(get_db)):
    session = db.get(AuthSession, authorization.partition(" ")[2])
    if session:
        db.delete(session)
        db.commit()