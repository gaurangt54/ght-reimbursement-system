"""Pure business rules: no database, no HTTP."""
from datetime import date, timedelta
from decimal import Decimal

from app import config
from app.models import APPROVED, DRAFT, PAID, REJECTED, SUBMITTED, Claim, User
from app.services import rules

TODAY = date.today()


def policy(amount="100", days_ago=0, receipt="R1", for_submit=False):
    return rules.validate_policy(
        amount=Decimal(amount), expense_date=TODAY - timedelta(days=days_ago),
        receipt_ref=receipt, for_submit=for_submit,
    )


def test_valid_claim_has_no_errors():
    assert policy() == {}


def test_amount_cap_boundary():
    assert policy(amount=str(config.MAX_CLAIM_AMOUNT)) == {}
    assert "amount" in policy(amount=str(config.MAX_CLAIM_AMOUNT + Decimal("0.01")))


def test_expense_date_cannot_be_in_future():
    assert "expense_date" in policy(days_ago=-1)


def test_expense_age_boundary():
    assert policy(days_ago=config.MAX_EXPENSE_AGE_DAYS) == {}
    assert "expense_date" in policy(days_ago=config.MAX_EXPENSE_AGE_DAYS + 1)


def test_receipt_only_required_on_submit_above_threshold():
    assert policy(amount="5000", receipt=None, for_submit=False) == {}
    assert policy(amount=str(config.RECEIPT_REQUIRED_ABOVE), receipt=None, for_submit=True) == {}
    assert "receipt_ref" in policy(amount="1000.01", receipt=None, for_submit=True)
    assert policy(amount="5000", receipt="R1", for_submit=True) == {}


def test_all_errors_reported_together():
    errors = policy(amount="999999", days_ago=-3, receipt=None, for_submit=True)
    assert set(errors) == {"amount", "expense_date", "receipt_ref"}


def test_fingerprint_ignores_case_and_extra_spaces():
    a = rules.make_fingerprint("INR", "Travel", Decimal("500"), TODAY, "Airport  Taxi")
    b = rules.make_fingerprint("INR", "Travel", Decimal("500.00"), TODAY, " airport taxi ")
    assert a == b


def test_fingerprint_differs_on_amount_date_category_currency():
    base = ("INR", "Travel", Decimal("500"), TODAY, "Taxi")
    f = rules.make_fingerprint(*base)
    assert f != rules.make_fingerprint("INR", "Travel", Decimal("501"), TODAY, "Taxi")
    assert f != rules.make_fingerprint("INR", "Travel", Decimal("500"), TODAY - timedelta(days=1), "Taxi")
    assert f != rules.make_fingerprint("INR", "Meals", Decimal("500"), TODAY, "Taxi")
    assert f != rules.make_fingerprint("USD", "Travel", Decimal("500"), TODAY, "Taxi")


def _user(uid, role):
    return User(id=uid, name="x", email=f"{uid}@x", role=role)


def _claim(status, employee_id=1):
    return Claim(employee_id=employee_id, status=status)


def test_allowed_actions_for_owner():
    owner = _user(1, "employee")
    assert rules.allowed_actions(owner, _claim(DRAFT)) == ["edit", "delete", "submit"]
    assert rules.allowed_actions(owner, _claim(SUBMITTED)) == ["withdraw"]
    assert rules.allowed_actions(owner, _claim(REJECTED)) == ["edit", "submit"]
    assert rules.allowed_actions(owner, _claim(APPROVED)) == []
    assert rules.allowed_actions(owner, _claim(PAID)) == []


def test_allowed_actions_for_approver():
    approver = _user(9, "approver")
    assert rules.allowed_actions(approver, _claim(SUBMITTED)) == ["approve", "reject"]
    assert rules.allowed_actions(approver, _claim(APPROVED)) == ["pay"]
    assert rules.allowed_actions(approver, _claim(REJECTED)) == []
    assert rules.allowed_actions(approver, _claim(DRAFT)) == []


def test_nobody_gets_actions_on_someone_elses_claim_as_employee():
    assert rules.allowed_actions(_user(2, "employee"), _claim(DRAFT, employee_id=1)) == []


def test_approver_cannot_act_on_own_claim():
    assert rules.allowed_actions(_user(9, "approver"), _claim(SUBMITTED, employee_id=9)) == []