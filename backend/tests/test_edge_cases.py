"""Edge cases from the brief: invalid state changes, duplicates, resubmissions,
incorrect amounts, missing information and concurrent actions."""
import threading
from datetime import date, timedelta

import pytest

from app.database import SessionLocal
from app.errors import ApiError
from app.models import Claim, User
from app.schemas import ApproveIn
from app.services import claims as svc


def code(r):
    return r.json()["error"]["code"]


# ---------- invalid state changes ----------

@pytest.mark.parametrize("path,body", [
    ("approve", {}), ("reject", {"comment": "nope"}), ("pay", {}), ("withdraw", None),
])
def test_cannot_review_pay_or_withdraw_a_draft(client, emp, apr, make_claim, path, body):
    claim = make_claim()
    headers = emp if path == "withdraw" else apr
    r = client.post(f"/api/claims/{claim['id']}/{path}", headers=headers, json=body)
    # approvers can't even see drafts (404); the owner gets a state error (409)
    assert r.status_code in (404, 409)


def test_cannot_pay_before_approval(client, apr, submitted_claim):
    claim = submitted_claim()
    r = client.post(f"/api/claims/{claim['id']}/pay", headers=apr, json={})
    assert r.status_code == 409 and code(r) == "INVALID_TRANSITION"


def test_cannot_approve_twice_or_reject_after_approve(client, apr, submitted_claim):
    claim = submitted_claim()
    assert client.post(f"/api/claims/{claim['id']}/approve", headers=apr, json={}).status_code == 200
    r = client.post(f"/api/claims/{claim['id']}/approve", headers=apr, json={})
    assert r.status_code == 409 and code(r) == "INVALID_TRANSITION"
    r = client.post(f"/api/claims/{claim['id']}/reject", headers=apr, json={"comment": "too late"})
    assert r.status_code == 409


def test_cannot_pay_twice(client, apr, submitted_claim):
    claim = submitted_claim()
    client.post(f"/api/claims/{claim['id']}/approve", headers=apr, json={})
    assert client.post(f"/api/claims/{claim['id']}/pay", headers=apr, json={}).status_code == 200
    assert client.post(f"/api/claims/{claim['id']}/pay", headers=apr, json={}).status_code == 409


def test_cannot_edit_or_delete_after_submit(client, emp, submitted_claim, payload):
    claim = submitted_claim()
    assert client.put(f"/api/claims/{claim['id']}", headers=emp, json=payload(title="Changed")).status_code == 409
    assert client.delete(f"/api/claims/{claim['id']}", headers=emp).status_code == 409


def test_cannot_edit_or_withdraw_after_approval(client, emp, apr, submitted_claim, payload):
    claim = submitted_claim()
    client.post(f"/api/claims/{claim['id']}/approve", headers=apr, json={})
    assert client.put(f"/api/claims/{claim['id']}", headers=emp, json=payload(title="Changed")).status_code == 409
    assert client.post(f"/api/claims/{claim['id']}/withdraw", headers=emp).status_code == 409


def test_cannot_delete_a_rejected_claim(client, emp, apr, submitted_claim):
    claim = submitted_claim()
    client.post(f"/api/claims/{claim['id']}/reject", headers=apr, json={"comment": "No"})
    assert client.delete(f"/api/claims/{claim['id']}", headers=emp).status_code == 409


# ---------- duplicate requests ----------

def test_double_submit_second_call_is_rejected(client, emp, make_claim):
    claim = make_claim()
    assert client.post(f"/api/claims/{claim['id']}/submit", headers=emp).status_code == 200
    r = client.post(f"/api/claims/{claim['id']}/submit", headers=emp)
    assert r.status_code == 409 and code(r) == "INVALID_TRANSITION"


def test_duplicate_expense_blocked_on_submit(client, emp, make_claim):
    first = make_claim(title="Airport taxi", amount="500")
    second = make_claim(title="  airport TAXI ", amount="500")   # same expense, sloppy typing
    assert client.post(f"/api/claims/{first['id']}/submit", headers=emp).status_code == 200
    r = client.post(f"/api/claims/{second['id']}/submit", headers=emp)
    assert r.status_code == 409 and code(r) == "DUPLICATE_CLAIM"


