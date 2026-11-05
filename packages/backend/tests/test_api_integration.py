"""Slidoxa native API integration tests.

Skipped automatically when SLIDOXA_PG_TEST_URL is not set so the suite
stays runnable without Docker. When set, the whole Alembic chain is
applied to the live DB and the FastAPI app is driven via TestClient.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

PG_URL = os.getenv("SLIDOXA_PG_TEST_URL")
pytestmark = pytest.mark.skipif(not PG_URL, reason="SLIDOXA_PG_TEST_URL not set")


ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


@pytest.fixture(scope="module", autouse=True)
def _reset_db():
    assert PG_URL
    # Rebuild schema from scratch for this module.
    env = {**os.environ, "DATABASE_URL": PG_URL}
    subprocess.run(["alembic", "-c", str(ALEMBIC_INI), "downgrade", "base"], env=env, check=True)
    subprocess.run(["alembic", "-c", str(ALEMBIC_INI), "upgrade", "head"], env=env, check=True)
    # Point the API's lazy engine at the test DB. The autouse conftest
    # fixture doesn't touch DATABASE_URL on purpose, so set it here.
    os.environ["DATABASE_URL"] = PG_URL
    from app.api import db as db_module
    db_module.reset_for_tests()
    yield
    db_module.reset_for_tests()
    os.environ.pop("DATABASE_URL", None)


@pytest.fixture()
def client():
    from app.api.main import app
    with TestClient(app) as c:
        yield c


# ---------- health ----------


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ---------- registration + login ----------


def test_register_login_me_logout(client):
    r = client.post("/auth/register", json={"email": "a@example.com", "password": "correct-horse-battery"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == "a@example.com"
    user_id = body["id"]
    # Cookies should now be set on the client.
    assert "ogs_access" in client.cookies
    assert "ogs_csrf" in client.cookies

    r = client.get("/auth/me")
    assert r.status_code == 200
    assert r.json() == {"id": user_id, "email": "a@example.com"}

    # Logout needs CSRF header.
    csrf = client.cookies.get("ogs_csrf")
    r = client.post("/auth/logout", headers={"X-CSRF": csrf})
    assert r.status_code == 204
    client.cookies.clear()
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_register_rejects_duplicate_email(client):
    client.post("/auth/register", json={"email": "dup@example.com", "password": "correct-horse-battery"})
    r = client.post("/auth/register", json={"email": "dup@example.com", "password": "correct-horse-battery"})
    assert r.status_code == 409


def test_register_rejects_weak_password(client):
    r = client.post("/auth/register", json={"email": "w@example.com", "password": "short"})
    assert r.status_code == 422


def test_login_rejects_wrong_password(client):
    client.post("/auth/register", json={"email": "wp@example.com", "password": "correct-horse-battery"})
    client.cookies.clear()
    r = client.post("/auth/login", json={"email": "wp@example.com", "password": "nope-nope-nope-123"})
    assert r.status_code == 401


def test_me_requires_auth(client):
    client.cookies.clear()
    assert client.get("/auth/me").status_code == 401


# ---------- provider keys ----------


def _bootstrap(client, email: str) -> str:
    client.cookies.clear()
    r = client.post("/auth/register", json={"email": email, "password": "correct-horse-battery"})
    assert r.status_code == 201, r.text
    return client.cookies.get("ogs_csrf")


def test_provider_key_roundtrip_is_encrypted_and_masked(client):
    csrf = _bootstrap(client, "k1@example.com")
    r = client.put(
        "/provider-keys",
        json={"provider": "openai", "api_key": "sk-prod-SUPERSECRET-VALUE-01"},
        headers={"X-CSRF": csrf},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "openai"
    assert body["masked_key"] == "sk-...01"
    assert "SUPERSECRET" not in r.text

    r = client.get("/provider-keys")
    assert r.status_code == 200
    rows = r.json()
    assert rows == [{"provider": "openai", "masked_key": "sk-...01"}]
    assert "SUPERSECRET" not in r.text

    # DB column stores ciphertext, not plaintext.
    engine = create_engine(PG_URL, future=True)
    with engine.connect() as c:
        stored = c.execute(text("SELECT encrypted_key FROM slidoxa_provider_key")).scalar()
    assert stored
    assert "SUPERSECRET" not in stored
    assert stored.startswith("gAAAA")  # Fernet token marker


def test_provider_key_upsert_replaces_value(client):
    csrf = _bootstrap(client, "k2@example.com")
    client.put("/provider-keys", json={"provider": "openai", "api_key": "sk-first-VALUE-0001"}, headers={"X-CSRF": csrf})
    client.put("/provider-keys", json={"provider": "openai", "api_key": "sk-second-VALUE-0002"}, headers={"X-CSRF": csrf})
    rows = client.get("/provider-keys").json()
    assert rows == [{"provider": "openai", "masked_key": "sk-...02"}]


def test_provider_key_write_requires_csrf(client):
    _bootstrap(client, "k3@example.com")
    r = client.put("/provider-keys", json={"provider": "openai", "api_key": "sk-abcd-1234"})
    assert r.status_code == 403


def test_provider_key_write_requires_auth(client):
    client.cookies.clear()
    r = client.put("/provider-keys", json={"provider": "openai", "api_key": "sk-abcd-1234"}, headers={"X-CSRF": "x"})
    assert r.status_code == 401


def test_provider_key_delete(client):
    csrf = _bootstrap(client, "k4@example.com")
    client.put("/provider-keys", json={"provider": "openai", "api_key": "sk-abc-99"}, headers={"X-CSRF": csrf})
    r = client.delete("/provider-keys/openai", headers={"X-CSRF": csrf})
    assert r.status_code == 204
    assert client.get("/provider-keys").json() == []
    # Second delete 404s.
    r = client.delete("/provider-keys/openai", headers={"X-CSRF": csrf})
    assert r.status_code == 404


def test_provider_key_ownership_isolation(client):
    csrf_a = _bootstrap(client, "iso-a@example.com")
    client.put("/provider-keys", json={"provider": "openai", "api_key": "sk-A-01"}, headers={"X-CSRF": csrf_a})
    # Log out and switch to a different user.
    client.post("/auth/logout", headers={"X-CSRF": csrf_a})
    client.cookies.clear()
    csrf_b = _bootstrap(client, "iso-b@example.com")
    assert client.get("/provider-keys").json() == []
    # B cannot delete A's key.
    r = client.delete("/provider-keys/openai", headers={"X-CSRF": csrf_b})
    assert r.status_code == 404


def test_legacy_tables_are_not_in_this_database(client):
    # Isolation sanity: the inherited Presenton `user` SQLModel table
    # must not exist in the Slidoxa database just because the API ran.
    engine = create_engine(PG_URL, future=True)
    with engine.connect() as c:
        exists = c.execute(
            text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name='user'"
            )
        ).scalar()
    assert exists == 0
