# Task 2B1 — OpenAPI workflow contract and API client

## Status

Implemented the generated project → drawing upload → analysis → findings workflow contract and the project/upload API client calls. FastAPI OpenAPI remains authoritative; the generator emits only the workflow schemas and enums needed by the web client.

## Files changed

- `apps/api/src/dev_pre_review/api/analyses.py` — typed job state and pipeline steps as backend enums while preserving JSON values.
- `apps/api/tests/api/test_workflow_openapi.py` — workflow paths, schemas, enum references, finding fields, and request media types.
- `apps/api/tests/test_workflow_contract_generator.py` — deterministic output and mutation/drift check coverage.
- `scripts/generate_workflow_contracts.py` — standard-library generator and non-rewriting `--check` mode.
- `packages/contracts/src/workflow.ts` — generated workflow types.
- `packages/contracts/src/index.ts` — export generated workflow types and preserve unrelated contracts.
- `apps/web/src/app/api.ts` — JSON project creation and multipart drawing upload; multipart requests do not receive a forced content type.
- `apps/web/src/app/api.test.ts` — request URL, method, body, and headers coverage.

## Backups

Before editing, copied all existing files that were modified to:

- `.superpowers/sdd/release-readiness-remediation/backups/apps/api/src/dev_pre_review/api/analyses.py.task2b1.bak`
- `.superpowers/sdd/release-readiness-remediation/backups/packages/contracts/src/index.ts.task2b1.bak`
- `.superpowers/sdd/release-readiness-remediation/backups/apps/web/src/app/api.ts.task2b1.bak`

New tests, generator, generated contract, and this report had no prior files to back up.

## RED evidence

- `.venv/bin/pytest apps/api/tests/api/test_workflow_openapi.py -q` — **1 failed, 2 passed**. The expected workflow enum schemas were missing because `AnalysisJobResponse.state`, `completed_steps`, and `failed_step` were plain strings.
- `.venv/bin/pytest apps/api/tests/test_workflow_contract_generator.py -q` — **failed** because the required generator did not exist.
- `pnpm --filter @dev-pre-review/web test -- --run src/app/api.test.ts` — **2 failed, 10 passed**. Both new API tests failed because `api.createProject` and `api.uploadDrawing` did not exist.

## GREEN and verification

- `.venv/bin/pytest apps/api/tests/api/test_workflow_openapi.py apps/api/tests/test_workflow_contract_generator.py -q` — **4 passed**.
- `.venv/bin/pytest apps/api/tests --ignore=apps/api/tests/test_launcher.py -q` — **143 passed**.
- `pnpm --filter @dev-pre-review/web test` — **12 passed**.
- `pnpm --filter @dev-pre-review/contracts typecheck` — **passed**.
- `.venv/bin/python scripts/generate_workflow_contracts.py --check` — **passed**; a separate test deliberately mutated generated output and verified nonzero drift detection without rewriting it.
- Ruff on all changed Python files — **passed**.
- `.venv/bin/mypy apps/api/src/dev_pre_review/api/analyses.py` — **passed**.
- `pnpm --filter @dev-pre-review/web lint` — **passed**.
- `git diff --check` — **passed**.

## Transitional limitation

- A full `.venv/bin/pytest apps/api/tests -q` run had **146 passed, 3 failed**. All three failures are existing launcher tests that bind loopback sockets; the sandbox returned `PermissionError: [Errno 1] Operation not permitted`. Rerunning the non-launcher suite passed.
- `pnpm --filter @dev-pre-review/web typecheck` and `pnpm --filter @dev-pre-review/web build` currently fail on existing mock/stale workflow component shapes: mock severities (`critical`, `major`, `minor`) and `compliant` status differ from backend enums; findings use `rule_code`/`bbox`/`evidences` instead of `finding_type`/`location`/`pixel_bbox`/`cad_bbox`/`evidence`; suggestions and step rendering use stale fields/steps. Components were not modified per this task's ownership boundary. The parent confirmed Task 2B2 immediately adapts router, analysis, and findings UI to backend shapes; this is the intended short transition state for that next commit.

## Commit

The task-specific commit SHA is recorded in the completion handoff.
