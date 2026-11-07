"""Shared test setup.

IMPORTANT: DATABASE_URL must be set before `app` is imported, so tests always run
against a throwaway SQLite file and never touch reimbursement.db.
"""
import os
import tempfile
from datetime import date

_TMP_DIR = tempfile.mkdtemp(prefix="reimbursement_tests_")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DIR}/test.db"
os.environ["SEED_DEMO_DATA"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.seed import init_db  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    """Empty database + the 5 mock users before every test (ids: 1-3 employees, 4-5 approvers)."""
    Base.metadata.drop_all(engine)
    init_db()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


def _login(client: TestClient, email: str) -> dict:
    users = client.get("/api/auth/users").json()
    user = next(u for u in users if u["email"] == email)
    token = client.post("/api/auth/login", json={"user_id": user["id"]}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def emp(client):    # Aarav Sharma, employee
    return _login(client, "aarav@napho.test")


@pytest.fixture
def emp2(client):   # Priya Nair, employee
    return _login(client, "priya@napho.test")


@pytest.fixture
def apr(client):    # Neha Kapoor, approver
    return _login(client, "neha@napho.test")


@pytest.fixture
def apr2(client):   # Vikram Rao, approver
    return _login(client, "vikram@napho.test")


@pytest.fixture
def payload():
    """Factory for a valid claim body; override any field per test."""
    def make(**overrides):
        body = {
            "title": "Client lunch", "category": "Meals", "amount": "8000.00",
            "expense_date": date.today().isoformat(), "receipt_ref": "INV-1",
            "description": "Lunch with client",
        }
        body.update(overrides)
        return body
    return make


@pytest.fixture
def make_claim(client, emp, payload):
    """Create a draft via the API and return its JSON. `headers` defaults to employee Aarav."""
    def make(headers=None, **overrides):
        r = client.post("/api/claims", json=payload(**overrides), headers=headers or emp)
        assert r.status_code == 201, r.text
        return r.json()
    return make


@pytest.fixture
def submitted_claim(client, emp, make_claim):
    def make(**overrides):
        claim = make_claim(**overrides)
        r = client.post(f"/api/claims/{claim['id']}/submit", headers=emp)
        assert r.status_code == 200, r.text
        return r.json()
    return make


@pytest.fixture
def users(db):
    return {u.name.split()[0].lower(): u for u in db.query(User)}