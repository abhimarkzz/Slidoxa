# Slidoxa — Vision

Slidoxa is an AI presentation workspace for people who want a local,
inspectable, hackable alternative to cloud slide generators. The goal
is a deck tool that respects your data, your model choices, and your
right to read the source.

## What Slidoxa is building toward

1. **Local-first by default.** Everything that can run on your own
   machine does. Cloud providers plug in, they are not required.
2. **Byo-model.** Swap OpenAI, Anthropic, Ollama, OpenRouter,
   Bedrock, local inference servers — and tomorrow's providers — by
   supplying an API key. Keys are encrypted at rest with your own
   master secret; the backend never emits plaintext, and masked
   values are what reach the UI.
3. **Honest about provenance.** Slidoxa is a derivative work of
   [Presenton](https://github.com/presenton/presenton) under the
   Apache License 2.0. We preserve upstream copyright, track
   modifications in `NOTICE`, and keep the `presenton-source` Git
   remote so we can pull upstream security fixes. Nothing in this
   repository claims inherited code as original Slidoxa work.
4. **Security that is reviewable.** Every security-relevant change
   ships with regression tests (see `packages/backend/tests/` and the
   `desktop-security` suite). The desktop crypto token, owner-scoped
   `/app_data` mount, and Fernet-encrypted provider keys are
   documented in `README.md` and `PHASE1_PROGRESS.md`.

## What we are deliberately not doing (yet)

- Replacing the inherited Next.js editor wholesale. The near-term
  Slidoxa frontend extends the existing editor rather than rewriting
  it.
- Building a hosted multi-tenant service. Slidoxa ships as a
  single-tenant deployment; multi-user support covers household /
  team use, not SaaS.
- Shipping telemetry back to any Slidoxa-operated endpoint. The code
  base has no "phone home" path.

## Roadmap pointers (non-binding)

- Phase 1 (done): security hardening, monorepo migration, Electron
  packaging, Docker production image.
- Phase 2 (done): PostgreSQL + pgvector, Alembic, Argon2 + JWT + CSRF
  auth, Fernet-encrypted provider keys, native FastAPI app at
  `packages/backend/app/api/`.
- Phase 3 (open): Slidoxa Blackboard service layer over
  `blackboard_entry` (CRUD + pgvector similarity) and a Slidoxa
  frontend surface for the new auth and provider-key APIs.

See `PHASE1_PROGRESS.md` for the full history and verified test
results.
