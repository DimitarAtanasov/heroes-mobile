---
name: pin-literals-not-constants
type: lesson
updated: 2026-11-02
evidence: checkpoint 80 (manual-save cap 999 changed to 998 survived every test until a literal-boundary test was added)
---
A test that reads the constant it checks cannot fail when the constant is wrong. Pin boundaries with literals (999 accepted, 1000 refused) in at least one test.
Why: the lead mutation of `MAX_MANUAL_NUMBER` passed 16 tests because they all used the constant.
How to apply: when you mutate a new module, include its named limits (caps, thresholds, sizes), not only its logic.
