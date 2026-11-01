---
name: environment-facts
type: fact
updated: 2026-11-01
evidence: tool output in this session; .github/workflows/test.yml (3759d2f)
---
The dev container has JDK 21, Gradle 8.14.3 (wrapper pinned), Python 3.13, Maven Central and the Gradle plugin portal. It cannot reach `dl.google.com` (Android Gradle plugin) or `nextwork.ai`.
Why: network policy of the session. The Android `:app` module therefore cannot be built here; CI on GitHub runners builds it.
How to apply: Maven Central sometimes returns HTTP 429; wait and retry, then use `gradle --offline`. The `android-app` CI job is green since commit 1a34df1 and uploads `heroes-mobile-debug-apk`; check the latest run before saying the app builds. GitHub artifacts need a login to download. The full Python suite is slow (about 30 minutes on a runner) until the test-speed change lands. Re-check reachability before relying on this note.
