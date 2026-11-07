"""Real authentication: passwords, JWT access tokens, refresh-token rotation, throttling."""
import base64
import hashlib
import json
from datetime import timedelta

import jwt
import pytest
from sqlalchemy import create_engine, select, text, update

from app import config, seed, security
from app.models import RefreshToken, User, utcnow
from tests.conftest import PASSWORD, login_headers

CSRF = {"X-Requested-With": "XMLHttpRequest"}
EMP = "aarav@napho.test"


def login(client, email=EMP, password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def refresh_with(client, raw):
    """Refresh using exactly this refresh token (bypassing the client's cookie jar)."""
    client.cookies.clear()
    return client.post("/api/auth/refresh", headers={**CSRF, "Cookie": f"refresh_token={raw}"})


def set_cookie_headers(response) -> list[str]:
    return [h for h in response.headers.get_list("set-cookie") if h.startswith("refresh_token=")]


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def b64(obj) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()


def claims_for(user_id=1, **overrides):
    now = utcnow()
    claims = {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=5),
              "jti": "abc", "type": "access"}
    claims.update(overrides)
    return {k: v for k, v in claims.items() if v is not None}


# ---------- login ----------

def test_wrong_password_and_unknown_email_look_identical(client):
    wrong = login(client, EMP, "not-the-password")
    unknown = login(client, "ghost@napho.test", "not-the-password")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert wrong.json()["error"]["message"] == "Incorrect email or password."


def test_unknown_email_still_runs_a_password_hash(client, monkeypatch):
    calls = []
    real = security.bcrypt.checkpw
    monkeypatch.setattr(security.bcrypt, "checkpw", lambda pw, h: calls.append(1) or real(pw, h))
    login(client, "ghost@napho.test", "whatever-password")
    assert len(calls) == 1  # timing does not reveal whether the email exists


def test_login_email_is_case_and_space_insensitive(client):
    assert login(client, "  AARAV@Napho.TEST ").status_code == 200


def test_login_sets_a_hardened_refresh_cookie_and_keeps_it_out_of_the_body(client):
    r = login(client)
    [cookie] = set_cookie_headers(r)
    lower = cookie.lower()
    assert "httponly" in lower and "samesite=lax" in lower and "path=/api/auth" in lower
    assert "secure" not in lower  # COOKIE_SECURE is off for plain-http local dev / tests
    assert "refresh" not in json.dumps(r.json())
    assert r.headers["cache-control"] == "no-store"


def test_cookie_is_secure_when_configured(client, monkeypatch):
    monkeypatch.setattr(config, "COOKIE_SECURE", True)
    [cookie] = set_cookie_headers(login(client))
    assert "secure" in cookie.lower()


def test_passwords_and_refresh_tokens_are_stored_hashed(client, db):
    raw = login(client).cookies["refresh_token"]
    user = db.scalar(select(User).where(User.email == EMP))
    assert user.password_hash.startswith("$2b$") and PASSWORD not in user.password_hash
    stored = db.scalar(select(RefreshToken.token_hash))
    assert stored == hashlib.sha256(raw.encode()).hexdigest() and raw not in stored


def test_deactivated_user_cannot_log_in(client, db):
    db.execute(update(User).where(User.email == EMP).values(is_active=False))
    db.commit()
    r = login(client)
    assert r.status_code == 401 and r.json()["error"]["code"] == "INVALID_CREDENTIALS"


# ---------- access tokens ----------

def test_tampered_token_is_rejected(client):
    token = login(client).json()["access_token"]
    header, payload, sig = token.split(".")
    forged = b64({**json.loads(base64.urlsafe_b64decode(payload + "==")), "sub": "4"})
    r = client.get("/api/auth/me", headers=bearer(f"{header}.{forged}.{sig}"))
    assert r.status_code == 401 and r.json()["error"]["code"] == "INVALID_TOKEN"


def test_expired_token_is_rejected(client):
    now = utcnow()
    token = jwt.encode(claims_for(iat=now - timedelta(hours=1), exp=now - timedelta(minutes=1)),
                       config.JWT_SECRET, algorithm="HS256")
    r = client.get("/api/auth/me", headers=bearer(token))
    assert r.status_code == 401 and r.json()["error"]["code"] == "TOKEN_EXPIRED"


def test_alg_none_token_is_rejected(client):
    claims = claims_for()
    claims = {**claims, "iat": int(claims["iat"].timestamp()), "exp": int(claims["exp"].timestamp())}
    unsigned = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64(claims)}."
    assert client.get("/api/auth/me", headers=bearer(unsigned)).status_code == 401