def test_drafts_may_be_duplicates_until_submitted(make_claim):
    make_claim(title="Taxi", amount="500")
    make_claim(title="Taxi", amount="500")   # no error: only live claims collide


def test_different_amount_or_date_is_not_a_duplicate(client, emp, make_claim):
    a = make_claim(title="Taxi", amount="500")
    b = make_claim(title="Taxi", amount="501")
    c = make_claim(title="Taxi", amount="500", expense_date=(date.today() - timedelta(days=1)).isoformat())
    for claim in (a, b, c):
        assert client.post(f"/api/claims/{claim['id']}/submit", headers=emp).status_code == 200


def test_same_expense_by_different_employees_is_fine(client, emp, emp2, make_claim, submitted_claim):
    submitted_claim(title="Taxi", amount="500")
    other = make_claim(headers=emp2, title="Taxi", amount="500")
    assert client.post(f"/api/claims/{other['id']}/submit", headers=emp2).status_code == 200


def test_rejected_claim_does_not_block_a_fresh_claim(client, emp, apr, make_claim, submitted_claim):
    first = submitted_claim(title="Taxi", amount="500")
    client.post(f"/api/claims/{first['id']}/reject", headers=apr, json={"comment": "Resend"})
    again = make_claim(title="Taxi", amount="500")
    assert client.post(f"/api/claims/{again['id']}/submit", headers=emp).status_code == 200


# ---------- resubmissions ----------

def test_resubmission_count_increments_each_round(client, emp, apr, submitted_claim):
    claim = submitted_claim()
    for round_no in (1, 2, 3):
        client.post(f"/api/claims/{claim['id']}/reject", headers=apr, json={"comment": "Again"})
        r = client.post(f"/api/claims/{claim['id']}/submit", headers=emp)
        assert r.json()["resubmission_count"] == round_no


def test_resubmit_still_checks_policy(client, emp, apr, submitted_claim, payload):
    claim = submitted_claim()
    client.post(f"/api/claims/{claim['id']}/reject", headers=apr, json={"comment": "Fix receipt"})
    client.put(f"/api/claims/{claim['id']}", headers=emp, json=payload(receipt_ref=""))
    r = client.post(f"/api/claims/{claim['id']}/submit", headers=emp)
    assert r.status_code == 422 and "receipt_ref" in r.json()["error"]["fields"]


# ---------- incorrect amounts ----------

@pytest.mark.parametrize("amount", ["0", "-5", "abc", "12.345", "", "NaN", "Infinity"])
def test_invalid_amounts_rejected(client, emp, payload, amount):
    r = client.post("/api/claims", headers=emp, json=payload(amount=amount))
    assert r.status_code == 422 and "amount" in r.json()["error"]["fields"]


def test_amount_over_cap_rejected(client, emp, payload):
    r = client.post("/api/claims", headers=emp, json=payload(amount="100000.01"))
    assert r.status_code == 422 and "amount" in r.json()["error"]["fields"]


def test_amount_at_cap_allowed(client, emp, payload):
    assert client.post("/api/claims", headers=emp, json=payload(amount="100000.00")).status_code == 201


def test_approved_amount_cannot_exceed_claimed(client, apr, submitted_claim):
    claim = submitted_claim()
    r = client.post(f"/api/claims/{claim['id']}/approve", headers=apr, json={"approved_amount": "8000.01"})
    assert r.status_code == 422 and "approved_amount" in r.json()["error"]["fields"]


@pytest.mark.parametrize("value", ["0", "-1", "100.999"])
def test_approved_amount_must_be_positive_with_two_decimals(client, apr, submitted_claim, value):
    claim = submitted_claim()
    r = client.post(f"/api/claims/{claim['id']}/approve", headers=apr,
                    json={"approved_amount": value, "comment": "x"})
    assert r.status_code == 422


def test_approved_amount_equal_to_claimed_counts_as_full_approval(client, apr, submitted_claim):
    claim = submitted_claim()
    r = client.post(f"/api/claims/{claim['id']}/approve", headers=apr, json={"approved_amount": "8000"})
    assert r.status_code == 200 and r.json()["is_partial"] is False
    assert r.json()["events"][-1]["action"] == "approved"


