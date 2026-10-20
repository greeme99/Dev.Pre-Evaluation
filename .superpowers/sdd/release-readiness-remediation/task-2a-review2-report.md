# Task 2A review 2 fix

## Change

Changed RULES finding recovery in `apps/api/src/dev_pre_review/analysis/runtime.py` from a set to a multiset using `Counter`. Each finding occurrence produced by the current evaluation is paired with one persisted occurrence of the same semantic signature. Only occurrences beyond the persisted count are inserted. Existing findings are not deleted.

Added `test_same_signature_findings_from_distinct_rules_survive_replay` in `apps/api/tests/api/test_project_workflow.py`. It persists two approved numeric rules that match one DXF text region and each produce an identical `missing_numeric_value` signature. It verifies both findings are stored, then replays RULES from the prior checkpoint and verifies the total stays at two.

## RED evidence

- `.venv/bin/pytest apps/api/tests/api/test_project_workflow.py::test_same_signature_findings_from_distinct_rules_survive_replay -q` — failed as expected: the first run stored **1** finding where the two distinct rules required **2**.

## GREEN and verification

- The targeted regression test — **1 passed**, including replay with total finding count still **2**.
- Focused API, drawing, storage, export, and worker tests — **30 passed**.
- Full backend suite — **142 passed, 3 failed**. The three launcher port tests were denied loopback socket binding by the sandbox (`PermissionError: [Errno 1] Operation not permitted`).
- Backend suite excluding launcher port-binding tests — **139 passed**.
- Ruff — **passed**.
- Mypy — **passed**.
- `git diff --check` — **passed**.

## Backups

- `.superpowers/sdd/release-readiness-remediation/backups/apps/api/src/dev_pre_review/analysis/runtime.py.task2a-review2.bak`
- `.superpowers/sdd/release-readiness-remediation/backups/apps/api/tests/api/test_project_workflow.py.task2a-review2.bak`

## Concern

Only the three launcher tests that require socket binding remain unverified in this sandbox; no launcher code or tests were changed.
