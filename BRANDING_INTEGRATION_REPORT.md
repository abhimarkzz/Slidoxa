# Slidoxa branding integration report

Captured 2026-11-05. All work local and uncommitted.

## Files created

**Branding sources (SVG masters + script, authored last session):**
- `branding/slidoxa-icon.svg`
- `branding/slidoxa-logo-light.svg`
- `branding/slidoxa-logo-dark.svg`
- `branding/render_wordmarks.py`

**Legacy-asset backups (so upstream originals are preserved, not
destructively deleted):**
- `electron/build/legacy-presenton/icon.icns`
- `electron/build/legacy-presenton/icon.ico`
- `electron/build/legacy-presenton/icon-1024.png`
- `electron/build/legacy-presenton/logo.png`
- `electron/build/legacy-presenton/iconset/*` (10 raster entries)
- `electron/build/legacy-presenton/appx/*` (3 tile PNGs)
- `electron/build/legacy-presenton/icons/*` (7 Linux raster sizes)
- `packages/frontend/public/legacy-presenton/{logo-with-bg,logo-white,Logo}.png`
- `packages/frontend/app/legacy-presenton/{favicon.ico,icon2.png}`

**New Slidoxa web assets:**
- `packages/frontend/public/apple-touch-icon.png`
- `packages/frontend/public/site.webmanifest`
- `packages/frontend/public/slidoxa-192.png`
- `packages/frontend/public/slidoxa-512.png`
- `packages/frontend/public/slidoxa-512-maskable.png`

## Files modified

**Electron:**
- `electron/build.js`
  - `productName: "Presenton" → "Slidoxa"`
  - `copyright` rewritten to credit Slidoxa + Presenton upstream.
  - `mac.artifactName`, `linux.artifactName`, `win.artifactName` → `Slidoxa-${version}.${ext}`.
  - `win.executableName`, `nsis.shortcutName`, `nsis.uninstallDisplayName` → `Slidoxa`.
  - `win.target` → `["nsis"]` only (AppX disabled by default; see Open items).
  - `appx` block kept with upstream Presenton publisher identity + inline note explaining why it's kept and how to replace it.
- `electron/build/icon.icns` / `icon.ico` / `icon-1024.png` / `logo.png` / `icon.iconset/*` / `appx/*` / `icons/*` — replaced with Slidoxa rasters; upstream originals preserved under `legacy-presenton/`.

**Frontend assets:**
- `packages/frontend/public/logo-with-bg.png` — now the 192×192 Slidoxa app icon (used by dashboard sidebar + upload header).
- `packages/frontend/public/logo-white.png` — Slidoxa dark-surface wordmark (2400×553).
- `packages/frontend/public/Logo.png` — Slidoxa light-surface wordmark (204×47).
- `packages/frontend/app/favicon.ico` — Slidoxa multi-size favicon.
- `packages/frontend/app/icon2.png` — Slidoxa 192×192 Apple/PWA icon.

**Frontend code — alt text / titles / manifest / icons metadata:**
- `packages/frontend/app/layout.tsx` — `metadata.manifest`, `metadata.icons`, `metadata.themeColor`, `openGraph.siteName` set to Slidoxa.
- `packages/frontend/app/not-found.tsx` — title → `Page not found | Slidoxa`.
- `packages/frontend/app/(presentation-generator)/(dashboard)/admin/page.tsx` → `Admin | Slidoxa`.
- `packages/frontend/app/(presentation-generator)/(dashboard)/community/page.tsx` → `Community | Slidoxa`.
- `packages/frontend/app/(presentation-generator)/upload/page.tsx` → `Slidoxa — AI presentation workspace`.
- `packages/frontend/app/ConfigurationInitializer.tsx` — `"Loading Presenton…" → "Loading Slidoxa…"`.
- `packages/frontend/app/(presentation-generator)/(dashboard)/Components/DashboardSidebar.tsx` — `alt="Presenton logo" → alt="Slidoxa logo"`.
- `packages/frontend/app/(presentation-generator)/upload/components/GenerateHeader.tsx` — `alt/aria-label` Presenton → Slidoxa.
- `packages/frontend/components/OnBoarding/OnBoardingSlidebar.tsx` — `alt` Presenton → Slidoxa.
- `packages/frontend/public/site.webmanifest` — icon paths corrected to public-root (`/slidoxa-192.png`, etc.).