@pytest.mark.filterwarnings("ignore::jwt.warnings.InsecureKeyLengthWarning")
@pytest.mark.parametrize("key,alg", [
    ("some-other-secret-that-is-long-enough-1234", "HS256"),  # wrong key
    (None, "HS512"),                                          # right key, algorithm swapped
])
def test_token_with_wrong_key_or_algorithm_is_rejected(client, key, alg):
    token = jwt.encode(claims_for(), key or config.JWT_SECRET, algorithm=alg)
    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 401


def test_token_missing_required_claims_is_rejected(client):
    token = jwt.encode(claims_for(jti=None), config.JWT_SECRET, algorithm="HS256")
    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 401


def test_refresh_token_cannot_be_used_as_an_access_token(client):
    raw = login(client).cookies["refresh_token"]
    assert client.get("/api/auth/me", headers=bearer(raw)).status_code == 401


def test_role_and_deactivation_are_read_from_the_database_each_request(client, db):
    headers = login_headers(client, EMP)
    db.execute(update(User).where(User.email == EMP).values(role="approver"))
    db.commit()
    assert client.get("/api/auth/me", headers=headers).json()["role"] == "approver"
    db.execute(update(User).where(User.email == EMP).values(is_active=False))
    db.commit()
    assert client.get("/api/auth/me", headers=headers).status_code == 401


# ---------- refresh tokens ----------

def test_refresh_requires_the_csrf_header(client):
    login(client)
    r = client.post("/api/auth/refresh")
    assert r.status_code == 403 and r.json()["error"]["code"] == "CSRF_CHECK_FAILED"


def test_refresh_without_a_cookie_is_401(client):
    assert client.post("/api/auth/refresh", headers=CSRF).status_code == 401


def test_refresh_rotates_the_token(client, db):
    first = login(client).cookies["refresh_token"]
    r = refresh_with(client, first)
    assert r.status_code == 200
    second = r.cookies["refresh_token"]
    assert second != first
    assert client.get("/api/auth/me", headers=bearer(r.json()["access_token"])).status_code == 200
    old = db.scalar(select(RefreshToken).where(
        RefreshToken.token_hash == hashlib.sha256(first.encode()).hexdigest()))
    assert old.revoked_at is not None and old.replaced_by is not None
    assert refresh_with(client, second).status_code == 200  # the new one works in turn


def test_replay_within_grace_window_is_tolerated(client):
    first = login(client).cookies["refresh_token"]
    second = refresh_with(client, first).cookies["refresh_token"]
    again = refresh_with(client, first)  # e.g. a second tab, or StrictMode's double effect
    assert again.status_code == 200 and again.json()["access_token"]
    assert set_cookie_headers(again) == []  # leaves the cookie the other request set
    assert refresh_with(client, second).status_code == 200  # the login is still alive


def test_replay_after_grace_window_revokes_the_whole_family(client, db):
    first = login(client).cookies["refresh_token"]
    second = refresh_with(client, first).cookies["refresh_token"]
    db.execute(update(RefreshToken).where(RefreshToken.revoked_at.is_not(None))
               .values(revoked_at=utcnow() - timedelta(seconds=config.REFRESH_REUSE_GRACE_SECONDS + 5)))
    db.commit()
    r = refresh_with(client, first)
    assert r.status_code == 401 and r.json()["error"]["code"] == "REFRESH_TOKEN_REUSED"
    assert refresh_with(client, second).status_code == 401  # the legitimate holder is out too
    assert db.scalar(select(RefreshToken.id).where(RefreshToken.revoked_at.is_(None))) is None


def test_reuse_only_revokes_that_login_not_other_devices(client, db):
    laptop = login(client).cookies["refresh_token"]
    phone = login(client).cookies["refresh_token"]
    refresh_with(client, laptop)
    db.execute(update(RefreshToken).where(RefreshToken.revoked_at.is_not(None))
               .values(revoked_at=utcnow() - timedelta(minutes=5)))
    db.commit()
    assert refresh_with(client, laptop).status_code == 401
    assert refresh_with(client, phone).status_code == 200


def test_expired_refresh_token_is_rejected(client, db):
    raw = login(client).cookies["refresh_token"]
    db.execute(update(RefreshToken).values(expires_at=utcnow() - timedelta(seconds=1)))
    db.commit()
    r = refresh_with(client, raw)
    assert r.status_code == 401
    assert any("max-age=0" in h.lower() or "expires=" in h.lower() for h in set_cookie_headers(r))


def test_refresh_for_deactivated_user_fails(client, db):
    raw = login(client).cookies["refresh_token"]
    db.execute(update(User).where(User.email == EMP).values(is_active=False))
    db.commit()
    assert refresh_with(client, raw).status_code == 401


# ---------- logout ----------

def test_logout_revokes_the_cookie_and_clears_it(client):
    raw = login(client).cookies["refresh_token"]
    r = client.post("/api/auth/logout", headers=CSRF)
    assert r.status_code == 204
    assert any("max-age=0" in h.lower() or "expires=" in h.lower() for h in set_cookie_headers(r))
    assert refresh_with(client, raw).status_code == 401


