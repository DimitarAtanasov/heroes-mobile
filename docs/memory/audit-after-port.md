---
name: audit-after-port
type: lesson
updated: 2026-11-02
evidence: audit of checkpoints 71-72 found 6 divergences (gzip 64 MiB cap, Int overflow on legal policies, UTF-16 vs code-point sort, repr escaping); fixed in 74-75
---
Green conformance vectors do not cover what the generator never emits. After each port, run a determinism audit that reads Kotlin against Python for overflow, string ordering, division and error text, and add vectors for each finding.
Why: both ports passed their vectors and still differed on inputs the corpus never reached.
How to apply: spawn determinism-auditor after the producer reports; fix with a failing reproducer first; record unreproducible Python behaviours in the conformance spec.