**Workflows and signing:**
- `.github/workflows/docker-release.yml` — `IMAGE_NAME` → `ghcr.io/abhimarkzz/slidoxa`.
- `electron/build.js` TEAM_ID now env-driven (`SLIDOXA_TEAM_ID` / `APPLE_TEAM_ID`); build fails fast if signed/notarized/MAS builds are requested without it.

**Repository configuration:**
- `.gitignore` extended for reproducible-build paths (previous session).
- `.dockerignore` extended for same (previous session).
- `electron/resources/export/package.json` — absolute `/Users/admin/...` dep path replaced with portable relative path (previous session).

## Electron / frontend / installer integrations

- **macOS:** `electron/build/icon.icns` + full `.iconset` are Slidoxa. `build.js` points at them; `extendInfo.ElectronTeamID` is env-driven.
- **Windows (NSIS):** installer icon, uninstaller icon, header icon, shortcut name, executable name, artifact name all rebranded. AppX left configured but off by default.
- **Linux:** `build/icons/{16,32,48,64,128,256,512}x*.png` are all Slidoxa.
- **Frontend favicon + PWA:** manifest linked, apple-touch-icon shipped, 192/512 PWA icons shipped, theme color `#0F1020`, siteName `Slidoxa`.

## Remaining Presenton references and why they remain

`grep -rn '"[Pp]resenton[^"]*"' packages/frontend/app` → ~35 matches. Each reviewed; none are user-visible Slidoxa branding. Categories:

- **Provider / enum identifiers** (`selectedProvider === 'presenton'`, `"presenton_cloud_only"`, route strings `/api/v1/auth/presenton/status`). Changing these would break backend API contract.
- **LocalStorage keys** (`"presenton.nonSotaTemplateToastDismissed"`, `"presenton:blank-slide-prompt"`, `"presenton_generate_guide_v3"`). Changing them silently invalidates persisted user state across upgrades.
- **"Presenton Cloud" product name**: a specific upstream service identifier, legitimately preserved alongside the Slidoxa brand.
- **Upstream copyright headers** in `packages/backend/app/legacy/**/*.py`. Apache 2.0 attribution — must stay.
- **TEAM_ID = "S6W5C54KL6"** (in build.js) — replaced with env-driven lookup; no hardcoded Presenton value remains.
- **AppX identityName / publisher** in build.js — kept pending Slidoxa Microsoft Partner Center registration.

## Test / build results

| Check | Result |
|---|---|
| `node -c electron/build.js` | PASS |
| `electron: tsc --noEmit` | PASS |
| Slidoxa crypto + auth tests | 24/24 PASS |
| `tools/check_fonts.py` | `OK: 12 fonts validated across 9 families; all OFL.txt files present.` |
| `docker compose --profile core config` | PASS (db, slidoxa-backend, slidoxa-frontend resolved) |
| All 6 workflow YAMLs parse | PASS |
| Secret scan over tracked files | 0 hits |
| Absolute `/Users/admin` paths in tracked code | 0 |
| Live `docker compose --profile core ps` | db healthy, backend + frontend Up |
| `/health` HTTP | 200 |
| Frontend HTTP root | 200 |

A full `next build` was not re-run this session (last successful build, 28 routes + 23 static pages, is on disk under `packages/frontend/.next-build/`; the only frontend code change since is metadata + 4 alt/title strings — trivial). Re-run with `cd packages/frontend && npm install && npm run build` before cutting the release image.

## Unresolved external signing / publisher requirements

| Requirement | Blocker | Action owner |
|---|---|---|
| macOS signed/notarized DMG | Slidoxa Apple Developer account → `SLIDOXA_TEAM_ID`, `CSC_NAME`, `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `PRESENTON_REQUIRE_MAC_SIGNING=1` | user |
| Windows AppX / Microsoft Store | Slidoxa Microsoft Partner Center publisher. Current `build.js:appx.identityName/publisher/applicationId` are still Presenton's and will not accept Slidoxa signing | user |
| Cloudflare R2 release sync | `secrets.R2_ACCESS_KEY`, `R2_SECRET_KEY`, `R2_ACCOUNT_ID` must be Slidoxa's if you want that workflow to run on release | user |
| `electron-linux-ubuntu22.yml` publishing to `presenton/presenton-export` | Repurpose or disable; currently gated to a branch name not present in Slidoxa | user |

## Commands to produce final unsigned builds

### macOS (unsigned `.app` + DMG)

```bash
# 1. Build the frozen FastAPI binary.
cd electron
npm run build:fastapi           # PyInstaller freeze, ~15–30 min

