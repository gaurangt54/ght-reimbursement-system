"""Claim use-cases: create, edit, delete, submit, withdraw, approve, reject, pay.

Every state change goes through `_apply`, which:
  1. checks the transition is legal,
  2. runs ONE conditional UPDATE (WHERE status and version still match) so concurrent
     actions cannot both win,
  3. writes a claim_events row in the same transaction.
"""
from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import config
from app.errors import Conflict, Forbidden, NotFound, Unprocessable
from app.models import (
    APPROVED, APPROVER, DRAFT, EMPLOYEE, PAID, REJECTED, SUBMITTED, Claim, ClaimEvent, User, utcnow,
)
from app.schemas import ApproveIn, ClaimIn, PayIn, RejectIn
from app.services import rules

_EDITABLE_FIELDS = ("title", "description", "category", "amount", "expense_date", "receipt_ref")


# ---------- helpers ----------

def get_claim(db: Session, user: User, claim_id: int) -> Claim:
    """Load a claim the user is allowed to see, else 404 (don't reveal it exists)."""
    claim = db.get(Claim, claim_id)
    if claim is None or claim.deleted_at is not None:
        raise NotFound("Claim not found.")
    if user.role == EMPLOYEE and claim.employee_id != user.id:
        raise NotFound("Claim not found.")
    if user.role == APPROVER and claim.status == DRAFT:
        raise NotFound("Claim not found.")  # drafts are private to the employee
    return claim


def _require_owner(user: User, claim: Claim, what: str) -> None:
    if user.role != EMPLOYEE or claim.employee_id != user.id:
        raise Forbidden(f"Only the employee who owns this claim can {what} it.")


def _require_reviewer(user: User, claim: Claim, what: str) -> None:
    if user.role != APPROVER:
        raise Forbidden(f"Only approvers can {what} claims.")
    if claim.employee_id == user.id:
        raise Forbidden("You cannot review your own claim.")


def _ensure_state(claim: Claim, allowed_from: set[str], verb: str) -> None:
    if claim.status not in allowed_from:
        raise Conflict(
            f"Cannot {verb} a claim that is {claim.status.lower()}.", code="INVALID_TRANSITION"
        )


