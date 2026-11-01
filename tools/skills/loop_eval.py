"""Deterministic loop evaluator. No model is involved: the same inputs always give the same verdict.

  python3 tools/skills/loop_eval.py graph docs/loops/agent-round.md
  python3 tools/skills/loop_eval.py run   docs/loops/agent-round.md docs/loops/runs/agent-round.example.jsonl

`graph` applies the structural checks of validate.py plus STRICT criteria (S1-S4).
`run` checks a recorded run (JSON lines) against the graph and its budgets (R1-R8).
Exit 0 means PASS, 1 means FAIL (violations are printed, one per line, with a rule id), 2 usage error.
An agent saying it is finished is never evidence; only a verifier record with command evidence is.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate as V  # noqa: E402

ROLES = ("advisor", "producer", "runner", "verifier", "lead")
EVIDENCE_KINDS = ("command", "file", "commit", "report", "decision")
RECORD_KEYS = {"step", "node", "to", "label", "actor", "role", "evidence", "spent"}
_LABELED = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)(?:\[[^\]]*\]|\{[^}]*\}|\([^)]*\))?\s*-->\s*(?:\|([^|]*)\|\s*)?"
                      r"([A-Za-z_][A-Za-z0-9_]*)(?:\[[^\]]*\]|\{[^}]*\}|\([^)]*\))?\s*$")


def parse_loop(text):
    """Return (edges, budgets) where edges is a list of (src, label, dst) in document order."""
    m = re.search(r"```mermaid\n(.*?)```", text, re.S)
    edges = []
    if m:
        for line in m.group(1).splitlines():
            e = _LABELED.match(line.strip())
            if e:
                edges.append((e.group(1), (e.group(2) or "").strip(), e.group(3)))
    budgets = {k.strip(): int(v) for k, v in
               re.findall(r"^\s*-\s*budget[: ]\s*([A-Za-z0-9_ -]+?)\s*[:=]\s*(\d+)", text, re.M | re.I)}
    return edges, budgets


def _back_edges(edges, start):
    """Edges whose target is on the DFS stack when met (they close a cycle)."""
    adj = {}
    for a, _, b in edges:
        adj.setdefault(a, []).append(b)
    state, back = {}, set()

    def visit(n):
        state[n] = 1
        for s in adj.get(n, ()):
            if state.get(s) == 1:
                back.add((n, s))
            elif s not in state:
                visit(s)
        state[n] = 2

    visit(start)
    return back


def eval_graph(text, name="loop"):
    errs = [f"G0 {e}" for e in V.check_loop(text, name)]
    edges, budgets = parse_loop(text)
    if not edges:
        return errs
    start = edges[0][0]
    out = {}
    for a, lab, b in edges:
        out.setdefault(a, []).append((lab, b))
    for n, outs in sorted(out.items()):
        if len(outs) > 1:
            for lab, b in outs:
                if not lab:
                    errs.append(f"S1 {name}: edge {n} --> {b} leaves a branching node without a label")
    for k, v in budgets.items():
        if v <= 0:
            errs.append(f"S2 {name}: budget '{k}' must be a positive integer")
    for a, b in sorted(_back_edges(edges, start)):
        labs = [lab for x, lab, y in edges if (x, y) == (a, b)]
        if not all(labs):
            errs.append(f"S2 {name}: back edge {a} --> {b} (a retry) must carry a label")
    nodes = {n for a, _, b in edges for n in (a, b)}
    gates = {n for n in nodes if n.startswith("verify")}
    if "done" in nodes:
        if not gates:
            errs.append(f"S3 {name}: no verify* node; success has no acceptance gate")
        else:
            seen, stack = set(), [start]
            while stack:
                n = stack.pop()
                if n in seen or n in gates:
                    continue
                seen.add(n)
                stack.extend(b for lab, b in out.get(n, ()))
            if "done" in seen:
                errs.append(f"S3 {name}: 'done' is reachable without passing a verify* node")
    if not ({"failed", "escalated"} & nodes):
        errs.append(f"S4 {name}: needs a non-success exit ('failed' or 'escalated')")
    return errs


def _load_run(path):
    recs = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                recs.append(json.loads(line))
            except ValueError as e:
                raise ValueError(f"line {i}: invalid JSON ({e})")
    return recs


def eval_run(text, recs, name="run"):
    errs = [f"G0 {e}" for e in eval_graph(text, name)]
    if errs:
        return errs + [f"R0 {name}: the graph itself fails, so no run can be accepted"]
    edges, budgets = parse_loop(text)
    start = edges[0][0]
    legal = {(a, b): lab for a, lab, b in edges}
    back = _back_edges(edges, start)
    terminals = {n for n in ("done", "failed", "escalated") if any(n in (a, b) for a, _, b in edges)}
    if not recs:
        return [f"R1 {name}: empty run"]
    prev_spent, prev_to = {}, start
    verifier_ok = False
    producers, verifiers = set(), set()
    for i, r in enumerate(recs, 1):
        w = f"{name} step {i}"
        if not isinstance(r, dict):
            errs.append(f"R6 {w}: record is not an object")
            continue
        extra = set(r) - RECORD_KEYS
        if extra:
            errs.append(f"R6 {w}: unknown keys {sorted(extra)}")
        if r.get("step") != i:
            errs.append(f"R1 {w}: step must be {i}, got {r.get('step')!r}")
        node, to = r.get("node"), r.get("to")
        if node != prev_to:
            errs.append(f"R1 {w}: node {node!r} must equal the previous 'to' {prev_to!r}")
        role = r.get("role")
        if role not in ROLES:
            errs.append(f"R6 {w}: role must be one of {ROLES}")
        if not isinstance(r.get("actor"), str) or not r.get("actor"):
            errs.append(f"R6 {w}: actor must be a non-empty string")
        ev = r.get("evidence", [])
        if not isinstance(ev, list):
            errs.append(f"R5 {w}: evidence must be a list")
            ev = []
        has_cmd_ok = False
        has_decision = False
        for item in ev:
            if not isinstance(item, dict) or item.get("kind") not in EVIDENCE_KINDS or \
                    not isinstance(item.get("ref"), str) or not item.get("ref"):
                errs.append(f"R5 {w}: evidence item needs kind in {EVIDENCE_KINDS} and a non-empty ref")
                continue
            if item["kind"] == "command":
                ec = item.get("exit_code")
                if type(ec) is not int:
                    errs.append(f"R5 {w}: command evidence needs an integer exit_code")
                elif ec == 0:
                    has_cmd_ok = True
            if item["kind"] == "decision":
                has_decision = True
        if role == "producer" or role == "runner":
            producers.add(r.get("actor"))
        if role == "verifier":
            verifiers.add(r.get("actor"))
            if isinstance(node, str) and node.startswith("verify") and has_cmd_ok:
                verifier_ok = True
        spent = r.get("spent", {})
        if not isinstance(spent, dict):
            errs.append(f"R3 {w}: spent must be an object")
            spent = {}
        for k, v in spent.items():
            if k not in budgets:
                errs.append(f"R3 {w}: counter {k!r} is not a budget of the loop")
            elif type(v) is not int or v < 0:
                errs.append(f"R3 {w}: counter {k!r} must be a non-negative integer")
            else:
                if v > budgets[k]:
                    errs.append(f"R3 {w}: counter {k!r}={v} exceeds its budget {budgets[k]}")
                if v < prev_spent.get(k, 0):
                    errs.append(f"R3 {w}: counter {k!r} went down ({prev_spent[k]} -> {v})")
        if to is None:
            if node not in terminals:
                errs.append(f"R1 {w}: the run stops at {node!r}, which is not a terminal")
            if i != len(recs):
                errs.append(f"R1 {w}: records continue after a terminal")
            if node == "done" and not verifier_ok:
                errs.append(f"R4 {w}: 'done' without an earlier verify* record carrying command evidence exit_code 0")
            if node == "escalated" and not (has_decision or any(
                    isinstance(e, dict) and e.get("kind") == "decision" for rr in recs for e in rr.get("evidence", []))):
                errs.append(f"R7 {w}: 'escalated' needs decision evidence naming what the owner must decide")
            if node == "failed" and not ev:
                errs.append(f"R8 {w}: 'failed' needs evidence")
        else:
            if (node, to) not in legal:
                errs.append(f"R2 {w}: {node!r} --> {to!r} is not an edge of the graph")
            else:
                if legal[(node, to)] != (r.get("label") or ""):
                    errs.append(f"R2 {w}: label {r.get('label')!r} must be {legal[(node, to)]!r}")
                if (node, to) in back:
                    grew = any(type(v) is int and v > prev_spent.get(k, 0) for k, v in spent.items())
                    if not grew:
                        errs.append(f"R3 {w}: retry edge {node} --> {to} did not increase any budget counter")
        for k, v in spent.items():
            if type(v) is int:
                prev_spent[k] = max(prev_spent.get(k, 0), v)
        prev_to = to
    if recs and recs[-1].get("to") is not None:
        errs.append(f"R1 {name}: the run does not end in a terminal")
    both = producers & verifiers
    if both:
        errs.append(f"R4 {name}: actor(s) {sorted(both)} both produced work and verified it (maker must not accept)")
    return errs


def main(argv):
    if len(argv) >= 3 and argv[1] == "graph":
        with open(argv[2], encoding="utf-8") as f:
            errs = eval_graph(f.read(), argv[2])
    elif len(argv) >= 4 and argv[1] == "run":
        with open(argv[2], encoding="utf-8") as f:
            text = f.read()
        try:
            recs = _load_run(argv[3])
        except (OSError, ValueError) as e:
            print("FAIL R0", e)
            return 1
        errs = eval_run(text, recs, argv[3])
    else:
        print(__doc__)
        return 2
    for e in errs:
        print("FAIL", e)
    print("PASS" if not errs else f"{len(errs)} violation(s)")
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
