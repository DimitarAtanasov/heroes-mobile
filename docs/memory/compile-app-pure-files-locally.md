---
name: compile-app-pure-files-locally
type: lesson
updated: 2026-11-02
evidence: lead wiring of checkpoint 81 (GameController, Engine, Presets, SaveFiles compiled inside :presenter in /tmp/w_wire)
---
The :app module cannot compile here, but its Android-free files can: copy them into a scratch :presenter source dir and run `gradle --offline :presenter:compileKotlin`. Only Compose files and MainActivity then wait for CI.
Why: it catches signature mismatches in GameController and the save code before a CI round is spent.
How to apply: do it in a scratch copy (never commit the copy); keep new app logic in Android-free files so this works.