def test_logout_requires_the_csrf_header(client):
    login(client)
    assert client.post("/api/auth/logout").status_code == 403


def test_logout_without_a_session_is_harmless(client):
    assert client.post("/api/auth/logout", headers=CSRF).status_code == 204


# ---------- brute-force throttle ----------

def test_repeated_failures_lock_the_account_on_that_ip(client):
    for _ in range(config.LOGIN_MAX_FAILURES):
        assert login(client, EMP, "wrong-password").status_code == 401
    r = login(client)  # even the right password is refused while locked
    assert r.status_code == 429 and r.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"
    assert int(r.headers["retry-after"]) > 0
    assert login(client, "priya@napho.test").status_code == 200  # other accounts unaffected


def test_successful_login_resets_the_failure_count(client):
    for _ in range(config.LOGIN_MAX_FAILURES - 1):
        login(client, EMP, "wrong-password")
    assert login(client).status_code == 200
    for _ in range(config.LOGIN_MAX_FAILURES - 1):
        login(client, EMP, "wrong-password")
    assert login(client).status_code == 200


# ---------- change password ----------

def test_change_password_revokes_other_sessions(client):
    other_device = login(client).cookies["refresh_token"]
    headers = login_headers(client, EMP)
    r = client.post("/api/auth/change-password", headers=headers,
                    json={"current_password": PASSWORD, "new_password": "Brand-new-pass-2"})
    assert r.status_code == 200 and r.cookies.get("refresh_token")
    assert refresh_with(client, other_device).status_code == 401
    assert login(client, EMP, PASSWORD).status_code == 401
    assert login(client, EMP, "Brand-new-pass-2").status_code == 200


@pytest.mark.parametrize("current,new,field", [
    ("wrong-current-pw", "Brand-new-pass-2", "current_password"),
    (PASSWORD, "short", "new_password"),
    (PASSWORD, "é" * 40, "new_password"),  # 80 bytes: over bcrypt's 72-byte limit
    (PASSWORD, PASSWORD, "new_password"),
])
def test_change_password_validation(client, current, new, field):
    r = client.post("/api/auth/change-password", headers=login_headers(client, EMP),
                    json={"current_password": current, "new_password": new})
    assert r.status_code == 422 and field in r.json()["error"]["fields"]


def test_password_rules():
    assert security.password_problem("short")
    assert security.password_problem("x" * 73)
    assert security.password_problem("        ")
    assert security.password_problem("long-enough") is None
    # a >72-byte password can never verify (bcrypt would otherwise ignore the tail)
    hashed = security.hash_password("a" * 72)
    assert security.verify_password("a" * 72, hashed)
    assert not security.verify_password("a" * 72 + "b", hashed)


# ---------- user directory (replaces the public user list) ----------

def test_user_list_is_approver_only(client, emp, apr):
    assert client.get("/api/users").status_code == 401
    assert client.get("/api/users?role=employee", headers=emp).status_code == 403
    users = client.get("/api/users?role=employee", headers=apr).json()
    assert {u["email"] for u in users} == {"aarav@napho.test", "priya@napho.test", "rohan@napho.test"}
    assert all("password_hash" not in u for u in users)
    assert client.get("/api/users?role=admin", headers=apr).status_code == 422


# ---------- configuration and CORS ----------

def test_jwt_secret_is_required_outside_dev():
    with pytest.raises(RuntimeError):
        config.resolve_jwt_secret("prod", None)
    with pytest.raises(RuntimeError):
        config.resolve_jwt_secret("prod", "too-short")
    assert config.resolve_jwt_secret("prod", "s" * 40) == "s" * 40
    assert len(config.resolve_jwt_secret("dev", None)) >= 32  # dev falls back to a random secret


def test_cors_is_credentialed_only_for_the_configured_origin(client):
    preflight = {"Access-Control-Request-Method": "POST",
                 "Access-Control-Request-Headers": "x-requested-with"}
    ok = client.options("/api/auth/refresh", headers={"Origin": "http://localhost:5173", **preflight})
    assert ok.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert ok.headers["access-control-allow-credentials"] == "true"
    evil = client.options("/api/auth/refresh", headers={"Origin": "https://evil.example", **preflight})
    assert "access-control-allow-origin" not in evil.headers


def test_old_database_schema_is_refused_with_instructions(tmp_path, monkeypatch):
    old = create_engine(f"sqlite:///{tmp_path}/old.db")
    with old.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT, role TEXT)"))
    monkeypatch.setattr(seed, "engine", old)
    with pytest.raises(RuntimeError, match="reset-db"):
        seed.check_schema()
