---
name: drift-tests-hide-when-skipped
type: lesson
updated: 2026-11-02
evidence: main CI runs 139 and 140 (unittest failed on test_real_report.test_matches_the_android_loader_contract after PR #10 moved LOD_NAMES into GameDataLayout.kt); fixed on branch fix/real-report-contract-test
---
A test that reads other source files by regex and skips when they are absent passes silently in a partial scratch copy and fails in CI. When you move or rename a constant, grep the tests for its name, and in verification look at the skipped count and the CI result before merging.
Why: PR #10 was verified in a copy where the test skipped; main went red on the full suite.
How to apply: before declaring a PR ready, run the full Python suite in a copy that contains ALL sources (a git archive of the branch plus the changed files, not a partial tree), and read every CI job on the PR head, not only android-app.
