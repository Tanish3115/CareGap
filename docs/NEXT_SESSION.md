8 November 2026 current state: persistent-data hosting is reachable at https://caregap360.vercel.app. Frontend/API, hosted admin login/session/logout, Supabase schema/private-file upload/download/anonymous denial and Redis checks passed. The test storage object was removed. Private settings and administrator credentials remain under ignored `.tools/hosting/20261107T181040Z/`; never publish them. No existing local data migration or Render-restart persistence test has been performed. See the current note in HOSTING_HANDOVER.md before the historical handoff below.

7–8 November publication instruction: the user explicitly authorized pushing the project to the existing GitHub repository. This supersedes earlier no-push restrictions for reviewed current application source on `main`. Preserve remote history and the existing demo branch. Do not publish credentials, patient records, databases, backups or generated archives. Commands and meanings are in GITHUB_COMMANDS.md.

Historical hosting hold: hosting preparation remains in docs/HOSTING_HANDOVER.md, private setup under .tools/hosting/20261102T171812Z and the backup under .tools/backups/20261102T172123Z-97e0163c.

5 November 2026 recovery: restored altered source files from the verified 2 November source archive (SHA-256 0b9d4c63f8540ebe6abcc02174b9f490c897e178ef6b1fe07ed1ddfb3b843f1f), then reapplied the later detail-navigation update. The pre-restoration source backup and exact restored-file list are in .tools/recovery/20261105T092939Z/. No patient database, document vault or private environment was restored or changed. Docker Desktop was stopped during recovery; no container restart or cloud deployment was performed.

Latest UI change: detail/history buttons now scroll to and focus the requested content after it renders, including consultations/follow-ups, clinical records, medication reports, transcription/prescription histories, timeline sources, care extracts and organization evidence. Shared helper: frontend/src/lib/useDetailNavigation.ts. It respects reduced motion and scopes targets to their own workspace. Desktop/mobile destination-focus regression and sidebar regression passed; the existing consultation/source/correction/follow-up browser flow also passed. Type checking, lint and formatting passed. No cloud changes or push.

# CareGap 360 — next-session handoff

**Historical 2 November push scope:** the verified source-only `deploy/free-demo` branch was authorized and published. The later 7 November instruction above supersedes its restriction on current application source publication to main.

The user subsequently authorized continuing with the explained separate deployment branch. The reviewed source-only bundle was published to `deploy/free-demo` at `eab722725ae00379fc9ccde3743e987d7212fbd4`. Main/master were verified unchanged; no runtime credentials, patient files or databases were published. This is an exception for that deployment branch, not authorization to push main or unrelated work. Public Render deployment is still pending account access.

Branch: https://github.com/Tanish3115/CareGap/tree/deploy/free-demo

Direct Render setup: https://render.com/deploy?repo=https%3A%2F%2Fgithub.com%2FTanish3115%2FCareGap%2Ftree%2Fdeploy%2Ffree-demo


Updated: 2 November 2026, Asia/Calcutta. Local engineering closure is documented in MASTER_PROMPT_CHECKLIST.md against all 22 master-prompt sections. Read HANDOVER.md for final verification and DEPLOYMENT_GATES.md for external approvals. No commit or push.

## Objective and specification

Continue implementing the supplied CareGap 360 master prompt milestone by milestone, preserving a working application. The product is a patient-controlled longitudinal health-record and care-continuity platform, eventually including prescription extraction, medication reconciliation, care-gap analytics and clinician-reviewed intervention support.

The original master prompt attachment was provided at:
`C:/Users/tanis/.codex/attachments/b889c31d-7976-471a-92bb-25ee9d803e80/Pasted text.txt`.

Read `README.md`, `docs/PROGRESS.md`, `docs/ARCHITECTURE.md` and `docs/ROADMAP.md` before continuing. `docs/PROJECT_REVIEW.md` is a historical review; many listed defects were subsequently fixed.

## Current state

