#!/usr/bin/env python3
"""Determinism lint for the Kotlin simulation sources (android/sim, Law 2).

Companion of banned_api_lint.py (Python). Comments and string literals are
removed by a small tokenizer first (so they never trigger a rule), then the
remaining code is scanned. Rules (rule id -> meaning):

  KT_FLOAT       Double/Float types, float literals (1.0, 1e3, 1f), toDouble/toFloat
  KT_MATH        kotlin.math / java.lang.Math functions that work on reals
                 (floorDiv, floorMod, *Exact, abs, min, max are allowed)
  KT_CLOCK       System.currentTimeMillis/nanoTime, java.time, kotlin.time, Date
  KT_RANDOM      java.util.Random, kotlin.random, SecureRandom, Math.random
  KT_THREAD      Thread, Executors, coroutines, java.util.concurrent
  KT_UNORDERED   HashMap/HashSet/mutableMapOf/mutableSetOf (use LinkedHashMap,
                 sorted()/toSortedMap(); membership-only use may be allowlisted)
  KT_CHARSET     default-charset calls: String(bytes), toByteArray(), readText(), ...
  KT_LOCALE      String.format / toUpperCase() / toLowerCase() without Locale.ROOT
  KT_ENV         System.getenv / getProperty / ...
  KT_PRINT       println / print / System.out / System.err

Allowlist: JSON list of {"file", "rule", "line", "justification",
"count" (optional, default 1)}. ``line`` is the exact (whitespace-normalised)
source text of the offending line; an entry covers only that statement, at most
``count`` times, so a new violation elsewhere in the same function is still
reported. Justification is mandatory. Inline alternative:
``// det-lint-allow: RULE -- why`` on the offending line.

Usage: kotlin_banned_api_lint.py [--allowlist FILE] [--root DIR] [paths...]
Exit status 1 when violations remain.
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.normpath(os.path.join(
    HERE, "..", "..", "android", "sim", "src", "main", "kotlin", "h3", "sim"))
DEFAULT_ALLOWLIST = os.path.join(HERE, "kotlin_banned_api_allowlist.json")
INLINE_MARK = "det-lint-allow:"

RULES = ("KT_FLOAT", "KT_MATH", "KT_CLOCK", "KT_RANDOM", "KT_THREAD",
         "KT_UNORDERED", "KT_CHARSET", "KT_LOCALE", "KT_ENV", "KT_PRINT")


class Violation:
    def __init__(self, file, line, rule, message, text=""):
        self.file, self.line, self.rule = file, line, rule
        self.message, self.text = message, text

    def __str__(self):
        return "%s:%d: %s %s" % (self.file, self.line, self.rule, self.message)

    def key(self):
        return (self.file, self.line, self.rule, self.message)


# ---------------------------------------------------------------- tokenizer

def strip_source(src):
    """Return ``src`` with comments and string/char literal contents blanked to
    spaces. Length and newlines are preserved, so offsets and line numbers
    still match. Handles nested block comments, raw strings and ``${...}``
    templates (template code is kept, since it is code)."""
    out = list(src)
    n = len(src)

    def blank(a, b):
        for k in range(a, min(b, n)):
            if out[k] != "\n":
                out[k] = " "

    i = 0
    mode = "code"          # code | str | raw
    depth = 0              # brace depth inside the current code region
    stack = []             # saved (string mode, depth) when entering ${ ... }
    while i < n:
        c = src[i]
        if mode == "code":
            if src.startswith("//", i):
                j = src.find("\n", i)
                j = n if j < 0 else j
                blank(i, j)
                i = j
            elif src.startswith("/*", i):
                level, j = 1, i + 2
                while j < n and level:
                    if src.startswith("/*", j):
                        level += 1
                        j += 2
                    elif src.startswith("*/", j):
                        level -= 1
                        j += 2
                    else:
                        j += 1
                blank(i, j)
                i = j
            elif src.startswith('"""', i):
                mode = "raw"
                i += 3
            elif c == '"':
                mode = "str"
                i += 1
            elif c == "'":
                j = i + 1
                if j < n and src[j] == "\\":
                    j = src.find("'", j + 2)
                    j = n if j < 0 else j
                else:
                    j = j + 1
                blank(i + 1, j)
                i = j + 1
            elif c == "{":
                depth += 1
                i += 1
            elif c == "}":
                if depth == 0 and stack:
                    mode, depth = stack.pop()
                else:
                    depth -= 1
                i += 1
            else:
                i += 1
        else:
            if mode == "str" and c == "\\":
                blank(i, i + 2)
                i += 2
            elif mode == "str" and c == '"':
                mode = "code"
                i += 1
            elif mode == "raw" and src.startswith('"""', i):
                mode = "code"
                i += 3
            elif c == "$" and src.startswith("{", i + 1):
                stack.append((mode, depth))
                mode, depth = "code", 0
                i += 2
            else:
                blank(i, i + 1)
                i += 1
    return "".join(out)


