"""Basic auth behaviour. Token, refresh and throttle details are in test_auth_tokens.py."""
from tests.conftest import PASSWORD

CSRF = {"X-Requested-With": "XMLHttpRequest"}


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_public_user_list_is_gone(client):
    # The old mocked login exposed every user to anyone; that endpoint no longer exists.
    assert client.get("/api/auth/users").status_code == 404


def test_login_and_me(client):
    r = client.post("/api/auth/login", json={"email": "aarav@napho.test", "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 15 * 60
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}).json()
    assert me["email"] == "aarav@napho.test" and me["role"] == "employee"


def test_login_unknown_user(client):
    r = client.post("/api/auth/login", json={"email": "nobody@napho.test", "password": PASSWORD})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_requires_token(client):
    r = client.get("/api/claims")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


def test_bad_token_rejected(client):
    assert client.get("/api/claims", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get("/api/claims", headers={"Authorization": "Basic abc"}).status_code == 401


def test_logout_invalidates_refresh_token(client):
    client.post("/api/auth/login", json={"email": "aarav@napho.test", "password": PASSWORD})
    assert client.post("/api/auth/refresh", headers=CSRF).status_code == 200
    assert client.post("/api/auth/logout", headers=CSRF).status_code == 204
    assert client.post("/api/auth/refresh", headers=CSRF).status_code == 401


def test_error_shape_for_unknown_route(client):
    r = client.get("/api/nothing")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"