Latest steering and checkpoint: use free alternatives; user has no host/domain. Render Free one-container demo is prepared and tested locally at http://127.0.0.1:3600; no Render account/connection or public URL exists. The browser host was unavailable and native Edge control was denied, so account setup remains a user step. Preserve the no-push instruction and obtain explicit permission before publishing current verified source to any GitHub deployment branch. The normal app at http://localhost:3300 retains its records on schema `0019`. Approved-knowledge and extraction-evaluation adapters are executable but clinical data/reviews remain external. Latest checks: SQLite 270, PostgreSQL 271; eleven regression browser flows plus one corrected focused knowledge flow; 27 focused module tests; quality 175 Python/42 frontend files and 1003 locale keys. See HANDOVER.md, APPROVED_KNOWLEDGE.md, EXTRACTION_VALIDATION.md and infra/free-demo/README.md.

Latest deletion milestone supersedes older counts/schema below: migration `0019`, durable file-cleanup service and confirmed patient-owned deletion of documents, consultations, individual follow-ups, medication reports and structured records. Read RECORD_DELETION.md before changing dependency/erasure behavior. Final checks: SQLite 243, PostgreSQL 244, browser 11, Linux deletion/migration 18; Ruff 168 files, Biome 41 files, types/locales and all image builds passed. Catalogs cover 997 keys. Both local stacks are refreshed; original three sources and record counts are preserved. Pre-migration backup `.tools/backups/20261102T144553Z-723525b6` is verified. No existing application deletion, commit or push. External gates remain open.

The latest interface request is complete: use role-specific sidebars and focused sections instead of stacking all features. The normal local frontend has been refreshed; read INTERFACE_NAVIGATION.md. Ten browser flows, expanded accessibility scopes, frontend quality/types/locales and the production build passed. Preserve draft state across section navigation and retain existing capability/source keys.

Latest steering: configurable integrations with local test modes and exactly Kannada, Telugu, Tamil, Malayalam, English and Hindi, with 1003 interface keys in every translated catalog. Clinical/source text remains verbatim. Offline source-bound terminology review, registered-study synthetic diagnostics, provider abstractions and quality/privacy fixes are complete. Runtime migrations remain `0018`. Read PRIVACY_ERASURE.md before any operator use; no real erasure was executed.

Final verification on 2 November 2026: SQLite 225 passed/five environment skips; PostgreSQL 226 passed/four skips with clean migration/model comparison; all ten browser flows passed; Linux OCR five passed. Ruff lint/format passed for 162 Python files, Biome lint/format for 39 frontend source files, TypeScript and all six locale checks passed (1003 reference keys). Production container builds passed. The complete npm dependency audit reported zero advisories. The optional model comparison reproduced its artifact byte-for-byte. Accessibility checks found zero violations in the tested public and synthetic patient/upload screens; the bounded synthetic concurrent-read smoke recorded p95 261 ms over 60 requests at concurrency six. These are scoped development checks, not independent clinical, accessibility or production-capacity certification.

Both local stacks are healthy on schema `0018`; application http://localhost:3300. The final isolated HTTPS/certificate/Secure-HttpOnly-session/source/isolation/logout/shared-Redis smoke passed. Current records preserve five users, three documents, one consultation, four grants and four requests, including the newer grant/request. All three original source hashes match stored checksums and the retained prior backup. Fresh backup `.tools/backups/20261102T122418Z-fd76d347` has verified artifact hashes; no application S3 objects require a provider snapshot at this checkpoint. Zero application erasures, commits or pushes were performed.

The remaining entries below are historical implementation context; their older verification counts do not supersede this checkpoint.

