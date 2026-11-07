"""Read-side queries: filtered/paginated lists, dashboard summary, CSV export."""
import csv
import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app import config
from app.errors import Unprocessable
from app.models import (
    APPROVED, APPROVER, DRAFT, PAID, REJECTED, STATUSES, SUBMITTED, Claim, User,
)

SORTABLE = {
    "created_at": Claim.created_at, "updated_at": Claim.updated_at, "amount": Claim.amount,
    "expense_date": Claim.expense_date, "submitted_at": Claim.submitted_at,
}
SCOPES = {"pending": (SUBMITTED,), "reviewed": (APPROVED, REJECTED, PAID)}
EXPORT_LIMIT = 5000


@dataclass
class Filters:
    status: str | None = None
    category: str | None = None
    q: str | None = None
    scope: str | None = None        # approvers: "pending" | "reviewed"
    employee_id: int | None = None  # approvers only
    date_from: date | None = None
    date_to: date | None = None
    sort_by: str | None = None
    order: str = "desc"
    page: int = 1
    page_size: int = 20

    def validate(self) -> "Filters":
        errors = {}
        if self.status and self.status not in STATUSES:
            errors["status"] = f"Must be one of: {', '.join(STATUSES)}"
        if self.scope and self.scope not in SCOPES:
            errors["scope"] = "Must be 'pending' or 'reviewed'"
        if self.sort_by and self.sort_by not in SORTABLE:
            errors["sort_by"] = f"Must be one of: {', '.join(SORTABLE)}"
        if self.order not in ("asc", "desc"):
            errors["order"] = "Must be 'asc' or 'desc'"
        if self.date_from and self.date_to and self.date_from > self.date_to:
            errors["date_from"] = "date_from must be on or before date_to"
        if errors:
            raise Unprocessable("Invalid filters.", fields=errors)
        return self


def _visible_claims(user: User) -> Select:
    """Employees see their own claims; approvers see everything except private drafts."""
    stmt = select(Claim).where(Claim.deleted_at.is_(None))
    if user.role == APPROVER:
        return stmt.where(Claim.status != DRAFT)
    return stmt.where(Claim.employee_id == user.id)


def _apply_filters(stmt: Select, user: User, f: Filters) -> Select:
    if f.scope:
        stmt = stmt.where(Claim.status.in_(SCOPES[f.scope]))
    if f.status:
        stmt = stmt.where(Claim.status == f.status)
    if f.category:
        stmt = stmt.where(Claim.category == f.category)
    if f.employee_id and user.role == APPROVER:
        stmt = stmt.where(Claim.employee_id == f.employee_id)
    if f.date_from:
        stmt = stmt.where(Claim.expense_date >= f.date_from)
    if f.date_to:
        stmt = stmt.where(Claim.expense_date <= f.date_to)
    if f.q:
        conds = [
            Claim.title.icontains(f.q, autoescape=True),
            Claim.description.icontains(f.q, autoescape=True),
            Claim.employee.has(User.name.icontains(f.q, autoescape=True)),
        ]
        if f.q.isdigit():
            conds.append(Claim.id == int(f.q))
        stmt = stmt.where(or_(*conds))
    return stmt


def _ordered(stmt: Select, f: Filters) -> Select:
    if f.sort_by:
        col, desc = SORTABLE[f.sort_by], f.order == "desc"
    elif f.scope == "pending":
        col, desc = Claim.submitted_at, False  # oldest waiting first
    else:
        col, desc = Claim.updated_at, True
    return stmt.order_by(col.desc() if desc else col.asc(), Claim.id.desc())


def list_claims(db: Session, user: User, f: Filters) -> tuple[list[Claim], int]:
    f.validate()
    base = _apply_filters(_visible_claims(user), user, f)
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    stmt = (
        _ordered(base, f)
        .options(joinedload(Claim.employee), joinedload(Claim.reviewer))
        .offset((f.page - 1) * f.page_size)
        .limit(f.page_size)
    )
    return list(db.scalars(stmt).unique()), total


def summary(db: Session, user: User) -> dict:
    """Totals are added up in Python with Decimal (no float drift from SQL SUM)."""
    rows = db.execute(
        _visible_claims(user).with_only_columns(Claim.status, Claim.amount, Claim.approved_amount)
    ).all()
    counts = {s: 0 for s in STATUSES}
    zero = Decimal("0.00")
    total_claimed = pending = approved = paid = zero
    for status, amount, approved_amount in rows:
        counts[status] += 1
        if status != DRAFT:
            total_claimed += amount
        if status == SUBMITTED:
            pending += amount
        if status in (APPROVED, PAID):
            approved += approved_amount or zero
        if status == PAID:
            paid += approved_amount or zero
    return {
        "currency": config.DEFAULT_CURRENCY, "counts": counts, "total_claimed": total_claimed,
        "pending_amount": pending, "approved_amount": approved, "paid_amount": paid,
    }


def _csv_safe(value) -> str:
    """Stop spreadsheet formula injection (cells starting with = + - @)."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


def export_csv(db: Session, user: User, f: Filters) -> str:
    f.validate()
    stmt = (
        _ordered(_apply_filters(_visible_claims(user), user, f), f)
        .options(joinedload(Claim.employee), joinedload(Claim.reviewer))
        .limit(EXPORT_LIMIT)
    )
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["ID", "Employee", "Title", "Category", "Expense date", "Claimed", "Approved",
                "Currency", "Status", "Submitted at", "Reviewed at", "Reviewer",
                "Review comment", "Paid at", "Payment reference"])
    for c in db.scalars(stmt).unique():
        w.writerow([_csv_safe(v) for v in (
            c.id, c.employee.name, c.title, c.category, c.expense_date, c.amount, c.approved_amount,
            c.currency, c.status, c.submitted_at, c.reviewed_at, c.reviewer.name if c.reviewer else "",
            c.review_comment, c.paid_at, c.payment_reference)])
    return out.getvalue()