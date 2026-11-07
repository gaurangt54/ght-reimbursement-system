"""Turn ORM objects into the dicts our response schemas expect."""
from app.models import Claim, ClaimEvent, User
from app.services import rules


def user_out(u: User | None, *, full: bool = False) -> dict | None:
    if u is None:
        return None
    out = {"id": u.id, "name": u.name}
    if full:
        out.update(email=u.email, role=u.role)
    return out


def claim_out(claim: Claim, viewer: User) -> dict:
    return {
        "id": claim.id,
        "employee": user_out(claim.employee),
        "title": claim.title,
        "description": claim.description,
        "category": claim.category,
        "amount": claim.amount,
        "currency": claim.currency,
        "expense_date": claim.expense_date,
        "receipt_ref": claim.receipt_ref,
        "status": claim.status,
        "version": claim.version,
        "approved_amount": claim.approved_amount,
        "is_partial": claim.approved_amount is not None and claim.approved_amount < claim.amount,
        "reviewer": user_out(claim.reviewer),
        "review_comment": claim.review_comment,
        "reviewed_at": claim.reviewed_at,
        "paid_at": claim.paid_at,
        "payment_reference": claim.payment_reference,
        "submitted_at": claim.submitted_at,
        "resubmission_count": claim.resubmission_count,
        "created_at": claim.created_at,
        "updated_at": claim.updated_at,
        "allowed_actions": rules.allowed_actions(viewer, claim),
    }


def event_out(e: ClaimEvent) -> dict:
    return {
        "id": e.id, "action": e.action, "from_status": e.from_status, "to_status": e.to_status,
        "comment": e.comment, "details": e.details, "created_at": e.created_at,
        "user": user_out(e.user, full=True),
    }


def claim_detail_out(claim: Claim, viewer: User) -> dict:
    return {**claim_out(claim, viewer), "events": [event_out(e) for e in claim.events]}