- Functional account, patient-profile, document-vault, patient-consent and source-linked clinical-record application. The full master-prompt scope remains incremental; no measured completion percentage is claimed.
- Next.js 16.4.3 / React 19 frontend; Python 3.12 / FastAPI / SQLAlchemy backend; PostgreSQL in Docker; local filesystem document storage.
- Registration/login, HttpOnly cookie sessions, server-side session revocation, role restrictions, origin checks and rate limiting.
- Validated PDF/JPG/PNG upload, private authenticated downloads, checksum verification, ownership/consent enforcement and audit events.
- Doctor verification, access requests, patient approval/denial, document-category and selected-record scopes, explicit upload permission, expiration and revocation.
- Basic patient, doctor and operational administrator workspaces.
- Source-linked consultation notes, chronological document/consultation timeline, attributed correction history, stale-edit protection and consultation-linked follow-up tasks/outcomes.
- Permanent patient-owned consultation deletion with current-version protection and confirmation; removes note/task histories, retains original uploads and metadata-only deletion audit. No public entered-in-error controls/routes/filters remain. Its legacy migration column stays for compatibility.
- Durable SQL-backed jobs, exclusive five-minute leases, bounded retries and a separate worker. Upload enqueue is transactional. PDF text plus local Tesseract/Poppler OCR run in a supervised subprocess. Results remain unverified with page/confidence/uncertainty details. Older source-text-v1 results can be explicitly reprocessed with source-ocr-v2.
- Private S3 SDK adapter and per-document backend routing preserve existing local files. Local remains the default. Optional MinIO is built from official pinned source, because upstream public images were unavailable. Credentials are generated only into ignored configuration; actual S3 checks use an isolated synthetic bucket.
- Source-transcription review API/UI with source confirmation, immutable versions, processing snapshots and stale-edit protection. Doctor reads/writes also require clinical read/write consent; document-only grants do not expose human review text. Reviews do not set clinical/medication verification automatically.
- Separate explicit clinical read/write consent, disabled for old document grants. Clinical sharing requires unrestricted all-category document consent and includes revision history. Document upload remains a separate action. Patient corrections are patient-reported, retaining prior clinician entries.
- Source-bound prescription draft API/UI, conservative explicit-label candidates and manual passage editing. Every supplied field must match its exact Unicode source span. Only a verified clinician with clinical write consent can confirm historical prescription entries; missing values remain null with clarification flags. Prior revisions remain retained. This does not establish current medication use, issue orders or validate doses.
- Patient-owned medication-use reports and corrections, with optional historical-prescription comparisons. Clinicians can append separate reconciliation assessments under clinical write consent. Report/source versions bind each assessment; later changes flag it as stale. Offline exact-alias terminology proposals now require explicit review; no automatic prescribing, current-use verification or safety claims.
- Typed diagnoses/allergies/labs, appointment/referral/test outcomes, clinician decisions on rescheduling, separate clinician-recorded medication events and version-bound interventions. Clinical source/author/ownership relationships remain explicit; missing values stay missing.
- Care worklist, six-language local mock channel deliveries/preferences/history, exact source-linked overview, literal medication comparisons, synthetic safety fixtures, bounded FHIR preview/import/export and immutable original JSON sources. No real messaging, clinical safety provider or LLM summary is configured.
- Actual reproducible synthetic logistic baseline and held-out evaluation artifact, artificial-case UI, descriptive intervention event/outcome extracts and research protocol. No patient risk scoring or causal-effect model.
- Verified organization metadata/memberships, institution-bound grants checked on every read, account deactivation/session revocation, operational metrics, patient-owned data extracts and privacy review requests. Erasure requests do not execute data deletion.
- Alembic migrations through `0018`; Docker worker includes Tesseract, Poppler and a read-only vault mount. Dependencies, including the new Redis client, are hash-locked with existing versions preserved. See latest progress for runtime verification.
- No default administrator credentials. Administrators are provisioned explicitly with the CLI documented in README; do not invent credentials or expose secrets.

## User's latest ID preference

Patient-facing sharing IDs must be **one uppercase letter followed by three digits**, e.g. `A123`, `B007`, `A000`.

