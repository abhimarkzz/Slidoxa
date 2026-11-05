# Originality and Attribution

This document records what in **Slidoxa** is inherited from upstream
[Presenton](https://github.com/presenton/presenton) (Apache License 2.0), what
has been modified, what has been newly developed in this fork, the licensing
obligations that remain, and the areas where further original work would
increase product independence.

Nothing in this document should be read as a claim that inherited code was
originally authored by the Slidoxa maintainers. See `LICENSE`, `NOTICE`, and
`ATTRIBUTION.md` for the authoritative legal records.

## 1. Inherited from Presenton

The following components were created by the Presenton authors and remain
substantially upstream code, with structural moves and targeted security
changes applied by Slidoxa:

- The FastAPI backend application (now at `packages/backend/app/legacy/`),
  including:
  - Presentation generation pipeline (`api/v1/ppt/`)
  - Template v2 engine, layouts, and merged components
  - Alembic migrations under `packages/backend/migrations/`
  - LLM provider adapters, image providers, Ollama integration
  - MCP server integration
- The Next.js frontend (now at `packages/frontend/`), including the editor,
  dashboard, template library, custom-template, and provider pages.
- The Electron desktop host (`electron/`), its IPC surface, resource build
  scripts, and bundled runtime layout.
- Prebuilt assets: `assets/fonts/`, `layouts.json`, `presentation-export/`,
  and the templates under `templates/`.
- The Dockerfile baseline, `start.js` process orchestrator, and the
  `docker-compose.yml` topology.
- Third-party dependencies (Python, Node, system). Their licenses are
  reproduced in full in `NOTICE` (approximately 27,000 lines).

## 2. Modified by Slidoxa

- **Repository layout.** The upstream `servers/fastapi/` and `servers/nextjs/`
  trees were restructured into a monorepo under `packages/` (`packages/backend/`,
  `packages/frontend/`, `packages/shared-schema/`). Shared assets moved to
  `assets/`. Compatibility shims and build-path updates were made in
  `Dockerfile`, `start.js`, `electron/scripts/build-nextjs-resources.cjs`,
  `electron/scripts/copy-fastapi-assets.cjs`, `electron/app/utils/servers.ts`,
  CI workflows, and the Next.js Turbopack root.
- **Authentication bypass hardening.** The `DISABLE_AUTH` escape hatch is now
  only honored when the backend also sees `PRESENTON_ELECTRON=true`, which is
  set by the Electron host and not by the Docker or web runtime. See
  `packages/backend/app/legacy/utils/get_env.py:is_disable_auth_enabled`.
  A general web client cannot opt itself into the desktop single-user mode.
- **Private storage lockdown.** The `/app_data/*` static mount is wrapped in
  `_OwnerScopedStaticFiles` (`packages/backend/app/legacy/api/v1/auth/assets.py`)
  which authorizes each resolved file against the authenticated principal
  before serving it, replacing the upstream unrestricted static mount for
  private roots.
- **Asset directory containment.** `packages/backend/app/legacy/utils/asset_directory_utils.py`
  enforces per-asset-root containment and symlink safety and adds a
  Electron-only private-root bypass that mirrors `_OwnerScopedStaticFiles`.
- **Electron packaging.** Standalone Next.js assets are copied beside the
  nested `server.js`; the bundled `node_modules` symlink was rebased to a
  relative path so packaged resources are not machine-specific.
- **NOTICE and attribution.** `NOTICE` was regenerated to add Slidoxa-specific
  modification notes while retaining every upstream and third-party notice.
  `ATTRIBUTION.md` summarises the Apache 2.0 derivation.

## 3. Newly developed in Slidoxa

- `_OwnerScopedStaticFiles` and the owner-check middleware extension that
  wraps the FastAPI static mount for private roots.
- Private-storage regression tests in `electron/scripts/private-storage.test.cjs`
  and `packages/backend/app/legacy/tests/unit/test_asset_ownership_security.py`.
- Internal auth header tests and session auth middleware tests covering the
  restricted bypass (`tests/unit/test_internal_auth_headers.py`,
  `tests/unit/test_session_auth_middleware.py`).
- Monorepo tooling: adjusted CI workflow matrices, `test-local.sh`, and the
  resource-build CJS scripts.
- Branding touchpoints: README overhaul, `VISION.md`, and this document.
- Dockerfile hardening: dev/prod split (`Dockerfile.dev`), relative standalone
  layout handling in `start.js`.

## 4. Licensing obligations retained

- `LICENSE` is Apache License 2.0, unmodified from upstream.
- `NOTICE` preserves all upstream notices and every third-party notice from
  Presenton's own `NOTICE`. Slidoxa modification notes are additive.
- Attribution of Presenton as the upstream origin is maintained in
  `ATTRIBUTION.md` and `README.md`. We do not remove upstream copyright
  headers from inherited source files, and we do not represent inherited
  code as originally authored by Slidoxa.
- Where Slidoxa changes an inherited file, the file retains the upstream
  copyright header; Slidoxa modifications are tracked in the Git history
  and summarised in this document rather than by rewriting headers.

## 5. Future work for stronger product independence

The following are candidates for original replacement in later phases. They
are listed as *options*, not commitments:

- Replace the generation pipeline with a Slidoxa-authored engine that owns
  slide IR, layout solving, and export, rather than extending the inherited
  code in `legacy/`.
- Replace the editor UI with an independent frontend; the current
  `packages/frontend/` is largely upstream.
- Independent template format and library; the inherited `layouts.json`
  and `templates/` are the clearest derivative surface.
- Replace the Electron host shell with a Slidoxa-authored packaging layer.
- Independent docs site, brand guidelines, and visual identity.

Until those replacements land, Slidoxa is best described as *a hardened,
restructured, and rebranded derivative of Presenton*, which is accurate and
compliant with Apache 2.0.