# ---------- missing / invalid information ----------

def test_missing_required_fields_reported_per_field(client, emp):
    r = client.post("/api/claims", headers=emp, json={})
    assert r.status_code == 422
    assert {"title", "category", "amount", "expense_date"} <= set(r.json()["error"]["fields"])


def test_title_too_short_and_unknown_category(client, emp, payload):
    r = client.post("/api/claims", headers=emp, json=payload(title="ab", category="Boats"))
    assert {"title", "category"} <= set(r.json()["error"]["fields"])


def test_whitespace_only_title_rejected(client, emp, payload):
    assert client.post("/api/claims", headers=emp, json=payload(title="    ")).status_code == 422


def test_future_and_stale_dates_rejected(client, emp, payload):
    future = (date.today() + timedelta(days=1)).isoformat()
    stale = (date.today() - timedelta(days=91)).isoformat()
    for bad in (future, stale):
        r = client.post("/api/claims", headers=emp, json=payload(expense_date=bad))
        assert r.status_code == 422 and "expense_date" in r.json()["error"]["fields"]


def test_receipt_required_to_submit_large_claim(client, emp, make_claim):
    claim = make_claim(amount="1500", receipt_ref=None)       # a draft may be incomplete
    r = client.post(f"/api/claims/{claim['id']}/submit", headers=emp)
    assert r.status_code == 422 and "receipt_ref" in r.json()["error"]["fields"]


def test_small_claim_needs_no_receipt(client, emp, make_claim):
    claim = make_claim(amount="999", receipt_ref=None)
    assert client.post(f"/api/claims/{claim['id']}/submit", headers=emp).status_code == 200


def test_reject_requires_a_comment(client, apr, submitted_claim):
    claim = submitted_claim()
    for body in ({}, {"comment": ""}, {"comment": "  "}):
        r = client.post(f"/api/claims/{claim['id']}/reject", headers=apr, json=body)
        assert r.status_code == 422 and "comment" in r.json()["error"]["fields"]


def test_partial_approval_requires_a_comment(client, apr, submitted_claim):
    claim = submitted_claim()
    r = client.post(f"/api/claims/{claim['id']}/approve", headers=apr, json={"approved_amount": "6500"})
    assert r.status_code == 422 and "comment" in r.json()["error"]["fields"]


def test_validation_failure_changes_nothing(client, emp, apr, submitted_claim):
    claim = submitted_claim()
    client.post(f"/api/claims/{claim['id']}/approve", headers=apr, json={"approved_amount": "1"})
    after = client.get(f"/api/claims/{claim['id']}", headers=emp).json()
    assert after["status"] == "SUBMITTED" and after["version"] == claim["version"]


# ---------- permissions ----------

def test_approver_cannot_create_claims(client, apr, payload):
    r = client.post("/api/claims", headers=apr, json=payload())
    assert r.status_code == 403


def test_employee_cannot_review_or_pay(client, emp, submitted_claim):
    claim = submitted_claim()
    for path, body in (("approve", {}), ("reject", {"comment": "nope"}), ("pay", {})):
        assert client.post(f"/api/claims/{claim['id']}/{path}", headers=emp, json=body).status_code == 403


def test_employee_cannot_see_or_touch_other_employees_claims(client, emp2, make_claim, payload):
    claim = make_claim()   # Aarav's
    assert client.get(f"/api/claims/{claim['id']}", headers=emp2).status_code == 404
    assert client.put(f"/api/claims/{claim['id']}", headers=emp2, json=payload()).status_code == 404
    assert client.delete(f"/api/claims/{claim['id']}", headers=emp2).status_code == 404
    assert client.post(f"/api/claims/{claim['id']}/submit", headers=emp2).status_code == 404


def test_approver_cannot_see_drafts(client, apr, make_claim):
    claim = make_claim()
    assert client.get(f"/api/claims/{claim['id']}", headers=apr).status_code == 404
    assert client.get("/api/claims", headers=apr).json()["total"] == 0


def test_approver_cannot_edit_claims(client, apr, submitted_claim, payload):
    claim = submitted_claim()
    assert client.put(f"/api/claims/{claim['id']}", headers=apr, json=payload()).status_code == 403


