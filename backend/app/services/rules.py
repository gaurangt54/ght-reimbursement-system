"""Pure business rules: no database access here, so they are easy to test."""
from datetime import date
from decimal import Decimal

from app import config
from app.models import (
    APPROVED, APPROVER, DRAFT, EMPLOYEE, PAID, REJECTED, SUBMITTED, Claim, User,
)

# action -> (statuses it may start from, status it leads to)
TRANSITIONS = {
    "submit": ({DRAFT, REJECTED}, SUBMITTED),   # from REJECTED this is a "resubmit"
    "withdraw": ({SUBMITTED}, DRAFT),
    "approve": ({SUBMITTED}, APPROVED),
    "reject": ({SUBMITTED}, REJECTED),
    "pay": ({APPROVED}, PAID),
}
EDITABLE_STATUSES = {DRAFT, REJECTED}
DELETABLE_STATUSES = {DRAFT}


def make_fingerprint(currency: str, category: str, amount: Decimal, expense_date: date, title: str) -> str:
    """Identifies 'the same expense' for duplicate detection."""
    normalized_title = " ".join(title.lower().split())
    return "|".join([currency, category, f"{amount:.2f}", expense_date.isoformat(), normalized_title])


def validate_policy(*, amount: Decimal, expense_date: date, receipt_ref: str | None,
                    for_submit: bool) -> dict[str, str]:
    """Return {field: message} for every broken rule (empty dict = OK)."""
    errors: dict[str, str] = {}
    today = date.today()

    if amount > config.MAX_CLAIM_AMOUNT:
        errors["amount"] = f"Amount cannot exceed {config.MAX_CLAIM_AMOUNT:,.2f} {config.DEFAULT_CURRENCY} per claim."

    if expense_date > today:
        errors["expense_date"] = "Expense date cannot be in the future."
    elif (today - expense_date).days > config.MAX_EXPENSE_AGE_DAYS:
        errors["expense_date"] = f"Expenses older than {config.MAX_EXPENSE_AGE_DAYS} days cannot be claimed."

    # Only enforced on submit, so employees can save an incomplete draft first.
    if for_submit and amount > config.RECEIPT_REQUIRED_ABOVE and not receipt_ref:
        errors["receipt_ref"] = (
            f"A receipt reference is required for claims above {config.RECEIPT_REQUIRED_ABOVE:,.2f}."
        )
    return errors


def allowed_actions(user: User, claim: Claim) -> list[str]:
    """What this user may do with this claim right now (the UI uses this to show buttons)."""
    if user.role == EMPLOYEE and claim.employee_id == user.id:
        return {
            DRAFT: ["edit", "delete", "submit"],
            SUBMITTED: ["withdraw"],
            REJECTED: ["edit", "submit"],
        }.get(claim.status, [])
    if user.role == APPROVER and claim.employee_id != user.id:
        return {
            SUBMITTED: ["approve", "reject"],
            APPROVED: ["pay"],
        }.get(claim.status, [])
    return []