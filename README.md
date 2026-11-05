# Slidoxa

Slidoxa is a self-hosted AI presentation workspace: a FastAPI backend, a
Next.js frontend and an optional Electron desktop host that together
turn a short prompt or an uploaded reference into editable slide decks
and exportable PPTX / PDF files.

Slidoxa is derived from [Presenton](https://github.com/presenton/presenton)
and distributed under the Apache License 2.0. This repository preserves
every upstream copyright and third‑party notice; see `LICENSE`,
`NOTICE`, `ATTRIBUTION.md` and `ORIGINALITY_AND_ATTRIBUTION.md` for the
authoritative legal records. The sections below describe the Slidoxa
build and operational model — not a claim of original authorship over
inherited code.

## Features

- Generate and iteratively edit slide decks from prompts or reference
  documents.
- Pluggable LLM / image / embedding providers configured through a
  Slidoxa-owned `/provider-keys` API with Fernet encryption at rest.
- Template library with per-user customisation.
- Export to PPTX, PDF, PNG via a packaged Chromium.
- Local-first desktop runtime via Electron (no cloud required).
- Multi-user HTTP deployment via `docker compose --profile core`.

## Architecture

```
                ┌──────────────────────────────────────┐
                │  Frontend (Next.js, packages/frontend)│
                │  packages/frontend/server.js          │
                └────────────────┬─────────────────────┘
                                 │  HTTP
                ┌────────────────▼─────────────────────┐
                │  Slidoxa API (FastAPI, app/api)       │
                │  Auth, CSRF, encrypted provider keys  │
                └────────────────┬─────────────────────┘
                                 │  SQL
                ┌────────────────▼─────────────────────┐
                │  PostgreSQL 16 + pgvector             │
                │  Tables: slidoxa_user, slidoxa_       │
                │  provider_key, blackboard_entry       │
                └──────────────────────────────────────┘
                 ▲
                 │  (desktop only)
                ┌────────────────────────┐
                │  Legacy FastAPI stack   │
                │  packages/backend/app/  │
                │     legacy/             │
                └────────────────────────┘
```

Two parallel application planes share the repository:

- `packages/backend/app/api/` — Slidoxa-authored FastAPI app. New code
  lands here.
- `packages/backend/app/legacy/` — inherited Presenton FastAPI app. The
  Electron desktop currently runs this plane; it remains compatible
  with the new PostgreSQL database and the hardened desktop auth
  token.

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (standalone), React 18, Tailwind |
| Backend | Python 3.11, FastAPI, SQLAlchemy 2, pydantic v2 |
| Auth | Argon2id passwords, JWT HS256 (15 min), HttpOnly access cookie + double‑submit CSRF |
| Secrets at rest | Fernet with HKDF-SHA256 derivation, info `ogs-byok-v1` |
| Database | PostgreSQL 16, pgvector, Alembic migrations |
| Desktop | Electron 42, PyInstaller-frozen backend, bundled Chromium |
| Containers | Docker Compose, non-root UID 10001 |

## Prerequisites

- macOS (Intel/Apple Silicon) or Linux (including WSL2 on Windows).
- Docker Desktop 24+ with Compose v2.
- Node.js 22 (for local development of the frontend).
- Python 3.11 (for local backend development; the container ships with
  its own interpreter).
- `uv` (optional, for working on the inherited backend lockfile).

## Installation

```bash
git clone https://github.com/abhimarkzz/Slidoxa.git slidoxa
cd slidoxa
```

Generate a local `.env` from the template:

```bash
cp .env.example .env
python3 -c "import secrets; print('MASTER_KEY_SECRET=' + secrets.token_urlsafe(48))" >> .env
printf 'JWT_SECRET=%s\n' "$(openssl rand -base64 48 | tr -d '\n')" >> .env
printf 'POSTGRES_PASSWORD=%s\n' "$(openssl rand -hex 32)" >> .env
# Collapse duplicates so each key appears once with its real value.
chmod 600 .env
```

Never commit `.env`; `.gitignore` excludes it by default.

## Docker deployment

Boot the Slidoxa core profile only (upstream Presenton build variants
stay offline):

```bash
docker compose --profile core up --build -d db slidoxa-backend slidoxa-frontend
docker compose --profile core exec slidoxa-backend alembic -c /app/alembic.ini upgrade head
curl -sf http://127.0.0.1:8000/health          # {"status":"ok"}
curl -sf -o /dev/null -w 'frontend=%{http_code}\n' http://127.0.0.1:3000/
```

Stop with `docker compose --profile core down`. The `pgdata` volume
persists until you explicitly pass `-v`.

## Development

Backend (host):

```bash
python3.11 -m venv .venv && . .venv/bin/activate
pip install uv
cd packages/backend/app/legacy && uv sync          # inherited deps
cd ../../.. && pip install argon2-cffi PyJWT        # Slidoxa deltas
export DATABASE_URL=postgresql+psycopg://ogs:...@127.0.0.1:5432/ogs
uvicorn app.api.main:app --reload --port 8000
```

Frontend (host):

```bash
cd packages/frontend
npm install                                         # lockfile currently out of sync
npm run dev
```

Electron host (still runs the legacy stack today):

```bash
cd electron
npm install
npm run dev
```

## Testing

```bash
# Slidoxa security unit tests (crypto, auth) — no DB required.
pytest packages/backend/tests/test_crypto.py packages/backend/tests/test_auth.py -q

# Migration + API integration tests — require a disposable pgvector
# container. Never point SLIDOXA_PG_TEST_URL at a database that holds
# data you want to keep; the migration test runs `alembic downgrade base`.
docker run -d --name slidoxa-pg-test \
    -e POSTGRES_USER=ogs -e POSTGRES_DB=ogs -e POSTGRES_PASSWORD=t3st \
    -p 127.0.0.1:55432:5432 pgvector/pgvector:pg16
SLIDOXA_PG_TEST_URL=postgresql+psycopg://ogs:t3st@127.0.0.1:55432/ogs \
    pytest packages/backend/tests -q
docker rm -f slidoxa-pg-test

# Font checker (verifies 9 families + OFL licenses).
python3 tools/check_fonts.py

# Electron security suite.
cd electron && node --test scripts/*.test.cjs
```

## API overview

All Slidoxa endpoints live under the backend on port 8000. State‑
changing routes require the HttpOnly `ogs_access` cookie *and* a
matching `X-CSRF` header mirrored from the `ogs_csrf` cookie.

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | — | Liveness probe (`{"status":"ok"}`). |
| POST | `/auth/register` | — | Create a Slidoxa user; sets cookies. |
| POST | `/auth/login` | — | Password login; sets cookies. |
| GET | `/auth/me` | access | Current user. |
| POST | `/auth/logout` | access + CSRF | Clear cookies. |
| GET | `/provider-keys` | access | List configured providers (masked). |
| PUT | `/provider-keys` | access + CSRF | Upsert `{provider, api_key}`; stored encrypted. |
| DELETE | `/provider-keys/{provider}` | access + CSRF | Remove a provider's stored key. |

The inherited Presenton routes under `/api/v1/*` continue to serve the
desktop app; they enforce an independent per-launch cryptographic
desktop token with strict Host and Origin validation.

## Security architecture

- **Private files** (`/app_data/*`) are served through
  `_OwnerScopedStaticFiles`, which authorises each resolved path
  against the authenticated principal before StaticFiles returns it.
- **Desktop auth** uses a 32-byte random token generated by Electron,
  compared with `hmac.compare_digest`, and gated by strict Host +
  Origin allowlists (DNS-rebinding safe).
- **Provider keys** are encrypted at rest with Fernet (AES-128-CBC +
  HMAC-SHA256) derived via HKDF-SHA256 from `MASTER_KEY_SECRET`;
  responses never include plaintext.
- **CSRF** is enforced via double-submit cookies plus an `X-CSRF`
  header for every non‑GET Slidoxa route.
- **Containers** run as UID 10001 with a read-only root filesystem and
  a tmpfs-backed `/tmp`.

See `PHASE1_PROGRESS.md` for the full audit trail of fixes relative to
upstream (including upstream issues #972 / #973 / #974).

## Project structure

```
.
├── assets/fonts/              # OFL-licensed fonts (Plus Jakarta, Inter, JetBrains Mono, Noto)
├── docs/                      # Supplementary documentation
├── electron/                  # Electron host (desktop builds)
├── packages/
│   ├── backend/
│   │   ├── app/
│   │   │   ├── api/           # Slidoxa-authored FastAPI app
│   │   │   ├── security/      # Fernet + Argon2/JWT/CSRF primitives
│   │   │   ├── blackboard/    # Reserved for the Slidoxa shared store (phase 3)
│   │   │   └── legacy/        # Inherited Presenton stack
│   │   ├── migrations/        # Alembic (0001 blackboard, 0002 users+keys)
│   │   ├── tests/             # Slidoxa test suite
│   │   └── Dockerfile.slidoxa
│   ├── frontend/              # Next.js app (shared between legacy and new routes)
│   └── shared-schema/
├── tools/
│   ├── fetch_fonts.py
│   └── check_fonts.py
├── docker-compose.yml         # Includes upstream `production`/`development` and the new `core` profile
├── Dockerfile                 # Upstream Presenton production image
├── NOTICE                     # Upstream + third-party notices + Slidoxa modifications block
├── LICENSE                    # Apache 2.0
└── PHASE1_PROGRESS.md         # Design + verification history
```

## Licensing and acknowledgements

- Slidoxa is distributed under the Apache License 2.0; see `LICENSE`.
- Upstream origin: [Presenton](https://github.com/presenton/presenton),
  authored by the Presenton contributors. The upstream history is
  preserved in this repository; the `presenton-source` Git remote
  allows pulling future security fixes.
- Third-party notices for every bundled dependency are preserved
  verbatim in `NOTICE`; Slidoxa modifications are listed in the
  "SLIDOXA MODIFICATIONS" block near the top of that file.
- Bundled fonts are under the SIL Open Font License; each family's
  `OFL.txt` lives next to its `.ttf` files under `assets/fonts/`.
- Slidoxa-specific design, security hardening, migration and
  packaging changes are documented in `ORIGINALITY_AND_ATTRIBUTION.md`.

Contributions are welcome under the Apache 2.0 licence. See
`CONTRIBUTING.md`.
