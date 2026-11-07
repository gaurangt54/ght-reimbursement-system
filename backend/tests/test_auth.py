def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_list_users_public(client):
    users = client.get("/api/auth/users").json()
    assert {u["role"] for u in users} == {"employee", "approver"}


def test_login_and_me(client):
    uid = client.get("/api/auth/users").json()[0]["id"]
    token = client.post("/api/auth/login", json={"user_id": uid}).json()["token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["id"] == uid


def test_login_unknown_user(client):
    r = client.post("/api/auth/login", json={"user_id": 9999})
    assert r.status_code == 404


def test_requires_token(client):
    r = client.get("/api/claims")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


def test_bad_token_rejected(client):
    assert client.get("/api/claims", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get("/api/claims", headers={"Authorization": "Basic abc"}).status_code == 401


def test_logout_invalidates_token(client, emp):
    assert client.post("/api/auth/logout", headers=emp).status_code == 204
    assert client.get("/api/claims", headers=emp).status_code == 401


def test_error_shape_for_unknown_route(client):
    r = client.get("/api/nothing")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"