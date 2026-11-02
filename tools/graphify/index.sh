#!/usr/bin/env bash
# Rebuild the code knowledge graph in docs/codebase-index/ with Graphify (Apache-2.0, https://github.com/Graphify-Labs/graphify).
# Code is parsed locally with tree-sitter: no model call, no network use except installing the pinned package from PyPI.
# Indexes exactly what is committed (git archive HEAD), minus generated conformance vectors (data, not code).
# Usage: tools/graphify/index.sh
set -euo pipefail
GRAPHIFY_VERSION="0.9.100"
repo="$(cd "$(dirname "$0")/../.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
# POSIX venvs keep executables in bin/, Windows (Git Bash) venvs in Scripts/
venv_bin() { if [ -d "$work/venv/bin" ]; then echo "$work/venv/bin"; else echo "$work/venv/Scripts"; fi; }
python3 -m venv "$work/venv"
"$(venv_bin)/python" -m pip install -q --disable-pip-version-check "graphifyy==${GRAPHIFY_VERSION}"
mkdir "$work/proj"
git -C "$repo" archive HEAD | tar -x -C "$work/proj"
rm -rf "$work/proj/android/sim/src/test/resources/vectors" "$work/proj/docs/codebase-index"
export GRAPHIFY_BACKEND=none GRAPHIFY_QUERY_LOG_DISABLE=1
(cd "$work/proj" && "$(venv_bin)/graphify" update .)
out="$repo/docs/codebase-index"
mkdir -p "$out"
cp "$work/proj/graphify-out/graph.json" "$work/proj/graphify-out/graph.html" "$work/proj/graphify-out/GRAPH_REPORT.md" "$out/"
echo "Indexed $(git -C "$repo" rev-parse --short HEAD) with graphifyy ${GRAPHIFY_VERSION} -> docs/codebase-index/"
