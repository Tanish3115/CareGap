# Reproducible quality and release checks

2 November 2026. All development remains local; no push, remote workflow run or external deployment is authorized.

## Python

Install runtime requirements and the separately hash-pinned `backend/requirements-dev.lock.txt`. Ruff 0.17.3 enforces the existing E4/E7/E9/F lint set and formatting across application, tests, migrations, scripts and research. Entrypoint/conftest import-order exceptions are narrowly scoped because those files establish environment/import paths before loading the application. Model-registration imports and pytest fixture reexports remain explicit. The first formatting pass verified an unchanged AST for all 161 then-existing Python files.

```powershell
backend/.venv/Scripts/python.exe -m ruff check backend/app backend/tests backend/migrations scripts research --config backend/pyproject.toml
backend/.venv/Scripts/python.exe -m ruff format --check backend/app backend/tests backend/migrations scripts research --config backend/pyproject.toml
```

Boundary types are enforced through Pydantic input/output contracts, typed SQLAlchemy relationships and TypeScript's strict compiler configuration. This is not a claim that every internal Python helper has undergone strict whole-program static type checking.

## Frontend

The supported [Node.js 22 LTS line](https://nodejs.org/en/about/previous-releases) is used for the container and CI. Biome 2.6.4 replaces the legacy ESLint/Next lint dependency graph: its React/accessibility/correctness checks, explicit form-button semantics and frontend formatting run alongside TypeScript, not instead of it. The known legacy minimatch advisory graph was removed rather than forced to incompatible major versions. The final fresh npm audit reported zero advisories; this remains a point-in-time dependency check, not a security certification.

```powershell
cd frontend
npm ci
npm run check:locales
npm run typecheck
npm run lint
npm run format:check
npm run build
npm run test:e2e
```

Biome uses its recommended preset with documented parity exceptions. Array positions are meaningful identities for source/revision rows without independent entity IDs; database resources use their actual IDs. Non-null assertions remain governed by TypeScript and surrounding checks. Missing hook dependencies are checked; extra dependencies are permitted because refresh/source-version/scope tokens deliberately invalidate authorized data. Removing those tokens as an automatic lint fix would break refresh/revocation behavior. Tailwind's configured directives are accepted without disabling other unknown CSS at-rule diagnostics.

The browser suite checks real workflows against an isolated temporary database/vault, including six-language authenticated controls, source preservation, clinician approval/revocation, historical coding review, reconciliation, study report loading and patient consultation deletion. Its axe scan covers public/authentication pages, a synthetic patient dashboard and upload dialog; keyboard/focus/Escape behavior is tested too. An independent assistive-technology audit remains required before real deployment.

`performance.spec.ts` creates 40 synthetic consultations and performs 60 reads at concurrency six, checking pagination, unique rows, access denial and a generous latency smoke threshold. It writes `bounded-load.json`; the accessibility test writes `accessibility.json` under Playwright's test output. These are repeatable workstation smoke reports, not a representative production capacity or accessibility certification.

## Privacy-safe operational output

Container Uvicorn access logging and Next development logging are disabled so clinical search strings and identifiers in URLs are not copied into ordinary terminal logs. Unexpected request exceptions return a generic 500 body and record only a generated request ID, without the exception value, URL or traceback. Upload rollback/file-cleanup assertions remain enforced under this error contract. Configure external proxies/monitoring to preserve this boundary; debug body/query logging must not be enabled on clinical traffic. The private processing subprocess stdout is an internal result channel captured by its supervisor, not an application log sink.

## Research, containers and handover

The synthetic baseline, optional locked model comparisons and registered-study fixture are reproducible without application patient data. Study inputs/outputs for approved deidentified research must remain private; only the shipped artificial aggregate is exposed by the research dashboard.

CI defines SQLite/PostgreSQL regressions, Python/frontend quality checks, synthetic evaluation, browser tests, container builds and a source-only ZIP artifact after successful test jobs. The artifact pattern is restricted to the verified ZIP/checksum files, including its explicit hidden output directory. No private environment, database, vault, backup or dependency directories are uploaded. [GitHub's artifact documentation](https://docs.github.com/en/actions/tutorials/store-and-share-data) describes that workflow mechanism; this repository has not executed a remote run during this work.

Local release commands remain in README.md, OPERATIONS.md and HANDOVER.md. Existing data volumes must be retained. A Docker build, local TLS rehearsal and passing software tests do not satisfy the clinical, native-language, external-conformance, infrastructure or independent-review gates in DEPLOYMENT_GATES.md.
