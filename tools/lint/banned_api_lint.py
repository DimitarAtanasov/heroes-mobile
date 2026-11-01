#!/usr/bin/env python3
"""AST determinism lint for the simulation modules (battle, adventure, rules, rng).

Concept ported from Forge's banned_api_lint; see docs/specs/determinism-gate.md.

Rules (rule id -> meaning):
  FLOAT_LITERAL   float constant
  TRUE_DIV        ``/`` or ``/=`` (use ``//`` or Fraction)
  FLOAT_CALL      float(...)
  MATH_FLOAT      math function that returns a float (int-returning ones are allowed)
  BANNED_IMPORT   import of time/datetime/random/os/... (nondeterminism or I/O)
  BANNED_CALL     open/print/input/eval/exec/id/hash(...) or a call on a banned module
  ITER_UNORDERED  iteration over a set/dict view/set-valued name without sorted()
                  where the order could reach the result

Allowlist: JSON list of {"file", "rule", "function" (optional), "justification"}
(justification is mandatory), or an inline ``# det-lint-allow: RULE -- why``
comment on the offending line.

Usage: banned_api_lint.py [--allowlist FILE] [--root DIR] [paths...]
Exit status 1 when violations remain.
"""

import argparse
import ast
import json
import os
import sys

SIM_MODULES = ("battle.py", "adventure.py", "rules.py", "rng.py")
DEFAULT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "h3re", "h3re")
DEFAULT_ALLOWLIST = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "banned_api_allowlist.json")

BANNED_MODULES = frozenset({
    "time", "datetime", "random", "os", "secrets", "uuid", "socket",
    "subprocess", "threading", "multiprocessing", "asyncio", "tempfile",
    "pathlib", "shutil", "io", "sys",
})
BANNED_BUILTINS = frozenset({"open", "print", "input", "eval", "exec", "id",
                             "hash", "breakpoint"})
# math functions that return an int (or exact value); everything else is float.
MATH_INT_OK = frozenset({"floor", "ceil", "trunc", "gcd", "lcm", "isqrt",
                         "comb", "perm", "factorial"})
# Consumers whose result does not depend on iteration order.
ORDER_FREE = frozenset({"sorted", "sum", "min", "max", "any", "all", "len",
                        "set", "frozenset"})
ORDERED_BUILDERS = frozenset({"list", "tuple", "enumerate", "iter", "next",
                              "zip", "reversed", "map", "filter"})
DICT_VIEWS = frozenset({"keys", "values", "items"})
SET_METHODS = frozenset({"union", "intersection", "difference",
                         "symmetric_difference"})
INLINE_MARK = "det-lint-allow:"

RULES = ("FLOAT_LITERAL", "TRUE_DIV", "FLOAT_CALL", "MATH_FLOAT",
         "BANNED_IMPORT", "BANNED_CALL", "ITER_UNORDERED")


class Violation:
    def __init__(self, file, line, col, rule, message, function=""):
        self.file, self.line, self.col = file, line, col
        self.rule, self.message, self.function = rule, message, function

    def __str__(self):
        return "%s:%d:%d: %s %s" % (self.file, self.line, self.col, self.rule,
                                    self.message)

    def key(self):
        return (self.file, self.line, self.col, self.rule)


def load_allowlist(path):
    """Load and validate an allowlist; every entry needs a justification."""
    if not path or not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        entries = json.load(f)
    if not isinstance(entries, list):
        raise ValueError("allowlist must be a JSON list")
    for e in entries:
        if not isinstance(e, dict) or e.get("rule") not in RULES or not e.get("file"):
            raise ValueError("bad allowlist entry: %r" % (e,))
        if not str(e.get("justification", "")).strip():
            raise ValueError("allowlist entry lacks justification: %r" % (e,))
    return entries


def _is_set_expr(node, set_names):
    if isinstance(node, (ast.Set, ast.SetComp)):
        return True
    if isinstance(node, ast.Name):
        return node.id in set_names
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Name) and f.id in ("set", "frozenset"):
            return True
        if isinstance(f, ast.Attribute) and f.attr in SET_METHODS:
            return True
    if isinstance(node, ast.BinOp) and isinstance(
            node.op, (ast.BitOr, ast.BitAnd, ast.BitXor, ast.Sub)):
        return _is_set_expr(node.left, set_names) or _is_set_expr(node.right, set_names)
    return False


def _is_dict_view(node):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr in DICT_VIEWS and not node.args)


