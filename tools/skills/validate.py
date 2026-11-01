"""Validate loop-graph docs (docs/loops/*.md) and repo skills (.claude/skills/*/SKILL.md).

Stdlib only. A loop doc must carry the seven contract fields from the loop-graph guide, a
budget section, and a mermaid graph whose shape is checked: terminals have no exits, every other
node has an exit, every node is reachable from the start, every node can reach a terminal, there
is a `done` terminal, and any cycle requires a budget. Run:  python3 tools/skills/validate.py
"""
import os
import re
import sys

CONTRACT_FIELDS = (
    "goal and input", "state", "actions", "observation",
    "verification", "stop and escalation", "evidence",
)
TERMINALS = ("done", "failed", "escalated")

_NODE = r"([A-Za-z_][A-Za-z0-9_]*)(?:\[[^\]]*\]|\{[^}]*\}|\([^)]*\))?"
_EDGE = re.compile(r"^\s*" + _NODE + r"\s*-->\s*(?:\|[^|]*\|\s*)?" + _NODE + r"\s*$")


def _mermaid_edges(text):
    m = re.search(r"```mermaid\n(.*?)```", text, re.S)
    if not m:
        return None
    edges, nodes = [], []
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith(("flowchart", "graph", "%%")):
            continue
        e = _EDGE.match(line)
        if e:
            edges.append((e.group(1), e.group(2)))
            nodes += [e.group(1), e.group(2)]
    return edges, nodes


def _has_cycle(adj, nodes):
    state = {}

    def visit(n):
        state[n] = 1
        for s in adj.get(n, ()):
            if state.get(s) == 1:
                return True
            if s not in state and visit(s):
                return True
        state[n] = 2
        return False

    return any(n not in state and visit(n) for n in nodes)


def check_loop(text, name="loop"):
    errs = []
    low = text.lower()
    heads = [h.strip().lower() for h in re.findall(r"^#{2,3}\s+(.*)$", text, re.M)]
    for f in CONTRACT_FIELDS:
        if not any(f in h for h in heads):
            errs.append(f"{name}: missing contract section '{f}'")
    budgets = re.findall(r"^\s*-\s*budget[: ]\s*([A-Za-z0-9_ -]+?)\s*[:=]\s*(\d+)", text, re.M | re.I)
    if "## budget" not in low:
        errs.append(f"{name}: missing '## Budget' section")
    got = _mermaid_edges(text)
    if got is None:
        return errs + [f"{name}: missing ```mermaid graph"]
    edges, nodes = got
    if not edges:
        return errs + [f"{name}: mermaid graph has no edges"]
    adj = {}
    for a, b in edges:
        adj.setdefault(a, []).append(b)
    allnodes = sorted(set(nodes))
    terms = [n for n in allnodes if n in TERMINALS]
    if "done" not in terms:
        errs.append(f"{name}: no 'done' terminal node")
    for t in terms:
        if adj.get(t):
            errs.append(f"{name}: terminal '{t}' has outgoing edges")
    for n in allnodes:
        if n not in TERMINALS and not adj.get(n):
            errs.append(f"{name}: node '{n}' has no exit (dead end)")
    start = edges[0][0]
    seen, stack = set(), [start]
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack.extend(adj.get(n, ()))
    for n in allnodes:
        if n not in seen:
            errs.append(f"{name}: node '{n}' is unreachable from '{start}'")
    rev = {}
    for a, b in edges:
        rev.setdefault(b, []).append(a)
    good, stack = set(terms), list(terms)
    while stack:
        n = stack.pop()
        for p in rev.get(n, ()):
            if p not in good:
                good.add(p)
                stack.append(p)
    for n in allnodes:
        if n not in good:
            errs.append(f"{name}: node '{n}' cannot reach any terminal")
    if _has_cycle(adj, allnodes) and not budgets:
        errs.append(f"{name}: the graph has a cycle but no '- budget <name>: <int>' entry")
    return errs


def check_skill(text, dirname):
    errs = []
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return [f"{dirname}: missing YAML frontmatter"]
    fm = dict(re.findall(r"^([A-Za-z_-]+):\s*(.*)$", m.group(1), re.M))
    if fm.get("name") != dirname:
        errs.append(f"{dirname}: frontmatter name {fm.get('name')!r} must equal the directory name")
    desc = fm.get("description", "").strip()
    if not desc:
        errs.append(f"{dirname}: empty description")
    elif len(desc) > 400:
        errs.append(f"{dirname}: description over 400 characters ({len(desc)})")
    if len(text.splitlines()) > 220:
        errs.append(f"{dirname}: SKILL.md over 220 lines; split it (simplicity first)")
    return errs


MEMORY_TYPES = ("lesson", "fact", "preference", "pointer")


def check_memory(root):
    errs = []
    d = os.path.join(root, "docs", "memory")
    idx = os.path.join(d, "MEMORY.md")
    if not os.path.isdir(d):
        return errs
    if not os.path.isfile(idx):
        return ["docs/memory: missing MEMORY.md index"]
    with open(idx, encoding="utf-8") as f:
        itext = f.read()
    if len(itext.splitlines()) > 150:
        errs.append("docs/memory/MEMORY.md: over 150 lines; merge or delete notes")
    linked = set(re.findall(r"\]\(([^)#]+\.md)\)", itext))
    for fn in sorted(linked):
        if not os.path.isfile(os.path.join(d, fn)):
            errs.append(f"docs/memory/MEMORY.md: dead link {fn}")
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".md") or fn == "MEMORY.md":
            continue
        if fn not in linked:
            errs.append(f"docs/memory/{fn}: not listed in MEMORY.md")
        with open(os.path.join(d, fn), encoding="utf-8") as f:
            t = f.read()
        m = re.match(r"^---\n(.*?)\n---\n", t, re.S)
        if not m:
            errs.append(f"docs/memory/{fn}: missing frontmatter")
            continue
        fm = dict(re.findall(r"^([A-Za-z_-]+):\s*(.*)$", m.group(1), re.M))
        if fm.get("name") != fn[:-3]:
            errs.append(f"docs/memory/{fn}: name {fm.get('name')!r} must equal the file name")
        if fm.get("type") not in MEMORY_TYPES:
            errs.append(f"docs/memory/{fn}: type must be one of {MEMORY_TYPES}")
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", fm.get("updated", "")):
            errs.append(f"docs/memory/{fn}: 'updated' must be YYYY-MM-DD")
        if not fm.get("evidence", "").strip():
            errs.append(f"docs/memory/{fn}: empty 'evidence'")
    return errs


def validate_repo(root):
    errs = []
    d = os.path.join(root, "docs", "loops")
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".md"):
                with open(os.path.join(d, fn), encoding="utf-8") as f:
                    errs += check_loop(f.read(), "docs/loops/" + fn)
    s = os.path.join(root, ".claude", "skills")
    if os.path.isdir(s):
        for name in sorted(os.listdir(s)):
            p = os.path.join(s, name, "SKILL.md")
            if os.path.isfile(p):
                with open(p, encoding="utf-8") as f:
                    errs += check_skill(f.read(), name)
    errs += check_memory(root)
    return errs


if __name__ == "__main__":
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    problems = validate_repo(root)
    for p in problems:
        print("error:", p)
    print(f"{len(problems)} problem(s)")
    sys.exit(1 if problems else 0)
