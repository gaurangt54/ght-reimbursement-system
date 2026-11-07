from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import UserOut
from app.security import require_approver
from app.serializers import user_out

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut], dependencies=[Depends(require_approver)])
def list_users(role: Literal["employee", "approver"] | None = None, db: Session = Depends(get_db)):
    """Approver-only (powers the employee filter on the reviewed-claims screen)."""
    stmt = select(User).where(User.is_active.is_(True)).order_by(User.name)
    if role:
        stmt = stmt.where(User.role == role)
    return [user_out(u, full=True) for u in db.scalars(stmt)]