# ------------------------------------------------------------------- rules

def _split_args(text, open_idx):
    """Arguments of the call whose '(' is at ``open_idx``: list of stripped
    strings (empty list for no arguments), or None if unbalanced."""
    depth, args, cur = 0, [], []
    for k in range(open_idx, len(text)):
        c = text[k]
        if c in "([{":
            depth += 1
            if depth == 1:
                continue
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                last = "".join(cur).strip()
                if last or args:
                    args.append(last)
                return args
        elif c == "," and depth == 1:
            args.append("".join(cur).strip())
            cur = []
            continue
        cur.append(c)
    return None


MATH_OK = frozenset({"floorDiv", "floorMod", "ceilDiv", "ceilMod", "abs", "min",
                     "max", "multiplyHigh", "clamp", "absoluteValue"})
MATH_QUAL = re.compile(
    r"\b(?:kotlin\.math|java\.lang\.(?:Strict)?Math|(?:Strict)?Math)\s*\.\s*(\*|\w+)")

SIMPLE = (
    ("KT_FLOAT", re.compile(r"\b(?:Double|Float)(?:Array)?\b"), "float type"),
    ("KT_FLOAT", re.compile(r"\.\s*(?:toDouble|toFloat)\b"), "conversion to float"),
    ("KT_CLOCK", re.compile(r"\bSystem\s*\.\s*(?:currentTimeMillis|nanoTime)\b"),
     "wall clock"),
    ("KT_CLOCK", re.compile(r"\bjava\s*\.\s*time\b|\bkotlinx\s*\.\s*datetime\b"
                            r"|\bkotlin\s*\.\s*time\b|\bjava\s*\.\s*util\s*\.\s*(?:Date|Calendar)\b"
                            r"|\b(?:measureTimeMillis|measureNanoTime|measureTime|TimeSource"
                            r"|LocalDateTime|LocalDate|Instant|ZonedDateTime)\b"),
     "time API"),
    ("KT_RANDOM", re.compile(r"\bjava\s*\.\s*util\s*\.\s*Random\b|\bkotlin\s*\.\s*random\b"
                             r"|\b(?:Random|SecureRandom|ThreadLocalRandom|SplittableRandom)\b"),
     "non-stream randomness"),
    ("KT_THREAD", re.compile(r"\b(?:Thread|Executors|ExecutorService|Executor|CompletableFuture"
                             r"|runBlocking|GlobalScope|CoroutineScope|Dispatchers)\b"
                             r"|\bkotlinx\s*\.\s*coroutines\b|\bjava\s*\.\s*util\s*\.\s*concurrent\b"
                             r"|\bkotlin\s*\.\s*concurrent\b|\bsuspend\s+fun\b"),
     "threads / coroutines"),
    ("KT_UNORDERED", re.compile(r"\b(?:HashMap|HashSet|mutableMapOf|mutableSetOf|hashMapOf"
                                r"|hashSetOf|toHashSet|toMutableSet)\b"),
     "hash-ordered collection (use LinkedHashMap/LinkedHashSet or sort)"),
    ("KT_ENV", re.compile(r"\bSystem\s*\.\s*(?:getenv|getProperty|getProperties|setProperty"
                          r"|lineSeparator|console)\b"), "environment / property read"),
    ("KT_PRINT", re.compile(r"\b(?:println|print|printf|readLine|readln)\s*\("
                            r"|\bSystem\s*\.\s*(?:out|err|in)\b|\.printStackTrace\b"),
     "console I/O"),
    ("KT_LOCALE", re.compile(r"\bLocale\s*\.\s*(?:getDefault|US|ENGLISH|UK|GERMANY|FRANCE)\b"
                             r"|\bLocale\s*\(", ), "non-ROOT locale"),
)

