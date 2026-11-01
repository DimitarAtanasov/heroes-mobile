"""Divergence bisector: find the first step where two runs disagree.

Concept ported from Forge's divergence_bisector. Two modes:

* two command logs:   ``python3 -m h3re.bisect_tool A.json B.json``
* seed + perturbation: ``python3 -m h3re.bisect_tool --kind battle --seed 7 --perturb rng@5``
  (perturbations: ``rng@K`` extra RNG draw before step K, ``drop@K`` skip step
  K, ``dup@K`` apply step K twice). The log is generated live from the seed.

A log is JSON ``{"kind", "seed", "commands": [{"type": ..., ...}]}``; write
one with ``--emit PATH``. The report gives the first divergent step, the
commands there and the differing state fields (dotted paths).
Spec: docs/specs/determinism-gate.md.
"""

import argparse
import json
import sys
from dataclasses import asdict

from . import soak

__all__ = ["load_log", "dump_log", "flatten", "diff_states", "bisect", "main"]


def dump_log(kind, seed, commands):
    return {"kind": kind, "seed": seed,
            "commands": [soak.encode_command(c) for c in commands]}


def load_log(path):
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    kind = d["kind"]
    if kind not in soak.KINDS:
        raise ValueError("unknown kind %r" % (kind,))
    return kind, d["seed"], [soak.decode_command(kind, c) for c in d["commands"]]


def flatten(obj, prefix=""):
    """Flatten nested dataclass/dict/list/tuple into {dotted.path: leaf}."""
    if hasattr(obj, "__dataclass_fields__"):
        obj = asdict(obj)
    out = {}
    if isinstance(obj, dict):
        for k in sorted(obj, key=str):
            out.update(flatten(obj[k], "%s.%s" % (prefix, k) if prefix else str(k)))
    elif isinstance(obj, (list, tuple)):
        if not obj:
            out[prefix] = []
        for i, v in enumerate(obj):
            out.update(flatten(v, "%s[%d]" % (prefix, i)))
    else:
        out[prefix] = obj
    return out


def diff_states(a, b):
    """List of (path, a_value, b_value) where two states differ; a missing
    side is the string '<absent>'."""
    fa, fb = flatten(a), flatten(b)
    out = []
    for k in sorted(set(fa) | set(fb)):
        va, vb = fa.get(k, "<absent>"), fb.get(k, "<absent>")
        if va != vb:
            out.append((k, va, vb))
    return out


def _steps(kind, seed, commands, perturb):
    return list(soak.replay_steps(kind, seed, commands, perturb))


def bisect(kind_a, seed_a, cmds_a, perturb_a, kind_b, seed_b, cmds_b, perturb_b):
    """Compare two runs. Returns None if identical, else a report dict with
    ``step``, ``cmd_a``, ``cmd_b``, ``fields`` and ``note``."""
    if kind_a != kind_b:
        return {"step": 0, "cmd_a": None, "cmd_b": None, "fields": [],
                "note": "different kinds: %s vs %s" % (kind_a, kind_b)}
    sa = _steps(kind_a, seed_a, cmds_a, perturb_a)
    sb = _steps(kind_b, seed_b, cmds_b, perturb_b)
    mod = soak._MODULES[kind_a]
    for i in range(max(len(sa), len(sb))):
        ra = sa[i] if i < len(sa) else None
        rb = sb[i] if i < len(sb) else None
        if ra is None or rb is None:
            return {"step": i, "cmd_a": ra and ra[1], "cmd_b": rb and rb[1],
                    "fields": [], "note": "run %s ended early" % ("A" if ra is None else "B")}
        _, ca, st_a, ev_a, err_a = ra
        _, cb, st_b, ev_b, err_b = rb
        if err_a or err_b:
            if err_a != err_b:
                return {"step": i, "cmd_a": ca, "cmd_b": cb, "fields": [],
                        "note": "A: %s | B: %s" % (err_a or "ok", err_b or "ok")}
            continue
        if mod.state_hash(st_a) != mod.state_hash(st_b) or repr(ev_a) != repr(ev_b):
            fields = diff_states(st_a, st_b)
            note = "state differs" if fields else "same state, events differ"
            if not fields:
                fields = [("events", repr(ev_a), repr(ev_b))]
            return {"step": i, "cmd_a": ca, "cmd_b": cb, "fields": fields, "note": note}
    return None


def _parse_perturb(s):
    if not s:
        return None
    name, _, k = s.partition("@")
    if name not in ("rng", "drop", "dup") or not k.isdigit():
        raise ValueError("perturbation must be rng@K, drop@K or dup@K")
    return name, int(k)


def format_report(rep):
    if rep is None:
        return "no divergence"
    lines = ["first divergence at step %d: %s" % (rep["step"], rep["note"])]
    for tag in ("a", "b"):
        c = rep["cmd_" + tag]
        lines.append("  cmd %s: %s" % (tag.upper(), soak.encode_command(c) if c else None))
    for path, va, vb in rep["fields"][:40]:
        lines.append("  %s: %s != %s" % (path, va, vb))
    if len(rep["fields"]) > 40:
        lines.append("  ... %d more field(s)" % (len(rep["fields"]) - 40))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="h3re.bisect_tool",
                                 description=__doc__.split("\n")[0])
    ap.add_argument("logs", nargs="*", help="two command-log files (A B)")
    ap.add_argument("--kind", choices=soak.KINDS)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--perturb", help="rng@K | drop@K | dup@K (applied to run B)")
    ap.add_argument("--max-steps", type=int, default=400)
    ap.add_argument("--emit", help="write the generated log (seed mode) to PATH")
    args = ap.parse_args(argv)
    if len(args.logs) == 2:
        ka, sa, ca = load_log(args.logs[0])
        kb, sb, cb = load_log(args.logs[1])
        pa = pb = None
    elif not args.logs and args.kind is not None and args.seed is not None:
        ka = kb = args.kind
        sa = sb = args.seed
        ca, _ = soak.generate_log(ka, sa, args.max_steps)
        cb = ca
        pa, pb = None, _parse_perturb(args.perturb)
        if args.emit:
            with open(args.emit, "w", encoding="utf-8") as f:
                json.dump(dump_log(ka, sa, ca), f)
    else:
        ap.error("give two log files, or --kind and --seed")
    rep = bisect(ka, sa, ca, pa, kb, sb, cb, pb)
    print(format_report(rep))
    return 1 if rep else 0


if __name__ == "__main__":
    sys.exit(main())