def _apply(db: Session, claim: Claim, user: User, *, verb: str, allowed_from: set[str],
           values: dict, action: str, expected_version: int | None = None,
           comment: str | None = None, details: dict | None = None) -> Claim:
    """Atomically change a claim and record the event (see module docstring)."""
    _ensure_state(claim, allowed_from, verb)
    if expected_version is not None and expected_version != claim.version:
        raise Conflict(
            "This claim was changed by someone else. Refresh the page and try again.",
            code="STALE_VERSION",
        )
    from_status = claim.status
    try:
        result = db.execute(
            update(Claim)
            .where(
                Claim.id == claim.id,
                Claim.version == claim.version,
                Claim.status.in_(allowed_from),
                Claim.deleted_at.is_(None),
            )
            .values(**values, version=Claim.version + 1, updated_at=utcnow())
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:  # someone else changed it between our read and write
            db.rollback()
            raise Conflict(
                "This claim was just changed by someone else. Refresh the page and try again.",
                code="CONCURRENT_UPDATE",
            )
        db.add(ClaimEvent(
            claim_id=claim.id, user_id=user.id, action=action, from_status=from_status,
            to_status=values.get("status"), comment=comment, details=details,
        ))
        db.commit()
    except IntegrityError:  # the partial unique index on `fingerprint` fired
        db.rollback()
        raise Conflict(
            "You already have an active claim with the same category, amount, date and title.",
            code="DUPLICATE_CLAIM",
        )
    db.refresh(claim)
    return claim


def _raise_if_invalid(errors: dict[str, str]) -> None:
    if errors:
        raise Unprocessable("Please fix the highlighted fields.", fields=errors)


# ---------- employee actions ----------

def create_claim(db: Session, user: User, data: ClaimIn) -> Claim:
    if user.role != EMPLOYEE:
        raise Forbidden("Only employees can create claims.")
    _raise_if_invalid(rules.validate_policy(
        amount=data.amount, expense_date=data.expense_date,
        receipt_ref=data.receipt_ref, for_submit=False,
    ))
    claim = Claim(
        employee_id=user.id, title=data.title, description=data.description,
        category=data.category, amount=data.amount, currency=config.DEFAULT_CURRENCY,
        expense_date=data.expense_date, receipt_ref=data.receipt_ref, status=DRAFT,
        fingerprint=rules.make_fingerprint(
            config.DEFAULT_CURRENCY, data.category, data.amount, data.expense_date, data.title),
    )
    db.add(claim)
    db.flush()
    db.add(ClaimEvent(claim_id=claim.id, user_id=user.id, action="created", to_status=DRAFT))
    db.commit()
    db.refresh(claim)
    return claim


def update_claim(db: Session, user: User, claim_id: int, data: ClaimIn) -> Claim:
    claim = get_claim(db, user, claim_id)
    _require_owner(user, claim, "edit")
    _ensure_state(claim, rules.EDITABLE_STATUSES, "edit")
    _raise_if_invalid(rules.validate_policy(
        amount=data.amount, expense_date=data.expense_date,
        receipt_ref=data.receipt_ref, for_submit=False,
    ))
    new_values = {f: getattr(data, f) for f in _EDITABLE_FIELDS}
    changes = {f: [str(getattr(claim, f)), str(v)]
               for f, v in new_values.items() if getattr(claim, f) != v}
    if not changes:
        return claim  # nothing changed: no version bump, no history noise
    new_values["fingerprint"] = rules.make_fingerprint(
        claim.currency, data.category, data.amount, data.expense_date, data.title)
    return _apply(
        db, claim, user, verb="edit", allowed_from=rules.EDITABLE_STATUSES,
        values=new_values, action="edited", expected_version=data.expected_version,
        details=changes,
    )


def delete_claim(db: Session, user: User, claim_id: int, expected_version: int | None = None) -> None:
    claim = get_claim(db, user, claim_id)
    _require_owner(user, claim, "delete")
    _apply(
        db, claim, user, verb="delete", allowed_from=rules.DELETABLE_STATUSES,
        values={"deleted_at": utcnow()}, action="deleted", expected_version=expected_version,
    )


def submit_claim(db: Session, user: User, claim_id: int, expected_version: int | None = None) -> Claim:
    claim = get_claim(db, user, claim_id)
    _require_owner(user, claim, "submit")
    allowed_from, _ = rules.TRANSITIONS["submit"]
    _ensure_state(claim, allowed_from, "submit")
    # Re-check policy now: a draft may have aged past the date limit since it was saved.
    _raise_if_invalid(rules.validate_policy(
        amount=claim.amount, expense_date=claim.expense_date,
        receipt_ref=claim.receipt_ref, for_submit=True,
    ))
    resubmitting = claim.status == REJECTED
    values = {
        "status": SUBMITTED, "submitted_at": utcnow(),
        # clear the previous review; it stays in the history
        "approved_amount": None, "reviewer_id": None, "review_comment": None, "reviewed_at": None,
    }
    if resubmitting:
        values["resubmission_count"] = Claim.resubmission_count + 1
    return _apply(
        db, claim, user, verb="submit", allowed_from=allowed_from, values=values,
        action="resubmitted" if resubmitting else "submitted", expected_version=expected_version,
    )


def withdraw_claim(db: Session, user: User, claim_id: int, expected_version: int | None = None) -> Claim:
    claim = get_claim(db, user, claim_id)
    _require_owner(user, claim, "withdraw")
    allowed_from, _ = rules.TRANSITIONS["withdraw"]
    return _apply(
        db, claim, user, verb="withdraw", allowed_from=allowed_from,
        values={"status": DRAFT, "submitted_at": None}, action="withdrawn",
        expected_version=expected_version,
    )


# ---------- approver actions ----------

def approve_claim(db: Session, user: User, claim_id: int, data: ApproveIn) -> Claim:
    claim = get_claim(db, user, claim_id)
    _require_reviewer(user, claim, "approve")
    allowed_from, _ = rules.TRANSITIONS["approve"]
    _ensure_state(claim, allowed_from, "approve")

    approved: Decimal = data.approved_amount if data.approved_amount is not None else claim.amount
    if approved > claim.amount:
        raise Unprocessable("Please fix the highlighted fields.", fields={
            "approved_amount": f"Approved amount cannot exceed the claimed amount ({claim.amount:,.2f})."})
    partial = approved < claim.amount
    if partial and not data.comment:
        raise Unprocessable("Please fix the highlighted fields.", fields={
            "comment": "A comment explaining the reduction is required for a partial approval."})

    return _apply(
        db, claim, user, verb="approve", allowed_from=allowed_from,
        values={"status": APPROVED, "approved_amount": approved, "reviewer_id": user.id,
                "review_comment": data.comment, "reviewed_at": utcnow()},
        action="partially_approved" if partial else "approved",
        expected_version=data.expected_version, comment=data.comment,
        details={"claimed": str(claim.amount), "approved": str(approved)},
    )


def reject_claim(db: Session, user: User, claim_id: int, data: RejectIn) -> Claim:
    claim = get_claim(db, user, claim_id)
    _require_reviewer(user, claim, "reject")
    allowed_from, _ = rules.TRANSITIONS["reject"]
    return _apply(
        db, claim, user, verb="reject", allowed_from=allowed_from,
        values={"status": REJECTED, "approved_amount": None, "reviewer_id": user.id,
                "review_comment": data.comment, "reviewed_at": utcnow()},
        action="rejected", expected_version=data.expected_version, comment=data.comment,
    )


def pay_claim(db: Session, user: User, claim_id: int, data: PayIn) -> Claim:
    claim = get_claim(db, user, claim_id)
    _require_reviewer(user, claim, "mark as paid")
    allowed_from, _ = rules.TRANSITIONS["pay"]
    return _apply(
        db, claim, user, verb="mark as paid", allowed_from=allowed_from,
        values={"status": PAID, "paid_at": utcnow(), "paid_by_id": user.id,
                "payment_reference": data.payment_reference},
        action="paid", expected_version=data.expected_version,
        details={"amount": str(claim.approved_amount)},
    )