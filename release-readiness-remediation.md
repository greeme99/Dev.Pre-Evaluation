# Release Readiness Remediation Plan

**Date:** 2026-10-21 (Asia/Seoul)

## Goal

Bring the repository from a tested scaffold to an honestly documented, executable local MVP whose primary workflow is backed by real API calls and release evidence.

## Global Constraints

- Preserve the current architecture and dependencies unless a task explicitly proves a new dependency is necessary.
- Use TDD for production-code behavior changes: add a focused failing test, confirm the expected failure, implement the minimum fix, then run the focused and related suites.
- Do not keep mock-success fallbacks in production UI paths.
- Do not claim a quality, Windows, privacy, model, or E2E gate without executable evidence.
- Keep the application loopback-only and local-first. No production deployment or external service call is authorized.
- Back up every existing file before editing it under the plan workspace `backups/` directory using the same filename plus `.bak`.
- Preserve user changes and avoid unrelated refactors, dependency additions, or formatting churn.

## Task 1: Restore documentation truthfulness

- Mark the current golden metrics and Windows E2E/MVP completion claims as unverified or partial.
- Align Node.js and test-count guidance with executable configuration and current collection.
- Add an implementation-status matrix distinguishing Implemented, Partial, Planned, and Verified.
- Align model-license documentation with the manifest while explicitly marking placeholder/unverified assets.

**Acceptance:** Documentation no longer states that real golden, Windows E2E, offline model, or complete workflow gates passed without evidence.

## Task 2: Complete one real vertical workflow

- Add the minimum project and persistent drawing APIs needed to create a project, upload a validated drawing, and create an analysis job.
- Wire the single-job runner/worker into FastAPI lifespan with startup recovery, enqueue/retry notification, and clean shutdown.
- Ensure the job progresses through real validation/parsing/rule evaluation and persists findings; unsupported portions must fail honestly rather than report success.
- Connect the production React router to real APIs for the workflow and remove mock-success fallbacks from production paths.
- Add one browser/API integration path covering project creation, upload, analysis polling, findings retrieval, and CSV export at the appropriate available test level.

**Acceptance:** A production-path request can create a project, persist a fixture drawing, complete an analysis, retrieve persisted findings, and export CSV without seeded database rows or mock UI results.

## Task 3: Enforce contracts and data integrity

- Make FastAPI OpenAPI the contract source or add an equivalent deterministic generation/check command using existing dependencies.
- Align TypeScript types and API client routes with backend schemas and fail CI on drift.
- Store server-side import preview state or reparse the verified source on commit; never commit only the five sample rows or trust client-supplied preview/hash as authority.
- Fix analysis version handling, cancellation boundaries, and project/drawing ownership validation with real SQLite integration tests.
- Use one application data-path implementation for database and artifacts.

**Acceptance:** Six or more Excel rows import completely; tampered preview data is rejected; contract drift is detected; SQLite pipeline and cancellation regression tests pass.

## Task 4: Make the Windows release path executable

- Resolve bundled web assets automatically in frozen execution and serve the SPA from `/`.
- Use the real `/api/health` endpoint with strict product identity for single-instance detection.
- Include and locate Alembic migrations in the packaged application.
- Extend Windows CI to install or unpack, launch, health-check, load the UI, and exercise a minimal workflow before publishing artifacts.

**Acceptance:** The workflow contains an executable Windows smoke/E2E gate, and local packaging configuration contains all runtime assets needed by the launcher.

## Task 5: Replace synthetic gates and add security hardening

- Replace the answer-echo golden evaluator with an evaluator that consumes actual pipeline outputs; refuse to report product metrics when no real evaluator is configured.
- Record build, environment, manifest, and version evidence in generated reports.
- Escape spreadsheet-formula prefixes in CSV/XLSX exports.
- Add bounded streaming restore input and XLSX archive safety checks.
- Add loopback Host/Origin or per-run mutation protection using existing platform capabilities, proportionate to the single-user local threat model.
- Validate model manifest assets and keep unavailable models explicitly non-operational rather than silently successful.

**Acceptance:** Golden commands cannot produce perfect product metrics by echoing expected values; malicious spreadsheet cells are inert; oversized restore/archive inputs fail safely; security checks have regression tests.

## Task 6: Final verification and independent review

- Run backend tests, Ruff check/format, mypy, frontend tests, ESLint, TypeScript typecheck, production build, contract drift check, and real/smoke evaluation commands.
- Independently review the complete branch for spec compliance, regressions, security, and unnecessary complexity.
- Update documentation status only from fresh verification evidence.

**Acceptance:** All available gates pass with recorded commands; Windows-only items remain explicitly unverified unless the Windows workflow provides evidence.