- The patient dashboard displays this short ID.
- The clinician input shows `e.g. A123`, validates four characters, and normalizes the letter to uppercase.
- Internal UUIDs and document/consent relationships remain unchanged. The API still accepts UUIDs for backward compatibility.
- The namespace has 26,000 unique codes. Allocation handles collisions, scans remaining free slots and rejects exhausted capacity without leaving a partial account.
- Migration `0004` converted existing sharing codes; live checks found zero invalid codes and zero orphaned documents.

Previous ID checkpoint: `3289979`. GitHub repository: `https://github.com/Tanish3115/CareGap`; local `master` tracks `origin/main`. Use `git log -1` for the latest milestone checkpoint.

## Latest verification

- 1 November extension: full SQLite initially 150 then 152 passed (five environment skips); full PostgreSQL 151 passed (four skips), plus 23 final targeted PostgreSQL checks with clean migration/model comparison. Full six expanded browser tests passed, plus a focused final care/mobile run. Two initial implicit select-label failures were corrected using explicit labels without weakening assertions. Lint/types and final production builds passed. The synthetic restore and isolated TLS/shared-Redis/cookie/isolation/logout smokes passed; latest final SQLite results are in PROGRESS.md.
- Final full SQLite: 155 passed/five skips. Final mobile clinical/worklist screenshots were inspected; no horizontal overflow. All three original local source hashes and backup manifests were verified. Final input/logging guard: clinical/FHIR/operational NUL values are rejected before PostgreSQL; SQL parameters are hidden in exception output. Its 37 focused SQLite tests passed; see latest progress for PostgreSQL completion.
- Final input/logging guard also passed 37 focused PostgreSQL tests and migration/model comparison. Backend/worker final images rebuilt; both local stacks are healthy. Readiness explicitly checks schema `0014`; update that check intentionally when adding future migrations. Final UI refinements and the source-download/terminology fields are in the built frontend image.
- Medication-use milestone: SQLite 129 passed/five skipped; PostgreSQL 130 passed/four skipped and clean migration/model comparison. Final focused medication tests passed. All six browser tests passed, covering patient correction/history, source comparison, clinician discrepancy review, stale reviews and revoked access. Mobile layout inspected; lint/types and production Docker builds passed. Runtime schema `0010`, existing aggregate counts preserved and readiness/routes checked. See PROGRESS.md.
- Prescription milestone: full SQLite 122 passed/five skipped; full PostgreSQL 123 passed/four skipped, with clean migration/model comparison. Seven focused prescription tests passed, including two added after the full suites. All six browser tests passed with patient drafting, clinician confirmation and post-revocation denial. Mobile draft form inspected with no horizontal overflow; lint/types passed. Latest build/runtime results are in PROGRESS.md.
- Full SQLite: 116 passed, five environment-specific checks skipped. Full PostgreSQL: 117 passed, four external/OCR checks skipped; migration/model comparison passed. A later targeted production-S3-TLS guard test also passed.
- Linux OCR suite: five passed, including real printed-image and scanned-PDF OCR; supervised OCR worker subprocess smoke passed. Live MinIO: two tests passed in a unique synthetic bucket, then that bucket was deleted. No application objects were accessed.
- All six browser tests passed, plus the final focused mobile transcription-review flow with inspected screenshot and no horizontal overflow. Review edits/history/source checks are covered. Processing/review assertions reuse the upload/login flow so the unchanged login throttle is respected. Use normal Windows permissions for browser teardown.
- ESLint, TypeScript and Docker production builds passed.
- This milestone's browser tests caught implicit form labels incorporating prefilled textarea/option/help text. Explicit label associations fixed exact accessible-name matching without weakening the assertions. A previous milestone added route precompilation for cold starts; preserve it.
- Known maintenance notice: Starlette's httpx-based TestClient emits a deprecation warning; tests currently pass.

Do not rerun checks merely to repeat old results. Run the checks appropriate to the next changes.

## Running and testing

Last verified application URL: `http://localhost:3300`.
API documentation: `http://localhost:8001/docs`.
API readiness: `http://localhost:8001/ready`.
PostgreSQL host port: `55432`.

