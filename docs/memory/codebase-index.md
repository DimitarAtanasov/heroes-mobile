---
name: codebase-index
type: pointer
updated: 2026-11-01
evidence: tools/graphify/index.sh; docs/codebase-index/README.md
---
A Graphify knowledge graph of the code is in `docs/codebase-index/` (report, interactive HTML, `graph.json`); rebuild it with `tools/graphify/index.sh`.
Why: it answers "what calls what" and finds the Python/Kotlin pair of a function without grepping 190 files.
How to apply: read `GRAPH_REPORT.md` first, then `graphify explain` or `path` against `graph.json`. It is a snapshot of one commit, so check the commit in the README and rebuild if the code moved.
