from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import Forbidden
from app.models import APPROVER, User
from app.schemas import (
    ActionIn, ApproveIn, ClaimDetailOut, ClaimIn, ClaimListOut, ClaimOut, PayIn, RejectIn, SummaryOut,
)
from app.security import current_user
from app.serializers import claim_detail_out, claim_out
from app.services import claims as svc
from app.services import queries

router = APIRouter(prefix="/api/claims", tags=["claims"])


def filters(
    status: str | None = None,
    category: str | None = None,
    q: str | None = Query(default=None, max_length=100),
    scope: str | None = None,
    employee_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort_by: str | None = None,
    order: str = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> queries.Filters:
    return queries.Filters(
        status=status, category=category, q=(q or "").strip() or None, scope=scope,
        employee_id=employee_id, date_from=date_from, date_to=date_to,
        sort_by=sort_by, order=order, page=page, page_size=page_size,
    )


# NOTE: fixed paths (/summary, /export.csv) must be declared before /{claim_id}.

@router.get("", response_model=ClaimListOut)
def list_claims(f: queries.Filters = Depends(filters), user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    items, total = queries.list_claims(db, user, f)
    return {"items": [claim_out(c, user) for c in items], "total": total,
            "page": f.page, "page_size": f.page_size}


@router.get("/summary", response_model=SummaryOut)
def get_summary(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return queries.summary(db, user)


@router.get("/export.csv")
def export_csv(f: queries.Filters = Depends(filters), user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    if user.role != APPROVER:
        raise Forbidden("Only approvers can export claims.")
    return Response(
        queries.export_csv(db, user, f), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="claims.csv"'},
    )


@router.post("", response_model=ClaimDetailOut, status_code=201)
def create_claim(body: ClaimIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return claim_detail_out(svc.create_claim(db, user, body), user)


@router.get("/{claim_id}", response_model=ClaimDetailOut)
def get_claim(claim_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return claim_detail_out(svc.get_claim(db, user, claim_id), user)


@router.put("/{claim_id}", response_model=ClaimDetailOut)
def update_claim(claim_id: int, body: ClaimIn, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    return claim_detail_out(svc.update_claim(db, user, claim_id, body), user)


@router.delete("/{claim_id}", status_code=204)
def delete_claim(claim_id: int, expected_version: int | None = None,
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    svc.delete_claim(db, user, claim_id, expected_version)


@router.post("/{claim_id}/submit", response_model=ClaimDetailOut)
def submit_claim(claim_id: int, body: ActionIn | None = None, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    claim = svc.submit_claim(db, user, claim_id, body.expected_version if body else None)
    return claim_detail_out(claim, user)


@router.post("/{claim_id}/withdraw", response_model=ClaimDetailOut)
def withdraw_claim(claim_id: int, body: ActionIn | None = None, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    claim = svc.withdraw_claim(db, user, claim_id, body.expected_version if body else None)
    return claim_detail_out(claim, user)


@router.post("/{claim_id}/approve", response_model=ClaimDetailOut)
def approve_claim(claim_id: int, body: ApproveIn | None = None, user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    return claim_detail_out(svc.approve_claim(db, user, claim_id, body or ApproveIn()), user)


@router.post("/{claim_id}/reject", response_model=ClaimDetailOut)
def reject_claim(claim_id: int, body: RejectIn, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    return claim_detail_out(svc.reject_claim(db, user, claim_id, body), user)


@router.post("/{claim_id}/pay", response_model=ClaimDetailOut)
def pay_claim(claim_id: int, body: PayIn | None = None, user: User = Depends(current_user),
              db: Session = Depends(get_db)):
    return claim_detail_out(svc.pay_claim(db, user, claim_id, body or PayIn()), user)