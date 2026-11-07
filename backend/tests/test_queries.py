"""Lists, filters, search, pagination, summary and CSV export."""
from datetime import date, timedelta


def titles(r):
    return [c["title"] for c in r.json()["items"]]


def test_employee_sees_only_own_claims(client, emp, emp2, make_claim):
    make_claim(title="Mine")
    make_claim(headers=emp2, title="Theirs")
    assert titles(client.get("/api/claims", headers=emp)) == ["Mine"]
    assert titles(client.get("/api/claims", headers=emp2)) == ["Theirs"]


def test_approver_sees_everyone_except_drafts(client, apr, make_claim, submitted_claim, emp2):
    make_claim(title="Draft")
    submitted_claim(title="Sent")
    assert titles(client.get("/api/claims", headers=apr)) == ["Sent"]


def test_pending_queue_oldest_first_and_reviewed_scope(client, emp, apr, submitted_claim):
    first = submitted_claim(title="First", amount="100")
    submitted_claim(title="Second", amount="200")
    assert titles(client.get("/api/claims?scope=pending", headers=apr)) == ["First", "Second"]
    client.post(f"/api/claims/{first['id']}/approve", headers=apr, json={})
    assert titles(client.get("/api/claims?scope=pending", headers=apr)) == ["Second"]
    assert titles(client.get("/api/claims?scope=reviewed", headers=apr)) == ["First"]


def test_filter_by_status_and_category(client, emp, apr, make_claim, submitted_claim):
    make_claim(title="Draft one", category="Travel", amount="50")
    submitted_claim(title="Sent one", category="Meals", amount="60")
    assert titles(client.get("/api/claims?status=DRAFT", headers=emp)) == ["Draft one"]
    assert titles(client.get("/api/claims?category=Meals", headers=emp)) == ["Sent one"]
    assert client.get("/api/claims?status=PAID", headers=emp).json()["total"] == 0


def test_filter_by_expense_date_range(client, emp, make_claim):
    old = (date.today() - timedelta(days=30)).isoformat()
    make_claim(title="Old", expense_date=old, amount="10")
    make_claim(title="New", amount="20")
    cutoff = (date.today() - timedelta(days=7)).isoformat()
    assert titles(client.get(f"/api/claims?date_from={cutoff}", headers=emp)) == ["New"]
    assert titles(client.get(f"/api/claims?date_to={cutoff}", headers=emp)) == ["Old"]


def test_search_by_title_description_id_and_employee(client, emp, apr, submitted_claim):
    claim = submitted_claim(title="Quarterly offsite", description="Hotel for the team", amount="10")
    for q in ("offsite", "HOTEL", str(claim["id"]), "aarav"):
        assert titles(client.get("/api/claims", params={"q": q}, headers=apr)) == ["Quarterly offsite"], q
    assert titles(client.get("/api/claims", params={"q": "nothing-like-this"}, headers=apr)) == []


def test_search_treats_wildcards_literally(client, emp, make_claim):
    make_claim(title="Plain title")
    assert client.get("/api/claims", params={"q": "%"}, headers=emp).json()["total"] == 0
    assert client.get("/api/claims", params={"q": "_"}, headers=emp).json()["total"] == 0


def test_pagination(client, emp, make_claim):
    for i in range(5):
        make_claim(title=f"Claim {i}", amount=str(10 + i))
    page1 = client.get("/api/claims?page=1&page_size=2", headers=emp).json()
    page3 = client.get("/api/claims?page=3&page_size=2", headers=emp).json()
    assert page1["total"] == 5 and len(page1["items"]) == 2
    assert len(page3["items"]) == 1
    seen = {c["id"] for p in (1, 2, 3)
            for c in client.get(f"/api/claims?page={p}&page_size=2", headers=emp).json()["items"]}
    assert len(seen) == 5   # no overlaps or gaps


def test_sorting(client, emp, make_claim):
    make_claim(title="Cheap", amount="10")
    make_claim(title="Pricey", amount="900")
    assert titles(client.get("/api/claims?sort_by=amount&order=desc", headers=emp)) == ["Pricey", "Cheap"]
    assert titles(client.get("/api/claims?sort_by=amount&order=asc", headers=emp)) == ["Cheap", "Pricey"]


def test_invalid_filter_values_return_422(client, emp):
    for qs in ("status=WRONG", "scope=x", "sort_by=password", "order=sideways", "page=0", "page_size=500",
               "date_from=2030-01-02&date_to=2030-01-01"):
        r = client.get(f"/api/claims?{qs}", headers=emp)
        assert r.status_code == 422, qs


def test_summary_for_employee_and_approver(client, emp, apr, make_claim, submitted_claim):
    make_claim(title="Draft", amount="100")
    pending = submitted_claim(title="Pending", amount="200")
    partial = submitted_claim(title="Partial", amount="8000")
    paid = submitted_claim(title="Paid", amount="500")
    client.post(f"/api/claims/{partial['id']}/approve", headers=apr,
                json={"approved_amount": "6500", "comment": "Reduced"})
    client.post(f"/api/claims/{paid['id']}/approve", headers=apr, json={})
    client.post(f"/api/claims/{paid['id']}/pay", headers=apr, json={})

    s = client.get("/api/claims/summary", headers=emp).json()
    assert s["counts"] == {"DRAFT": 1, "SUBMITTED": 1, "APPROVED": 1, "REJECTED": 0, "PAID": 1}
    assert s["total_claimed"] == "8700.00"       # drafts are not counted
    assert s["pending_amount"] == "200.00"
    assert s["approved_amount"] == "7000.00"     # 6500 + 500 (approved amounts, not claimed)
    assert s["paid_amount"] == "500.00"

    s = client.get("/api/claims/summary", headers=apr).json()
    assert s["counts"]["DRAFT"] == 0 and s["counts"]["SUBMITTED"] == 1


def test_summary_has_no_float_drift(client, emp, make_claim, submitted_claim):
    for i in range(10):
        submitted_claim(title=f"Tenth {i}", amount="0.10")
    assert client.get("/api/claims/summary", headers=emp).json()["total_claimed"] == "1.00"


def test_csv_export_for_approver(client, apr, submitted_claim):
    submitted_claim(title="Export me", amount="1234.50")
    r = client.get("/api/claims/export.csv", headers=apr)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("ID,Employee,Title")
    assert len(lines) == 2 and "Export me" in lines[1] and "1234.50" in lines[1]


def test_csv_export_is_approver_only(client, emp):
    assert client.get("/api/claims/export.csv", headers=emp).status_code == 403


def test_csv_neutralises_formula_injection(client, apr, submitted_claim):
    submitted_claim(title='=HYPERLINK("http://evil","click")', amount="10")
    assert "'=HYPERLINK" in client.get("/api/claims/export.csv", headers=apr).text


def test_csv_respects_filters(client, apr, submitted_claim):
    submitted_claim(title="Meal one", category="Meals", amount="10")
    submitted_claim(title="Travel one", category="Travel", amount="20")
    text = client.get("/api/claims/export.csv?category=Travel", headers=apr).text
    assert "Travel one" in text and "Meal one" not in text


def test_meta_endpoint(client):
    meta = client.get("/api/meta").json()
    assert "Travel" in meta["categories"] and meta["currency"] == "INR"