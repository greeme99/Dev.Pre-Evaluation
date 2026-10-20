# Task 2A — Real backend vertical workflow

## Status

Implemented the backend workflow for project creation, validated persistent drawing uploads, asynchronous analysis, persisted findings, and CSV export. The API integration test uses `tests/fixtures/dxf/missing-xref.dxf` and creates no database rows in advance.

## Files changed

- `apps/api/src/dev_pre_review/api/projects.py` — project creation and validated PDF/DXF upload endpoints.
- `apps/api/src/dev_pre_review/analysis/runtime.py` — production validation, parsing, approved-rule evaluation, and finding persistence handlers.
- `apps/api/src/dev_pre_review/main.py` — worker startup, interrupted-job recovery, and shutdown in FastAPI lifespan.
- `apps/api/src/dev_pre_review/api/analyses.py` — enqueue/retry wakeups and persisted `analysis_profile=rule_only`; this profile returns no generated suggestions.
- `apps/api/src/dev_pre_review/storage/files.py` — resolve a stored file from drawing hash and original filename.
- `apps/api/tests/api/test_project_workflow.py` — project/upload, full analysis/export, FileStore resolution, and interrupted-job recovery coverage.

## Backups

Created before editing each existing source file:

- `.superpowers/sdd/release-readiness-remediation/backups/apps/api/src/dev_pre_review/main.py.task2a.bak`
- `.superpowers/sdd/release-readiness-remediation/backups/apps/api/src/dev_pre_review/api/analyses.py.task2a.bak`
- `.superpowers/sdd/release-readiness-remediation/backups/apps/api/src/dev_pre_review/storage/files.py.task2a.bak`

The new runtime, projects API, test, and this report had no pre-existing files to back up.

## RED evidence

- `.venv/bin/pytest apps/api/tests/api/test_project_workflow.py -q` — 2 failed as expected; both project creation requests returned `404` instead of `201` because the required project API did not exist.
- `.venv/bin/pytest apps/api/tests/api/test_project_workflow.py::test_file_store_resolves_persisted_drawing_artifact -q` — failed with `AttributeError: 'FileStore' object has no attribute 'resolve'`.
- `.venv/bin/pytest apps/api/tests/api/test_project_workflow.py::test_missing_xref_dxf_completes_analysis_and_exports_finding -q` — failed because `rule_only` results still included generated suggestions.
- `.venv/bin/pytest apps/api/tests/api/test_project_workflow.py::test_startup_recovery_reparses_document_before_rules -q` — recovered job failed instead of completing because the in-memory parsed document was lost on restart.

## GREEN and verification

- Focused backend tests: `.venv/bin/pytest apps/api/tests/api/test_project_workflow.py apps/api/tests/api/test_analyses.py apps/api/tests/drawings/test_upload_api.py apps/api/tests/storage/test_files.py apps/api/tests/api/test_export_api.py apps/api/tests/analysis/test_worker.py -q` — **27 passed**.
- Backend tests excluding launcher port-binding tests: `.venv/bin/pytest apps/api/tests --ignore=apps/api/tests/test_launcher.py -q` — **136 passed**.
- Full backend suite: `.venv/bin/pytest apps/api/tests -q` — **139 passed, 3 failed**. The three failures are launcher tests that bind loopback sockets; this environment denied `socket.bind` with `PermissionError: [Errno 1] Operation not permitted`. The 136-test non-launcher rerun passed.
- Ruff on all changed Python files — **passed**.
- Mypy on changed production modules — **passed**.
- `git diff --check` — **passed**.

## Concerns

- The referenced `release-readiness-remediation.md` Global Constraints source was absent from `.superpowers/sdd`; the available Task 2A brief and repository `AGENTS.md` were followed.
- Three launcher tests require loopback socket binding and could not pass in this sandbox. No code changes were made to those tests or launcher behavior.
- Retrieval and generated suggestions are intentionally skipped for the identified `rule_only` profile. Findings remain persisted and exportable.
