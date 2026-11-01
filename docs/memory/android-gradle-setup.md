---
name: android-gradle-setup
type: lesson
updated: 2026-11-01
evidence: CI runs 41332439470 (plugin-version error), 41335348780 (BaseVariant error), 41335738899 (green); commits 86755dc, 1a34df1
---
Declare Gradle plugin versions once in `android/settings.gradle.kts` (pluginManagement.plugins), and put the Android Gradle plugin on the ROOT build's buildscript classpath, only when `-PwithApp=true`.
Why: two real CI failures. A version declared in both the root and `app` gave "plugin is already on the classpath with an unknown version". With the Android plugin only loaded in the app module, the Kotlin Android plugin could not see `com.android.build.gradle.api.BaseVariant` (different class loaders).
How to apply: never add a version to a module's `plugins {}` block; keep the default build (`:sim` only) free of Google Maven so it works in the dev container; verify any `:app` change by reading the `android-app` CI job, since it cannot be built locally.
