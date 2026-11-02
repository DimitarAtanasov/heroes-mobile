# Project memory (second brain)

Index of notes in this directory. Read this first, open what matches the task, and check any
named command or file before relying on it. See `.claude/skills/second-brain/SKILL.md`.

- [clean-copy-verification](clean-copy-verification.md) - verify from `git archive HEAD` plus owned files only
- [agent-reports-are-claims](agent-reports-are-claims.md) - reproduce results; mutate new code once
- [parallel-agent-ownership](parallel-agent-ownership.md) - disjoint files, private copies, lead wires shared files
- [environment-facts](environment-facts.md) - JDK/Gradle/network limits; Android app builds only in CI
- [owner-preferences](owner-preferences.md) - Kotlin + GPL, usage lines 95/98, commit verified pieces only
- [vcmi-is-evidence](vcmi-is-evidence.md) - VCMI facts and ported code: evidence, provenance, policies
- [golden-hash-discipline](golden-hash-discipline.md) - re-pin rule and the Python/Kotlin contract
- [android-gradle-setup](android-gradle-setup.md) - plugin versions once in settings; AGP on root classpath; verify via CI
- [evaluator-is-the-judge](evaluator-is-the-judge.md) - loop_eval.py decides; fix the loop, not the evaluator
- [codebase-index](codebase-index.md) - Graphify code graph in docs/codebase-index; rebuild with tools/graphify/index.sh
- [pin-literals-not-constants](pin-literals-not-constants.md) - tests must pin limits with literals, not the constant under test
- [compile-app-pure-files-locally](compile-app-pure-files-locally.md) - compile Android-free app files inside :presenter in a scratch copy
- [audit-after-port](audit-after-port.md) - run a determinism audit after each port; vectors only cover what they emit
