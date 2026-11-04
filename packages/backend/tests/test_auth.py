from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI, Depends, Response
from fastapi.testclient import TestClient

from app.security import auth


# ---------- primitives -----------------------------------------------


def test_password_hash_and_verify_roundtrip():
    h = auth.hash_password("correct horse battery staple")
    assert h != "correct horse battery staple"
    assert auth.verify_password(h, "correct horse battery staple")
    assert not auth.verify_password(h, "wrong password")


def test_verify_rejects_invalid_hash():
    assert not auth.verify_password("not-a-real-hash", "whatever")


def test_issue_and_verify_token():
    tok = auth.issue_access_token("user-123")
    principal = auth.verify_access_token(tok)
    assert principal.sub == "user-123"


def test_invalid_token_rejected():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        auth.verify_access_token("not.a.jwt")
    assert exc.value.status_code == 401


def test_expired_token_rejected():
    from fastapi import HTTPException
    # Issue a token dated 20 min ago so its 15-min TTL already lapsed.
    past = datetime.now(timezone.utc) - timedelta(minutes=20)
    tok = auth.issue_access_token("user-123", now=past)
    with pytest.raises(HTTPException) as exc:
        auth.verify_access_token(tok)
    assert exc.value.status_code == 401
    assert "expired" in exc.value.detail


def test_wrong_signature_rejected(monkeypatch):
    tok = auth.issue_access_token("user-123")
    monkeypatch.setenv("JWT_SECRET", "a-completely-different-secret-with-32-bytes-ok!!")
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        auth.verify_access_token(tok)
    assert exc.value.status_code == 401


# ---------- end-to-end dependency behaviour --------------------------


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/public/health")
    def health():
        return {"ok": True}

    @app.post("/public/login")
    def login(response: Response):
        auth.issue_session_cookies(response, subject="user-abc")
        return {"status": "ok"}

    @app.get("/protected/me")
    def me(principal: auth.Principal = Depends(auth.current_user)):
        return {"sub": principal.sub}

    @app.post(
        "/protected/write",
        dependencies=[Depends(auth.current_user), Depends(auth.csrf_guard)],
    )
    def write():
        return {"wrote": True}

    return app


def test_public_health_and_login_accessible():
    client = TestClient(_build_app())
    assert client.get("/public/health").status_code == 200
    r = client.post("/public/login")
    assert r.status_code == 200
    assert auth.ACCESS_COOKIE_NAME in r.cookies
    assert auth.CSRF_COOKIE_NAME in r.cookies


def test_protected_rejects_anonymous():
    client = TestClient(_build_app())
    r = client.get("/protected/me")
    assert r.status_code == 401


def test_protected_accepts_logged_in():
    client = TestClient(_build_app())
    client.post("/public/login")
    r = client.get("/protected/me")
    assert r.status_code == 200
    assert r.json()["sub"] == "user-abc"


def test_csrf_rejects_missing_header():
    client = TestClient(_build_app())
    client.post("/public/login")
    r = client.post("/protected/write")
    assert r.status_code == 403


def test_csrf_rejects_wrong_header():
    client = TestClient(_build_app())
    client.post("/public/login")
    r = client.post("/protected/write", headers={auth.CSRF_HEADER_NAME: "forged"})
    assert r.status_code == 403


def test_csrf_accepts_matching_header():
    client = TestClient(_build_app())
    client.post("/public/login")
    csrf = client.cookies.get(auth.CSRF_COOKIE_NAME)
    assert csrf
    r = client.post("/protected/write", headers={auth.CSRF_HEADER_NAME: csrf})
    assert r.status_code == 200
    assert r.json() == {"wrote": True}


def test_cookie_attributes(monkeypatch):
    monkeypatch.setenv("COOKIE_SECURE", "true")
    client = TestClient(_build_app())
    r = client.post("/public/login")
    raw = r.headers.get_list("set-cookie")
    access = next(c for c in raw if c.startswith(auth.ACCESS_COOKIE_NAME + "="))
    csrf = next(c for c in raw if c.startswith(auth.CSRF_COOKIE_NAME + "="))
    assert "HttpOnly" in access
    assert "HttpOnly" not in csrf  # CSRF cookie must be readable by the browser JS
    for cookie in (access, csrf):
        assert "SameSite=strict" in cookie.lower() or "samesite=strict" in cookie.lower()
        assert "Secure" in cookie


def test_missing_jwt_secret(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(auth.AuthConfigError):
        auth.issue_access_token("u")


def test_short_jwt_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "tooshort")
    with pytest.raises(auth.AuthConfigError):
        auth.issue_access_token("u")
