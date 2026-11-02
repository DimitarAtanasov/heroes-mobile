# Codebase index (Graphify)

A knowledge graph of the project's code, built by [Graphify](https://github.com/Graphify-Labs/graphify)
(`graphifyy` 0.9.100, Apache-2.0). Code is parsed locally with tree-sitter: no model call, no data leaves the machine.

| File | Use |
|---|---|
| `GRAPH_REPORT.md` | Start here: hubs, communities, surprising links, suggested questions |
| `graph.html` | Interactive graph; open it in a browser |
| `graph.json` | The full graph for queries |

Indexed at commit `d3719dd`: 298 files, 6,264 nodes, 16,246 edges, 354 communities (94% edges read directly
from the source, 6% inferred). Generated conformance vectors are excluded because they are data.

## Query it
```
python3 -m venv .venv && .venv/bin/pip install graphifyy==0.9.100
.venv/bin/graphify explain "Battle" --graph docs/codebase-index/graph.json
.venv/bin/graphify path "legal_commands" "strike_preview" --graph docs/codebase-index/graph.json
```
Names that exist in both engines (for example `apply`) are listed per file, so you can pick the Kotlin or Python one.

## Rebuild
`tools/graphify/index.sh` rebuilds it from the committed code in a throw-away environment. The index goes stale
with every commit; rebuild before relying on it. Known limits: tree-sitter reports a syntax-error region in
`android/sim/src/main/kotlin/h3/sim/Datapack.kt` (the file compiles; 38 symbols were still extracted), and
Markdown, JSON and Gradle files give no symbols unless the optional model pass is configured (not used here).
