"""Divergence bisector: find the first step where two runs disagree.

Concept ported from Forge's divergence_bisector. Two modes:

* two command logs:   ``python3 -m h3re.bisect_tool A.json B.json``
* policies: ``--policy NAME`` (soak.POLICY_MATRIX), ``--override JSON|f=v;f=v``,
  per side ``--policy-a/--policy-b/--override-a/--override-b``. Unknown names or
  fields are rejected. Logs may carry an optional ``"policy": {"name", "fields"}``
  header (used unless the CLI overrides it); each side's policy is printed.
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
from dataclasses import asdict, fields as dc_fields

from . import soak

__all__ = ["load_log", "load_log_ex", "dump_log", "flatten", "diff_states",
           "bisect", "resolve_policy", "parse_overrides", "format_policy", "main"]


def _policy_class(kind):
    return soak._MODULES[kind].BattlePolicy if kind == "battle" \
        else soak._MODULES[kind].AdventurePolicy


def _tuplify(v):
    if isinstance(v, list):
        return tuple(_tuplify(x) for x in v)
    return v


def parse_overrides(text):
    """Parse an override string into a dict: a JSON object, or ``field=value``
    pairs separated by ';' (each value is JSON, or a bare string)."""
    if text is None or not text.strip():
        return {}
    text = text.strip()
    if text.startswith("{"):
        d = json.loads(text)
        if not isinstance(d, dict):
            raise ValueError("policy override must be a JSON object")
        return d
    out = {}
    for part in text.split(";"):
        part = part.strip()
        if not part:
            continue
        k, eq, v = part.partition("=")
        if not eq or not k.strip():
            raise ValueError("bad override %r (want field=value)" % (part,))
        try:
            out[k.strip()] = json.loads(v)
        except ValueError:
            out[k.strip()] = v.strip()
    return out


def resolve_policy(kind, name=None, overrides=None):
    """Build the kind's policy object from a ``soak.POLICY_MATRIX`` name and
    field overrides. Unknown names or fields raise ValueError. Returns
    (policy, spec) where spec is the header form ``{"name", "fields"}``."""
    if kind not in soak.KINDS:
        raise ValueError("unknown kind %r" % (kind,))
    overrides = dict(overrides or {})
    base = {}
    if name is not None:
        for n, bk, ak in soak.POLICY_MATRIX:
            if n == name:
                base = dict(bk if kind == "battle" else ak)
                break
        else:
            raise ValueError("unknown policy %r (known: %s)" % (
                name, ", ".join(n for n, _, _ in soak.POLICY_MATRIX)))
    valid = sorted(f.name for f in dc_fields(_policy_class(kind)))
    for k in sorted(overrides):
        if k not in valid:
            raise ValueError("unknown %s policy field %r" % (kind, k))
    base.update({k: _tuplify(v) for k, v in overrides.items()})
    spec = {"name": name, "fields": {k: overrides[k] for k in sorted(overrides)}}
    return _policy_class(kind)(**base), spec


def format_policy(spec):
    if not spec or (spec.get("name") is None and not spec.get("fields")):
        return "default"
    out = spec.get("name") or "default"
    if spec.get("fields"):
        out += " + " + json.dumps(spec["fields"], sort_keys=True)
    return out


def dump_log(kind, seed, commands, policy=None):
    """``policy`` is an optional header spec ``{"name", "fields"}``; omitted
    from the log when None or empty so older logs round-trip unchanged."""
    d = {"kind": kind, "seed": seed,
         "commands": [soak.encode_command(c) for c in commands]}
    if policy and (policy.get("name") is not None or policy.get("fields")):
        d["policy"] = {"name": policy.get("name"),
                       "fields": dict(policy.get("fields") or {})}
    return d


def load_log_ex(path):
    """(kind, seed, commands, policy_spec_or_None)."""
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    kind = d["kind"]
    if kind not in soak.KINDS:
        raise ValueError("unknown kind %r" % (kind,))
    pol = d.get("policy")
    if pol is not None:
        if not isinstance(pol, dict) or set(pol) - {"name", "fields"}:
            raise ValueError("bad policy header")
        resolve_policy(kind, pol.get("name"), pol.get("fields"))  # validate
    return (kind, d["seed"], [soak.decode_command(kind, c) for c in d["commands"]],
            pol)


def load_log(path):
    kind, seed, cmds, _ = load_log_ex(path)
    return kind, seed, cmds


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


def _steps(kind, seed, commands, perturb, policy=None):
    return list(soak.replay_steps(kind, seed, commands, perturb, policy))


def bisect(kind_a, seed_a, cmds_a, perturb_a, kind_b, seed_b, cmds_b, perturb_b,
           policy_a=None, policy_b=None):
    """Compare two runs. Returns None if identical, else a report dict with
    ``step``, ``cmd_a``, ``cmd_b``, ``fields`` and ``note``. ``policy_a/b`` are
    policy objects (None: default) used for each side's scenario and replay."""
    if kind_a != kind_b:
        return {"step": 0, "cmd_a": None, "cmd_b": None, "fields": [],
                "note": "different kinds: %s vs %s" % (kind_a, kind_b)}
    sa = _steps(kind_a, seed_a, cmds_a, perturb_a, policy_a)
    sb = _steps(kind_b, seed_b, cmds_b, perturb_b, policy_b)
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
    ap.add_argument("--policy", help="soak.POLICY_MATRIX name, both sides")
    ap.add_argument("--policy-a", help="policy name for side A only")
    ap.add_argument("--policy-b", help="policy name for side B only")
    ap.add_argument("--override", help="field overrides, both sides: JSON object "
                    "or 'field=value;field=value'")
    ap.add_argument("--override-a", help="field overrides for side A only")
    ap.add_argument("--override-b", help="field overrides for side B only")
    args = ap.parse_args(argv)

    def side_spec(hdr, name_side, ov_side):
        # CLI beats the log header; side-specific beats the shared option.
        name = name_side if name_side is not None else args.policy
        ov = ov_side if ov_side is not None else args.override
        if name is None and ov is None:
            return (hdr or {}).get("name"), dict((hdr or {}).get("fields") or {})
        if name is None:
            name = (hdr or {}).get("name")
        return name, parse_overrides(ov)

    try:
        if len(args.logs) == 2:
            ka, sa, ca, ha = load_log_ex(args.logs[0])
            kb, sb, cb, hb = load_log_ex(args.logs[1])
            pa, pb = None, None
        elif not args.logs and args.kind is not None and args.seed is not None:
            ka = kb = args.kind
            sa = sb = args.seed
            ha = hb = None
            pa, pb = None, _parse_perturb(args.perturb)
        else:
            ap.error("give two log files, or --kind and --seed")
        na, fa = side_spec(ha, args.policy_a, args.override_a)
        nb, fb = side_spec(hb, args.policy_b, args.override_b)
        pol_a, spec_a = resolve_policy(ka, na, fa)
        pol_b, spec_b = resolve_policy(kb, nb, fb)
    except ValueError as e:
        ap.error(str(e))
    if not args.logs:
        ca, _ = soak.generate_log(ka, sa, args.max_steps, pol_a)
        cb = ca
        if args.emit:
            with open(args.emit, "w", encoding="utf-8") as f:
                json.dump(dump_log(ka, sa, ca, spec_a), f)
    print("policy A: %s" % format_policy(spec_a))
    print("policy B: %s" % format_policy(spec_b))
    rep = bisect(ka, sa, ca, pa, kb, sb, cb, pb, pol_a, pol_b)
    print(format_report(rep))
    return 1 if rep else 0


if __name__ == "__main__":
    sys.exit(main())