Check actual runtime state next session; do not assume containers remained running.

```powershell
docker compose up -d
docker compose ps
```

Working host interpreter: `backend/.venv/Scripts/python.exe`. The old `backend/venv` points to a missing interpreter and was preserved. A workspace-local Python runtime also exists under ignored `.tools/python`.

Backend tests, from `backend`:

```powershell
.venv/Scripts/python.exe -m pytest -q
```

PostgreSQL regression, from the repository root:

```powershell
backend/.venv/Scripts/python.exe scripts/check_postgres.py
```

This creates and removes only a uniquely named synthetic test database. Never point destructive test fixtures at real clinical data.

Frontend checks, from `frontend`:

```powershell
npm run lint
npm run typecheck
npm run test:e2e
```

Read `frontend/AGENTS.md` and relevant installed Next.js documentation before frontend changes. Browser tests use isolated ports 3100/8100 and disposable synthetic data. `.next-e2e` isolates their build output.

## Data and environment preservation

Latest verified state: migration `0015`, normal app http://localhost:3300 with readiness 200, eight table fingerprints unchanged (five users/three documents/one encounter/three grants/three requests). Latest backup is `.tools/backups/20261101T100130Z-a1f8d5ef`; artifact and all three original-source hashes verified. Both local stacks were refreshed and the certificate/session/isolation/Redis smoke passed. Full regressions: SQLite 164 passed/five skips; PostgreSQL 165 passed/four skips; final scope guards 48 passed on each engine; final migration preservation test passed. All six expanded browser tests, lint/types and production images passed. These supersede the older checkpoint numbers below. No commit/push.

- The original `backend/caregap360.db` was not modified; the running application uses PostgreSQL.
- Existing Docker accounts, sessions and uploaded files were preserved through ID migrations.
- Root `.env` and `backend/.env` contain generated local secrets and are ignored. Do not print or commit them.
- Latest backup is `.tools/backups/20261101T080053Z-d6c68204` with PostgreSQL dump, local-vault archive and manifest; all three original file hashes were verified. Older container backups remain. Migration `0014` is applied; normal app services are healthy with unchanged counts (five users, three documents, one encounter). A separate `caregap-staging` project runs loopback TLS/Redis with independent volumes and synthetic smoke users. Its `.tools/staging.env` and CA file are ignored. Do not change Windows trust or conflate this development rehearsal with production certification. Verify runtime next session; never remove volumes or restore over live data casually.
- An ignored `backend/wheelhouse` holds verified Linux wheels because dependency downloads were slow. Docker can install these offline with required hashes. Fresh checkouts download from locked requirements normally.
- Git operations need the existing safe-directory override and may require filesystem escalation. Do not include `.env`, patient files, virtual environments, `.tools`, generated build output or wheel binaries in commits.

## Resume here

The latest local milestone adds nine clinical resource groups, patient narrowing, independently calculated read/write permissions and a combined current-record timeline. Backend aggregates, raw FHIR sources, prescription screens and all source/history routes enforce these groups. Migration `0015` preserves existing clinical coverage as explicit snapshots and leaves document-only grants unchanged. Missing/malformed scopes fail closed. Downgrade disables restricted permissions rather than broadening them. Read CONSENT_SCOPES.md for the all-document disclosure and precise boundaries.

Remaining gates: obtain native-language medical review; extend evaluated extraction/terminology and external FHIR conformance for the approved receiving system; configure approved live providers; obtain representative approved outcomes and independent reviews; establish managed encryption/infrastructure and provider/backup retention procedures. The local erasure tool requires an independently approved policy and is not full production erasure assurance. These are not completed by synthetic tests. Read CLINICAL_EXTENSIONS.md, RESEARCH_EVALUATION.md, DEPLOYMENT_GATES.md and ROADMAP.md. Preserve missing values, source provenance, patient-owned consultation deletion and the working application. No push is authorized.