FLOAT_LITERALS = (
    re.compile(r"(?<![\w.])\d[\d_]*\.\d[\d_]*(?:[eE][+-]?\d+)?[fF]?(?![\w])"),
    re.compile(r"(?<![\w.])\.\d[\d_]*(?:[eE][+-]?\d+)?[fF]?(?![\w])"),
    re.compile(r"(?<![\w.])\d[\d_]*[eE][+-]?\d+[fF]?(?![\w])"),
    re.compile(r"(?<![\w.])\d[\d_]*[fF](?![\w])"),
)
HEX_BIN = re.compile(r"\b0[xXbB][0-9a-fA-F_]+[uUlL]*\b")
CHARSET_ARG = re.compile(r"\bCharsets\s*\.|\bStandardCharsets\s*\.|\bcharset\b|\bCharset\b"
                         r"|\bUTF_8\b|\bUTF8\b", re.I)
CHARSET_FUNCS = re.compile(
    r"\.\s*(toByteArray|readText|readLines|reader|bufferedReader|writer|bufferedWriter"
    r"|printWriter|writeText|appendText|forEachLine|useLines)\s*\(")
CHARSET_CTORS = re.compile(
    r"(?<![.\w])(String|InputStreamReader|OutputStreamWriter|FileReader|FileWriter"
    r"|Scanner|PrintWriter|PrintStream)\s*\(")
FORMAT_CALL = re.compile(r"\.\s*format\s*\(")
CASE_CALL = re.compile(r"\.\s*(toUpperCase|toLowerCase|capitalize|decapitalize)\s*\(")


def _scan(code, file):
    """Yield (offset, rule, message) for the stripped code text."""
    for rule, rx, msg in SIMPLE:
        for m in rx.finditer(code):
            yield m.start(), rule, "%s: %r" % (msg, m.group(0).strip())
    # float literals (hex/binary literals blanked first so 0x1F / 0b1e are not hits)
    masked = HEX_BIN.sub(lambda m: " " * len(m.group(0)), code)
    for rx in FLOAT_LITERALS:
        for m in rx.finditer(masked):
            yield m.start(), "KT_FLOAT", "float literal: %r" % m.group(0)
    for m in MATH_QUAL.finditer(code):
        name = m.group(1)
        if name == "random":
            yield m.start(), "KT_RANDOM", "Math.random"
        elif name not in MATH_OK and not name.endswith("Exact"):
            yield m.start(), "KT_MATH", "real-valued math: %s" % name
    for m in CHARSET_FUNCS.finditer(code):
        args = _split_args(code, m.end() - 1)
        if args is not None and not any(CHARSET_ARG.search(a) for a in args):
            yield m.start(), "KT_CHARSET", "%s() without explicit charset" % m.group(1)
    for m in CHARSET_CTORS.finditer(code):
        # skip declarations such as "fun String(" and class headers
        pre = code[max(0, m.start() - 6):m.start()]
        if pre.rstrip().endswith(("fun", "class")):
            continue
        args = _split_args(code, m.end() - 1)
        if args and not any(CHARSET_ARG.search(a) for a in args):
            yield m.start(), "KT_CHARSET", "%s(...) without explicit charset" % m.group(1)
    for m in FORMAT_CALL.finditer(code):
        args = _split_args(code, m.end() - 1)
        if args is not None and not (args and args[0].startswith("Locale.ROOT")):
            yield m.start(), "KT_LOCALE", "format() without Locale.ROOT"
    for m in CASE_CALL.finditer(code):
        args = _split_args(code, m.end() - 1)
        if args is not None and not (args and "Locale.ROOT" in args[0]):
            yield m.start(), "KT_LOCALE", "%s() without Locale.ROOT" % m.group(1)