# 2. Prepare ImageMagick + export runtime (cached between runs).
npm run prepare:imagemagick
npm run build:export-runtime

# 3. Produce the unsigned .app + Slidoxa-<version>.dmg.
npm run build:electron
# Artifacts in electron/dist/mac/Slidoxa.app and electron/dist/Slidoxa-0.9.12-beta.dmg
```

### Windows (unsigned NSIS installer)

```bash
# From a Windows host (or Linux cross-build with Wine):
cd electron
npm run build:fastapi           # PyInstaller on Windows produces fastapi.exe
npm run prepare:imagemagick     # Windows ImageMagick portable vendor
npm run build:electron          # electron-builder NSIS target produces Slidoxa-<version>.exe
# Artifacts in electron/dist/
```

### Linux (unsigned AppImage + .deb)

```bash
cd electron
npm run build:fastapi           # Linux PyInstaller
npm run prepare:imagemagick     # Linux ImageMagick portable vendor (if supported by the script on Linux)
npm run build:electron          # electron-builder AppImage + deb
# Artifacts: Slidoxa-<version>.AppImage and Slidoxa-<version>.deb
```

Signed macOS / notarized builds additionally need:

```bash
export SLIDOXA_TEAM_ID=<your-apple-team-id>
export CSC_NAME="<Developer ID Application certificate common name>"
export APPLE_ID=<your-apple-id>
export APPLE_APP_SPECIFIC_PASSWORD=<app-specific-password>
export PRESENTON_REQUIRE_MAC_SIGNING=1
cd electron && npm run build:electron
```

Signed Windows (code-signing certificate) needs `CSC_LINK` + `CSC_KEY_PASSWORD` set to a `.pfx` and its password, per electron-builder docs.

## Git state

- No commits. No pushes. No tags. No branch switches.
- `.env` holds locally-generated secrets; never tracked (`.gitignore` covers it; `chmod 600`).
- `presenton-source` remote preserved for upstream security-fix pulls.
- Full history retained; 2,959 commits + upstream contributors intact.

## Live verification (2026-11-05)

### Frontend production build
```
packages/frontend $ npm install --no-audit --no-fund   # ~3 min, 757 pkgs
packages/frontend $ npm run build
```
Second iteration output:
```
✓ Compiled successfully in 20.8s
✓ Generating static pages using 15 workers (23/23) in 1779ms
```
Routes include `/apple-icon.png`, `/icon1.svg`, `/icon2.png` (Next.js
convention) all serving Slidoxa assets. `/legacy-presenton/*` ghost
route eliminated by moving the backup directory out of `app/`.

### Unsigned macOS `.app` (Slidoxa branding)
```
electron $ PRESENTON_MAC_TARGET=dir node build.js
```
Produced `electron/dist/mac/Slidoxa.app`:
```
CFBundleIdentifier: io.slidoxa.app
CFBundleName: Slidoxa
CFBundleExecutable: Slidoxa
CFBundleShortVersionString: 0.9.12-beta
Contents/Resources/icon.icns: 1024×1024 Slidoxa icon
Contents/Resources/app.asar.unpacked/resources/fastapi/fastapi: executable
```
FastAPI binary executable permissions set by `afterPack` hook; 36
unsupported native prebuild directories pruned by electron-builder as
expected.

### Verification results

| Check | Result |
|---|---|
| `node -c electron/build.js` | PASS |
| `electron: tsc --noEmit` | PASS |
| Slidoxa crypto + auth tests | 24/24 PASS |
| `tools/check_fonts.py` | `OK: 12 fonts validated across 9 families` |
| Next.js production build | PASS (28 routes, 23 static pages, 0 errors/warnings) |
| Electron dir-mode package | PASS (Slidoxa.app, io.slidoxa.app, Slidoxa icon) |
| Secret scan over tracked files | 0 hits |
| Workflow YAML syntax (6 files) | PASS |

### Residual branding fix this session

`packages/frontend/app/apple-icon.png` and `app/icon1.svg` were still
the upstream Presenton assets (previous session had missed the Next
convention-icon routes). Replaced with Slidoxa versions; upstream
copies preserved under `packages/frontend/legacy-presenton/`. Also
moved `packages/frontend/app/legacy-presenton/` (previous backup
dir) to `packages/frontend/legacy-presenton/` because any PNG under
`app/` becomes a Next.js route, producing a `/legacy-presenton/icon2.png`
ghost route.

### Remaining blockers
- **Signed macOS DMG** — requires `SLIDOXA_TEAM_ID`, `CSC_NAME`,
  `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `PRESENTON_REQUIRE_MAC_SIGNING=1`.
- **Signed Windows installer** — requires `.pfx` + `CSC_LINK`/`CSC_KEY_PASSWORD`.
- **AppX / Microsoft Store** — requires Slidoxa Microsoft Partner
  Center publisher; currently `win.target = ["nsis"]` only.
- **Cloudflare R2 release sync** + **electron-linux-ubuntu22 release**
  workflows — need Slidoxa-owned `R2_*` and `RELEASE_REPO_TOKEN` secrets.
- **Refreshed `package-lock.json`** — out of sync (direct deps OK,
  transitive drift). Dockerfile uses `npm install` as a workaround.
  Approve `npm install --package-lock-only` to re-enable `npm ci`.

## Packaged-app smoke test + DMG verification (2026-11-05)

**Launch — PASS.** Running the freshly rebuilt `Slidoxa.app`
directly:

- FastAPI frozen backend: `Application startup complete. Uvicorn
  running on http://127.0.0.1:40000`
- Next.js standalone server: `✓ Ready in 0ms` on `http://127.0.0.1:40001`
- Electron paths initialized with `userDataDir` / `appDataDir`
  rooted at `~/Library/Application Support/Slidoxa` (name reflects
  Slidoxa branding, no more `Presenton Open Source`).
- Export Chromium + ImageMagick runtimes resolved inside the
  packaged bundle.
- `GET http://127.0.0.1:40000/docs` from outside the Electron
  renderer → **401** (desktop crypto-token + Host/Origin gate
  correctly rejecting non-desktop requests).
- `GET http://127.0.0.1:40001/` from outside → **401** (same gate).
  The Electron renderer itself passes this gate automatically via
  the `x-presenton-desktop-token` header the preload script injects.
- Clean shutdown via `pkill` on `Slidoxa.app/Contents/MacOS`.

**Startup regression discovered + resolved during this test:**
earlier launches inherited a stray `DATABASE_URL` from a prior
Docker-compose shell session (`postgresql+psycopg://...@db:5432/ogs`),
and the frozen legacy FastAPI tried to migrate against that
non-existent host. Launching with a scrubbed env — `env -i HOME="$HOME"
PATH=... DATABASE_URL="" ...` — produced a clean start on the
bundled SQLite. **No code change needed**; this is only a host-env
hygiene issue when running the packaged app from a shell that has
been used for `docker compose up core`. End-user installs do not
hit this because `.app` double-click starts from a Finder-launched
LaunchServices environment that does not inherit compose env vars.
Documented so anyone smoke-testing from a Docker-active shell
remembers to `env -i` or open a fresh terminal.

**DMG build — PASS.** Produced at
`electron/dist/Slidoxa-0.9.12-beta.dmg`:
- Size: 711 MB (identical to the previous Presenton DMG size — the
  payload is the frozen backend; branding is thin by comparison).
- Format: UDIF read-only compressed (zlib), CRC32 checksum.
- `hdiutil verify` → `checksum ... is VALID`.
- Mounted contents: `Slidoxa.app` + `Applications` symlink.
- Inside `Slidoxa.app/Contents/Info.plist`:
  `CFBundleIdentifier=io.slidoxa.app`, `CFBundleName=Slidoxa`.
- Not signed, not notarized (as requested; no credentials consulted).

Previous `Presenton-0.9.12-beta.dmg` left in place beside the new
Slidoxa DMG — no artifact deleted.

**Windows NSIS packaging — not attempted.** `which wine` /
`wine64` / `wine-stable` → all absent on this macOS host.
electron-builder's Windows target requires Wine for cross-compiling
from macOS. Running the Windows build here would therefore either
fail outright or produce an installer electron-builder itself warns
about. The correct path is a Windows (or Linux-with-Wine) host:

```bash
cd electron
npm install
npm run build:fastapi         # Produces fastapi.exe on Windows
npm run prepare:imagemagick   # Windows ImageMagick portable vendor
npm run build:electron        # electron-builder NSIS target
# Output: electron/dist/Slidoxa-<version>.exe
```

No claim of a passing Windows NSIS build is made.
