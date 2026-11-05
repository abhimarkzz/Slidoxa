"""Slidoxa API integration tests against an explicitly configured test DB.

Set SLIDOXA_PG_TEST_URL only to a disposable PostgreSQL/pgvector database.
The fixture rebuilds that database and must never be pointed at live data.
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
EXPECTED_TABLES = {
    "workspaces", "users", "provider_keys", "presentations",
    "source_documents", "document_chunks", "evidence_facts", "slides",
    "qa_findings", "job_queue", "deck_events", "agent_runs",
}


@pytest.fixture(scope="module", autouse=True)
def _reset_disposable_db():
    assert PG_URL
    env = {**os.environ, "DATABASE_URL": PG_URL}
    subprocess.run(
        ["alembic", "-c", str(ALEMBIC_INI), "downgrade", "base"],
        env=env,
        check=True,
    )
    subprocess.run(
        ["alembic", "-c", str(ALEMBIC_INI), "upgrade", "head"],
        env=env,
        check=True,
    )
    os.environ["DATABASE_URL"] = PG_URL
    from app.api import db as db_module

    db_module.reset_for_tests()
    yield
    db_module.reset_for_tests()
    os.environ.pop("DATABASE_URL", None)


@pytest.fixture()
def client():
    from app.api.main import app

    with TestClient(app) as test_client:
        yield test_client


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_normalized_schema_has_twelve_tables_and_foreign_keys():
    assert PG_URL
    engine = create_engine(PG_URL, future=True)
    try:
        with engine.connect() as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema='public' AND table_type='BASE TABLE' "
                        "AND table_name <> 'alembic_version'"
                    )
                )
            }
            assert tables == EXPECTED_TABLES
            fk_count = connection.execute(
                text(
                    "SELECT count(*) FROM information_schema.table_constraints "
                    "WHERE table_schema='public' AND constraint_type='FOREIGN KEY'"
                )
            ).scalar_one()
            assert fk_count >= 12
    finally:
        engine.dispose()


def test_register_login_me_logout_and_personal_workspace(client):
    response = client.post(
        "/auth/register",
        json={"email": "a@example.com", "password": "correct-horse-battery"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    user_id = body["id"]
    assert body["email"] == "a@example.com"
    assert "ogs_access" in client.cookies
    assert "ogs_csrf" in client.cookies

    engine = create_engine(PG_URL, future=True)
    try:
        with engine.connect() as connection:
            workspace_count = connection.execute(
                text(
                    "SELECT count(*) FROM users u JOIN workspaces w "
                    "ON w.workspace_id=u.workspace_id WHERE u.user_id=:user_id"
                ),
                {"user_id": user_id},
            ).scalar_one()
        assert workspace_count == 1
    finally:
        engine.dispose()

    response = client.get("/auth/me")
    assert response.status_code == 200
    assert response.json() == {"id": user_id, "email": "a@example.com"}

    csrf = client.cookies.get("ogs_csrf")
    response = client.post("/auth/logout", headers={"X-CSRF": csrf})
    assert response.status_code == 204
    client.cookies.clear()
    assert client.get("/auth/me").status_code == 401


def test_register_duplicate_email_and_weak_password(client):
    payload = {"email": "duplicate@example.com", "password": "correct-horse-battery"}
    assert client.post("/auth/register", json=payload).status_code == 201
    assert client.post("/auth/register", json=payload).status_code == 409
    assert client.post(
        "/auth/register", json={"email": "weak@example.com", "password": "short"}
    ).status_code == 422


def _bootstrap(client, email: str) -> str:
    client.cookies.clear()
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "correct-horse-battery"},
    )
    assert response.status_code == 201, response.text
    csrf = client.cookies.get("ogs_csrf")
    assert csrf
    return csrf


def test_provider_key_api_returns_only_mask_and_raw_bytea_is_ciphertext(client):
    csrf = _bootstrap(client, "keys@example.com")
    plaintext = "sk-prod-SUPERSECRET-VALUE-01"
    response = client.put(
        "/provider-keys",
        json={"provider": "openai", "api_key": plaintext},
        headers={"X-CSRF": csrf},
    )
    assert response.status_code == 200
    assert response.json() == {"provider": "openai", "masked_key": "sk-...01"}
    assert plaintext not in response.text

    response = client.get("/provider-keys")
    assert response.status_code == 200
    assert response.json() == [{"provider": "openai", "masked_key": "sk-...01"}]
    assert plaintext not in response.text
    assert "encrypted_key" not in response.text
    assert "api_key" not in response.text

    engine = create_engine(PG_URL, future=True)
    try:
        with engine.connect() as connection:
            stored = connection.execute(
                text("SELECT encrypted_key FROM provider_keys WHERE provider='openai'")
            ).scalar_one()
        ciphertext = bytes(stored)
        assert ciphertext.startswith(b"gAAAA")
        assert plaintext.encode("utf-8") not in ciphertext
        assert b"SUPERSECRET" not in ciphertext
    finally:
        engine.dispose()


def test_provider_key_upsert_and_delete(client):
    csrf = _bootstrap(client, "key-lifecycle@example.com")
    first = client.put(
        "/provider-keys",
        json={"provider": "openai", "api_key": "sk-first-VALUE-0001"},
        headers={"X-CSRF": csrf},
    )
    second = client.put(
        "/provider-keys",
        json={"provider": "openai", "api_key": "sk-second-VALUE-0002"},
        headers={"X-CSRF": csrf},
    )
    assert first.status_code == second.status_code == 200
    assert second.json() == {"provider": "openai", "masked_key": "sk-...02"}
    assert client.get("/provider-keys").json() == [
        {"provider": "openai", "masked_key": "sk-...02"}
    ]
    assert client.delete("/provider-keys/openai", headers={"X-CSRF": csrf}).status_code == 204
    assert client.get("/provider-keys").json() == []


def test_provider_key_writes_require_auth_and_csrf(client):
    client.cookies.clear()
    anonymous = client.put(
        "/provider-keys",
        json={"provider": "openai", "api_key": "sk-abcd-1234"},
        headers={"X-CSRF": "not-a-session"},
    )
    assert anonymous.status_code == 401

    _bootstrap(client, "csrf@example.com")
    no_header = client.put(
        "/provider-keys", json={"provider": "openai", "api_key": "sk-abcd-1234"}
    )
    assert no_header.status_code == 403


def test_provider_key_ownership_isolation(client):
    csrf_a = _bootstrap(client, "owner-a@example.com")
    response = client.put(
        "/provider-keys",
        json={"provider": "openai", "api_key": "sk-owner-a-01"},
        headers={"X-CSRF": csrf_a},
    )
    assert response.status_code == 200
    client.post("/auth/logout", headers={"X-CSRF": csrf_a})

    csrf_b = _bootstrap(client, "owner-b@example.com")
    assert client.get("/provider-keys").json() == []
    assert client.delete("/provider-keys/openai", headers={"X-CSRF": csrf_b}).status_code == 404