def lint_source(source, file="<src>"):
    """Return the raw violations (before allowlisting) for one Kotlin text."""
    code = strip_source(source)
    lines = source.splitlines()
    kept = []
    seen = set()
    for off, rule, msg in _scan(code, file):
        line = code.count("\n", 0, off) + 1
        text = lines[line - 1] if line <= len(lines) else ""
        v = Violation(file, line, rule, msg, text.strip())
        if v.key() in seen:
            continue
        seen.add(v.key())
        if INLINE_MARK in text:
            tail = text.split(INLINE_MARK, 1)[1]
            rules, _, why = tail.partition("--")
            if rule in rules.replace(",", " ").split() and why.strip():
                continue
        kept.append(v)
    return sorted(kept, key=lambda x: (x.line, x.rule, x.message))


# --------------------------------------------------------------- allowlist

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
        if not str(e.get("line", "")).strip():
            raise ValueError("allowlist entry lacks the source 'line' text "
                             "(function-wide entries are not allowed): %r" % (e,))
        c = e.get("count", 1)
        if type(c) is not int or c < 1:
            raise ValueError("allowlist entry has a bad 'count': %r" % (e,))
    return entries


def _entry_matches(e, v):
    return (e["rule"] == v.rule
            and os.path.basename(v.file) == os.path.basename(e["file"])
            and " ".join(e["line"].split()) == " ".join(v.text.split()))


def apply_allowlist(violations, allowlist, unused=None):
    """Drop violations covered by a line-scoped entry; each entry absorbs at
    most ``count`` violations. ``unused`` receives entries that matched nothing."""
    budget = [e.get("count", 1) for e in allowlist]
    used = [False] * len(allowlist)
    out = []
    for v in violations:
        for i, e in enumerate(allowlist):
            if budget[i] > 0 and _entry_matches(e, v):
                budget[i] -= 1
                used[i] = True
                break
        else:
            out.append(v)
    if unused is not None:
        unused.extend(e for e, u in zip(allowlist, used) if not u)
    return out


def lint_paths(paths, allowlist=(), unused=None):
    out = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            out.extend(lint_source(f.read(), p))
    return apply_allowlist(out, list(allowlist), unused)


def default_paths(root):
    found = []
    for d, dirs, files in os.walk(root):
        dirs.sort()
        found.extend(os.path.join(d, f) for f in sorted(files) if f.endswith(".kt"))
    return found


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="*", help="files (default: every .kt under --root)")
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--allowlist", default=DEFAULT_ALLOWLIST)
    args = ap.parse_args(argv)
    paths = args.paths or default_paths(args.root)
    if not paths:
        print("error: no Kotlin sources found under %s" % args.root)
        return 2
    unused = []
    viol = lint_paths(paths, load_allowlist(args.allowlist), unused)
    for v in viol:
        print(v)
    for e in unused:
        print("note: unused allowlist entry: %s %s %r" % (e["file"], e["rule"], e["line"]))
    print("%d violation(s) in %d file(s)" % (len(viol), len(paths)))
    return 1 if viol else 0


if __name__ == "__main__":
    sys.exit(main())
