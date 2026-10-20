# Task 2A review fixes

## Status

Both independent review findings are fixed in a separate commit over `070c8f5`.

## RED evidence

- `.venv/bin/pytest apps/api/tests/api/test_project_workflow.py::test_cancelling_running_analysis_keeps_worker_alive_for_next_job -q` — failed as expected. The cancel API returned a terminal cancellation while the worker was blocked in validation; after release, the worker raised `InvalidStateTransition` while completing the step and never processed the next queued job.
- `.venv/bin/pytest apps/api/tests/api/test_project_workflow.py::test_recovery_after_rule_findings_saved_does_not_duplicate_or_delete_findings -q` — failed as expected. Simulating the persisted RULES result before its job checkpoint, recovery produced two `quality_blocked` findings instead of one.

## Changes and design choices

- `apps/api/src/dev_pre_review/api/analyses.py`: when a worker is attached, cancellation now calls `JobRunner.cancel()` and wakes the worker. A running job remains `cancelling` until the worker reaches its step boundary; queued cancellation is still immediately terminal. The no-worker compatibility path keeps its prior immediate confirmation behavior.
- `apps/api/src/dev_pre_review/analysis/runtime.py`: RULES replay compares semantic finding signatures (verdict, severity, confidence, type, location, message, bounding boxes, and evidence) against persisted job findings and adds only missing signatures. This avoids deleting any existing user or other-stage finding and remains safe across the add-before-checkpoint crash window.
- `apps/api/tests/api/test_project_workflow.py`: added deterministic worker cancellation/queue-drain coverage and SQLite recovery coverage with an existing rule finding plus a separate finding that must remain untouched.

## Backups

- `.superpowers/sdd/release-readiness-remediation/backups/apps/api/src/dev_pre_review/api/analyses.py.task2a-review.bak`
- `.superpowers/sdd/release-readiness-remediation/backups/apps/api/src/dev_pre_review/analysis/runtime.py.task2a-review.bak`
- `.superpowers/sdd/release-readiness-remediation/backups/apps/api/tests/api/test_project_workflow.py.task2a-review.bak`

## GREEN and verification

- Focused suite: `.venv/bin/pytest apps/api/tests/api/test_project_workflow.py apps/api/tests/api/test_analyses.py apps/api/tests/drawings/test_upload_api.py apps/api/tests/storage/test_files.py apps/api/tests/api/test_export_api.py apps/api/tests/analysis/test_worker.py -q` — **29 passed**.
- Full backend suite: `.venv/bin/pytest apps/api/tests -q` — **141 passed, 3 failed**. The three failures are existing launcher tests that require loopback socket binding; the sandbox returns `PermissionError: [Errno 1] Operation not permitted` at `socket.bind`.
- Backend suite excluding launcher port-binding tests: `.venv/bin/pytest apps/api/tests --ignore=apps/api/tests/test_launcher.py -q` — **138 passed**.
- Ruff on changed Python files — **passed**.
- Mypy on changed production modules — **passed**.
- `git diff --check` — **passed**.

## Concerns

Full backend validation remains limited by the sandbox's loopback socket restriction. No launcher code or tests were changed.
