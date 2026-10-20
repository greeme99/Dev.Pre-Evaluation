# Task 2B2 — Production React vertical workflow

## Status

Implemented the production React path for project creation, drawing upload, analysis polling, persisted findings, and real-job CSV export. Knowledge, rules, and settings are not exposed in the production router; their components and tests remain intact.

## Files changed

- `apps/web/src/app/router.tsx` — limit production navigation to analysis/results and retain only the latest completed findings response.
- `apps/web/src/app/router.test.tsx` — integration coverage for real API result rendering, results-tab switch, CSV job ID, and hidden mock-backed tabs.
- `apps/web/src/features/analysis/AnalysisWorkflow.tsx` — project/file inputs, sequential real API calls, bounded polling, unmount stop, and accessible error handling; cancel/retry use real API calls.
- `apps/web/src/features/analysis/AnalysisWorkflow.test.tsx` — exact project → upload → analysis → queued/running polling → findings call order; error and empty findings coverage.
- `apps/web/src/features/analysis/AnalysisWorkflow.test.tsx` — cancellation remains available while polling; a `cancelling` API response is polled to terminal `cancelled`; retry uses the real endpoint and does not create a duplicate analysis.
- `apps/web/src/features/findings/FindingsViewer.tsx` — generated contract fields, status/severity/confidence/location/evidence/suggestion rendering, bbox tuple handling, and CSV export keyed by actual job ID.
- `apps/web/src/features/findings/FindingsViewer.test.tsx` — backend field and tuple coverage, actual status filtering, and empty-result CSV coverage.

## Backups

Copied each existing edited file before changes to:

- `.superpowers/sdd/release-readiness-remediation/backups/apps/web/src/app/router.tsx.task2b2.bak`
- `.superpowers/sdd/release-readiness-remediation/backups/apps/web/src/features/analysis/AnalysisWorkflow.tsx.task2b2.bak`
- `.superpowers/sdd/release-readiness-remediation/backups/apps/web/src/features/analysis/AnalysisWorkflow.test.tsx.task2b2.bak`
- `.superpowers/sdd/release-readiness-remediation/backups/apps/web/src/features/findings/FindingsViewer.tsx.task2b2.bak`
- `.superpowers/sdd/release-readiness-remediation/backups/apps/web/src/features/findings/FindingsViewer.test.tsx.task2b2.bak`

New test and report files did not have pre-existing versions to back up.

## RED evidence

- `pnpm --filter @dev-pre-review/web test -- --run src/features/analysis/AnalysisWorkflow.test.tsx` — **3 failed, 10 passed**. All three new workflow tests failed because the current screen had no `프로젝트 이름:` input and still rendered the sample drawing selector.

## GREEN and verification

- `pnpm --filter @dev-pre-review/web test -- --run src/features/analysis/AnalysisWorkflow.test.tsx src/features/findings/FindingsViewer.test.tsx src/app/router.test.tsx` — **8 files passed, 14 tests passed**.
- `pnpm --filter @dev-pre-review/web test -- --run src/features/analysis/AnalysisWorkflow.test.tsx` after cancel/retry additions — **8 files passed, 16 tests passed**.
- `pnpm --filter @dev-pre-review/web test -- --run` — **8 files passed, 16 tests passed**.
- `pnpm --filter @dev-pre-review/contracts typecheck` — **passed**.
- `pnpm --filter @dev-pre-review/web typecheck` — **passed**.
- `pnpm --filter @dev-pre-review/web lint` — **passed**.
- `pnpm --filter @dev-pre-review/web build` — **passed**; Vite produced the production bundle.
- `git diff --check` — **passed**.
- Searched production router, analysis, and findings source for `p-demo`, `draw-001`, `draw-002`, previous mock result names, and sample drawing names — no matches.

## Cancellation regression follow-up

- Added a regression test with `cancelAnalysis → cancelling`, then `getAnalysis → cancelled`. Before the fix, the test failed with the job stuck at `취소 처리 중 (Cancelling)` after polling time advanced.
- The cancel action now resumes bounded polling for non-terminal responses. Poll run tokens prevent the previous poll from overwriting the cancel response; retry releases the request lock while polling, leaving cancellation usable and preventing duplicate start/retry actions.

## Limitations and concerns

- Polling is capped at 120 requests, one second apart by default (about two minutes). If the job does not reach a terminal state, the UI reports a timeout and leaves the real job ID visible.
- This is component/integration test evidence, not browser E2E. Controller-owned live browser/API smoke remains separate.

## Independent review follow-up

- RED — FindingsViewer tests detected the percentage based overlay against a placeholder canvas and required pixel/CAD bbox values as text.
- RED — the cancelled-job retry test failed while the retry button was available for `cancelled`; production retry is now limited to `failed`, while the start action remains available.
- RED — a pending `getAnalysis` promise resolved to `completed` after cancel and overwrote the cancelled UI when the post-request poll token guard was temporarily removed. Restoring the guard made the real pending-promise race test pass.
- The AppRouter integration test now exercises one complete mocked API-client path: project create, selected-file upload, queued → running → completed polling, findings rendering, and CSV href using the returned job ID.
- Final review verification: frontend **18/18 tests**, contracts and web typecheck, ESLint, production build, and `git diff --check` all passed.
- Backups for every edited existing file are under `.superpowers/sdd/release-readiness-remediation/backups-review/` with `.task2b2-review.bak` suffixes.

## Commit

Initial implementation: `a8c6dc31f3cf691f9ffac303dd06b0deb0e847d9`. Review follow-up commit pending.