class _Visitor(ast.NodeVisitor):
    def __init__(self, file):
        self.file = file
        self.out = []
        self.func = []
        self.set_names = [set()]
        self.parents = []
        self.math_aliases = set()
        self.banned_aliases = set()

    # -- helpers
    def add(self, node, rule, msg):
        self.out.append(Violation(self.file, node.lineno, node.col_offset, rule, msg,
                                  ".".join(self.func)))

    def generic_visit(self, node):
        self.parents.append(node)
        super().generic_visit(node)
        self.parents.pop()

    def _order_free_context(self):
        # innermost enclosing Call (skipping the comprehension itself)
        if self.parents:
            p = self.parents[-1]
            if isinstance(p, ast.Call) and isinstance(p.func, ast.Name) \
                    and p.func.id in ORDER_FREE:
                return True
        return False

    def _check_iter(self, it, node, what):
        if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) \
                and it.func.id == "sorted":
            return
        if _is_set_expr(it, self.set_names[-1] | self.set_names[0]):
            self.add(node, "ITER_UNORDERED", "%s over a set without sorted()" % what)
        elif _is_dict_view(it):
            self.add(node, "ITER_UNORDERED",
                     "%s over dict .%s() without sorted()" % (what, it.func.attr))

    # -- scopes
    def _scope(self, node):
        self.func.append(node.name)
        self.set_names.append(set())
        self.generic_visit(node)
        self.set_names.pop()
        self.func.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = _scope

    def visit_ClassDef(self, node):
        self.func.append(node.name)
        self.generic_visit(node)
        self.func.pop()

    # -- literals / arithmetic
    def visit_Constant(self, node):
        if isinstance(node.value, float):
            self.add(node, "FLOAT_LITERAL", "float literal %r" % (node.value,))

    def visit_BinOp(self, node):
        if isinstance(node.op, ast.Div):
            self.add(node, "TRUE_DIV", "true division '/' (use // or Fraction)")
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        if isinstance(node.op, ast.Div):
            self.add(node, "TRUE_DIV", "true division '/=' (use // or Fraction)")
        self.generic_visit(node)

    # -- imports
    def _import(self, node, mod):
        root = mod.split(".")[0]
        if root in BANNED_MODULES:
            self.add(node, "BANNED_IMPORT", "import of %r" % mod)

    def visit_Import(self, node):
        for a in node.names:
            self._import(node, a.name)
            if a.name == "math":
                self.math_aliases.add(a.asname or "math")
            if a.name.split(".")[0] in BANNED_MODULES:
                self.banned_aliases.add(a.asname or a.name.split(".")[0])

    def visit_ImportFrom(self, node):
        if node.level == 0 and node.module:
            self._import(node, node.module)
            if node.module == "math":
                for a in node.names:
                    if a.name not in MATH_INT_OK:
                        self.add(node, "MATH_FLOAT",
                                 "math.%s returns a float" % a.name)

    # -- calls
    def visit_Call(self, node):
        f = node.func
        if isinstance(f, ast.Name):
            if f.id == "float":
                self.add(node, "FLOAT_CALL", "float() call")
            elif f.id in BANNED_BUILTINS:
                self.add(node, "BANNED_CALL", "call to %s()" % f.id)
        elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
            if f.value.id in self.math_aliases and f.attr not in MATH_INT_OK:
                self.add(node, "MATH_FLOAT", "math.%s returns a float" % f.attr)
            elif f.value.id in self.banned_aliases:
                self.add(node, "BANNED_CALL", "call to %s.%s()" % (f.value.id, f.attr))
        # list(set)/tuple(set)/etc. materialise an arbitrary order
        if isinstance(f, ast.Name) and f.id in ORDERED_BUILDERS and node.args:
            self._check_iter(node.args[0], node, "%s()" % f.id)
        self.generic_visit(node)

    # -- iteration
    def visit_For(self, node):
        self._check_iter(node.iter, node, "for loop")
        self.generic_visit(node)

    def _comp(self, node):
        if not self._order_free_context():
            for g in node.generators:
                self._check_iter(g.iter, g.iter, "comprehension")
        self.generic_visit(node)

    visit_ListComp = visit_GeneratorExp = visit_DictComp = _comp

    def visit_SetComp(self, node):
        # building a set from an unordered source is order-free
        self.generic_visit(node)

    def visit_Assign(self, node):
        if _is_set_expr(node.value, self.set_names[-1] | self.set_names[0]):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    self.set_names[-1].add(t.id)
        else:
            for t in node.targets:
                if isinstance(t, ast.Name):
                    self.set_names[-1].discard(t.id)
        self.generic_visit(node)


def lint_source(source, file="<src>"):
    """Return the raw violations (before allowlisting) for one source text."""
    tree = ast.parse(source, filename=file)
    v = _Visitor(file)
    v.visit(tree)
    lines = source.splitlines()
    kept = []
    for x in v.out:
        text = lines[x.line - 1] if x.line <= len(lines) else ""
        if INLINE_MARK in text:
            tail = text.split(INLINE_MARK, 1)[1]
            rule, _, why = tail.partition("--")
            if x.rule in rule.replace(",", " ").split() and why.strip():
                continue
        kept.append(x)
    return sorted(kept, key=lambda x: x.key())


def apply_allowlist(violations, allowlist):
    out = []
    for v in violations:
        ok = False
        for e in allowlist:
            if e["rule"] == v.rule and os.path.basename(v.file) == os.path.basename(e["file"]):
                fn = e.get("function")
                if fn is None or fn == v.function or v.function.startswith(fn + "."):
                    ok = True
                    break
        if not ok:
            out.append(v)
    return out


def lint_paths(paths, allowlist=()):
    out = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            out.extend(lint_source(f.read(), p))
    return apply_allowlist(out, list(allowlist))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="*", help="files (default: the four sim modules)")
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--allowlist", default=DEFAULT_ALLOWLIST)
    args = ap.parse_args(argv)
    paths = args.paths or [os.path.normpath(os.path.join(args.root, m))
                           for m in SIM_MODULES]
    viol = lint_paths(paths, load_allowlist(args.allowlist))
    for v in viol:
        print(v)
    print("%d violation(s) in %d file(s)" % (len(viol), len(paths)))
    return 1 if viol else 0


if __name__ == "__main__":
    sys.exit(main())
