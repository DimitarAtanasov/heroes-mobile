---
name: environment-facts
type: fact
updated: 2026-11-01
evidence: tool output in this session; .github/workflows/test.yml (62e4136)
---
The dev container has JDK 21, Gradle 8.14.3 (wrapper pinned), Python 3.13, Maven Central and the Gradle plugin portal. It cannot reach `dl.google.com` (Android Gradle plugin) or `nextwork.ai`.
Why: network policy of the session. The Android `:app` module therefore cannot be built here; CI on GitHub runners builds it.
How to apply: Maven Central sometimes returns HTTP 429; wait and retry, then use `gradle --offline`. Never claim the app builds until the `android-app` CI job is green. Re-check reachability before relying on this note.