def test_approver_cannot_review_own_claim(db, users):
    approver = users["neha"]
    own = Claim(employee_id=approver.id, title="Own", category="Meals", amount=100, expense_date=date.today(),
                status="SUBMITTED", fingerprint="own")
    db.add(own); db.commit()
    with pytest.raises(ApiError) as exc:
        svc.approve_claim(db, approver, own.id, ApproveIn())
    assert exc.value.status_code == 403


# ---------- concurrency ----------

def test_stale_version_is_rejected(client, emp, apr, submitted_claim):
    claim = submitted_claim()
    r = client.post(f"/api/claims/{claim['id']}/approve", headers=apr,
                    json={"expected_version": claim["version"] - 1})
    assert r.status_code == 409 and code(r) == "STALE_VERSION"
    # with the correct version it works
    r = client.post(f"/api/claims/{claim['id']}/approve", headers=apr,
                    json={"expected_version": claim["version"]})
    assert r.status_code == 200


def test_approver_with_stale_page_cannot_approve_a_changed_claim(client, emp, apr, submitted_claim):
    """Withdraw -> edit -> resubmit while an approver still has the old page open."""
    seen = submitted_claim()
    client.post(f"/api/claims/{seen['id']}/withdraw", headers=emp)
    client.post(f"/api/claims/{seen['id']}/submit", headers=emp)
    r = client.post(f"/api/claims/{seen['id']}/approve", headers=apr,
                    json={"expected_version": seen["version"]})
    assert r.status_code == 409 and code(r) == "STALE_VERSION"


def test_stale_edit_is_rejected(client, emp, make_claim, payload):
    claim = make_claim()
    client.put(f"/api/claims/{claim['id']}", headers=emp, json=payload(title="First edit"))
    r = client.put(f"/api/claims/{claim['id']}", headers=emp,
                   json=payload(title="Second edit", expected_version=claim["version"]))
    assert r.status_code == 409 and code(r) == "STALE_VERSION"


def _run_in_threads(jobs):
    results = []
    lock = threading.Lock()

    def wrap(job):
        outcome = job()
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=wrap, args=(j,)) for j in jobs]
    [t.start() for t in threads]
    [t.join() for t in threads]
    return results


def _as_user(user_id, fn, *args):
    """Run a service call in its own DB session, like a separate request would."""
    def job():
        with SessionLocal() as session:
            try:
                fn(session, session.get(User, user_id), *args)
                return "won"
            except ApiError as e:
                return e.code
    return job


def test_two_approvers_approving_at_once_only_one_wins(submitted_claim):
    claim = submitted_claim()
    results = _run_in_threads([
        _as_user(4, svc.approve_claim, claim["id"], ApproveIn()),
        _as_user(5, svc.approve_claim, claim["id"], ApproveIn()),
    ])
    assert results.count("won") == 1
    assert set(results) - {"won"} <= {"INVALID_TRANSITION", "CONCURRENT_UPDATE"}


def test_double_click_submit_only_one_wins(make_claim):
    claim = make_claim()
    results = _run_in_threads([_as_user(1, svc.submit_claim, claim["id"]) for _ in range(4)])
    assert results.count("won") == 1
    assert len(results) == 4


def test_duplicate_claims_submitted_at_once_only_one_wins(make_claim):
    a = make_claim(title="Taxi", amount="500")
    b = make_claim(title="Taxi", amount="500")
    results = _run_in_threads([
        _as_user(1, svc.submit_claim, a["id"]),
        _as_user(1, svc.submit_claim, b["id"]),
    ])
    assert results.count("won") == 1
    assert "DUPLICATE_CLAIM" in results


def test_withdraw_racing_with_approve_has_one_winner(client, emp, submitted_claim):
    claim = submitted_claim()
    results = _run_in_threads([
        _as_user(1, svc.withdraw_claim, claim["id"]),
        _as_user(4, svc.approve_claim, claim["id"], ApproveIn()),
    ])
    assert results.count("won") == 1
    final = client.get(f"/api/claims/{claim['id']}", headers=emp).json()
    assert final["status"] in ("DRAFT", "APPROVED")
    assert len(final["events"]) == 3   # created, submitted, + exactly one of withdrawn/approved