"""The happy paths: Create -> Submit -> Review -> Approve/Reject -> Paid, plus history."""
from decimal import Decimal

from app.models import Claim


def actions(claim):
    return [e["action"] for e in claim["events"]]


def test_full_flow_to_paid(client, emp, apr, make_claim):
    claim = make_claim()
    assert claim["status"] == "DRAFT" and claim["amount"] == "8000.00"
    assert claim["allowed_actions"] == ["edit", "delete", "submit"]

    r = client.post(f"/api/claims/{claim['id']}/submit", headers=emp)
    assert r.json()["status"] == "SUBMITTED" and r.json()["submitted_at"]

    r = client.post(f"/api/claims/{claim['id']}/approve", headers=apr, json={"comment": "ok"})
    body = r.json()
    assert body["status"] == "APPROVED"
    assert body["approved_amount"] == "8000.00" and body["is_partial"] is False
    assert body["reviewer"]["name"] == "Neha Kapoor"

    r = client.post(f"/api/claims/{claim['id']}/pay", headers=apr, json={"payment_reference": "UTR1"})
    body = r.json()
    assert body["status"] == "PAID" and body["payment_reference"] == "UTR1" and body["paid_at"]
    assert body["allowed_actions"] == []
    assert actions(body) == ["created", "submitted", "approved", "paid"]


def test_partial_approval_8000_to_6500(client, emp, apr, submitted_claim):
    claim = submitted_claim()
    r = client.post(f"/api/claims/{claim['id']}/approve", headers=apr,
                    json={"approved_amount": "6500", "comment": "Alcohol not covered"})
    body = r.json()
    assert body["amount"] == "8000.00"            # the request is never overwritten
    assert body["approved_amount"] == "6500.00"
    assert body["is_partial"] is True
    assert body["events"][-1]["action"] == "partially_approved"
    assert body["events"][-1]["details"] == {"claimed": "8000.00", "approved": "6500.00"}


def test_reject_edit_resubmit_approve(client, emp, apr, submitted_claim, payload):
    claim = submitted_claim()
    r = client.post(f"/api/claims/{claim['id']}/reject", headers=apr, json={"comment": "Wrong amount"})
    body = r.json()
    assert body["status"] == "REJECTED" and body["review_comment"] == "Wrong amount"
    assert body["allowed_actions"] == []   # the approver has nothing left to do...
    owner_view = client.get(f"/api/claims/{claim['id']}", headers=emp).json()
    assert owner_view["allowed_actions"] == ["edit", "submit"]   # ...the owner can fix it

    r = client.put(f"/api/claims/{claim['id']}", headers=emp, json=payload(amount="7500"))
    assert r.json()["status"] == "REJECTED" and r.json()["amount"] == "7500.00"

    r = client.post(f"/api/claims/{claim['id']}/submit", headers=emp)
    body = r.json()
    assert body["status"] == "SUBMITTED"
    assert body["resubmission_count"] == 1
    assert body["review_comment"] is None and body["reviewer"] is None  # cleared on the claim...
    assert "rejected" in actions(body)                                   # ...kept in history
    assert actions(body)[-1] == "resubmitted"

    r = client.post(f"/api/claims/{claim['id']}/approve", headers=apr, json={})
    assert r.json()["status"] == "APPROVED"


def test_withdraw_returns_to_draft_and_can_be_resubmitted(client, emp, submitted_claim):
    claim = submitted_claim()
    r = client.post(f"/api/claims/{claim['id']}/withdraw", headers=emp)
    assert r.json()["status"] == "DRAFT" and r.json()["submitted_at"] is None
    r = client.post(f"/api/claims/{claim['id']}/submit", headers=emp)
    assert r.json()["status"] == "SUBMITTED"
    assert actions(r.json()) == ["created", "submitted", "withdrawn", "submitted"]


def test_edit_records_old_and_new_values(client, emp, make_claim, payload):
    claim = make_claim()
    r = client.put(f"/api/claims/{claim['id']}", headers=emp,
                   json=payload(title="Team lunch", amount="9000"))
    event = r.json()["events"][-1]
    assert event["action"] == "edited"
    assert event["details"]["title"] == ["Client lunch", "Team lunch"]
    assert event["details"]["amount"] == ["8000.00", "9000.00"]
    assert r.json()["version"] == claim["version"] + 1


def test_edit_with_no_changes_is_a_noop(client, emp, make_claim, payload):
    claim = make_claim()
    r = client.put(f"/api/claims/{claim['id']}", headers=emp, json=payload())
    assert r.status_code == 200
    assert r.json()["version"] == claim["version"]
    assert actions(r.json()) == ["created"]


def test_delete_draft_is_soft_and_hidden(client, emp, make_claim, db):
    claim = make_claim()
    assert client.delete(f"/api/claims/{claim['id']}", headers=emp).status_code == 204
    assert client.get(f"/api/claims/{claim['id']}", headers=emp).status_code == 404
    assert client.get("/api/claims", headers=emp).json()["total"] == 0
    row = db.get(Claim, claim["id"])
    assert row is not None and row.deleted_at is not None   # still in DB for the audit trail


def test_amounts_keep_two_decimals(client, make_claim):
    claim = make_claim(amount="1234.5")
    assert claim["amount"] == "1234.50"
    assert Decimal(claim["amount"]) == Decimal("1234.50")


def test_version_increases_with_every_change(client, emp, apr, make_claim):
    claim = make_claim()
    v = claim["version"]
    r = client.post(f"/api/claims/{claim['id']}/submit", headers=emp)
    assert r.json()["version"] == v + 1
    r = client.post(f"/api/claims/{claim['id']}/approve", headers=apr, json={})
    assert r.json()["version"] == v + 2