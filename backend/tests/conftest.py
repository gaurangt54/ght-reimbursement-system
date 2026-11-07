"""Shared test setup.

IMPORTANT: DATABASE_URL must be set before `app` is imported, so tests always run
against a throwaway SQLite file and never touch reimbursement.db.
"""
import os
import tempfile
from datetime import date

_TMP_DIR = tempfile.mkdtemp(prefix="reimbursement_tests_")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DIR}/test.db"
os.environ["SEED_DEMO_DATA"] = "false"   # tests create their own users (below)
os.environ["APP_ENV"] = "test"
os.environ["JWT_SECRET"] = "test-secret-" + "x" * 40
os.environ["BCRYPT_ROUNDS"] = "4"        # the minimum; real hashing cost would slow every test
os.environ["COOKIE_SECURE"] = "false"    # the test client talks plain http

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.seed import create_demo_users, init_db  # noqa: E402
from app.services.throttle import login_throttle  # noqa: E402

PASSWORD = "Test-password-1"


@pytest.fixture(autouse=True)
def fresh_db():
    """Empty database + the 5 demo users before every test (ids: 1-3 employees, 4-5 approvers).
    Everyone's password is PASSWORD."""
    Base.metadata.drop_all(engine)
    init_db()
    with SessionLocal() as session:
        create_demo_users(session, PASSWORD)
    login_throttle.reset()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


def login_headers(client: TestClient, email: str, password: str = PASSWORD) -> dict:
    """Log in with email + password and return the Authorization header to send."""
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


_login = login_headers


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