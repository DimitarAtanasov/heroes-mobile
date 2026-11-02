"""Sanitized diagnostic report over a directory of the owner's own game files.

``python3 -m h3re real-report DATA_DIR [--out report.json]`` walks DATA_DIR
read-only and produces a JSON report the owner can send back without sending
any game content (CLAUDE.md laws 1 and 9; docs/runbooks/real-data-check.md).

What the report may contain, and nothing else:

* the h3re report version, the Python version and ``sys.platform``;
* archive-relative file names of ``*.lod`` and ``*.h3m`` files (characters
  outside ``[A-Za-z0-9._ -]`` are replaced), sizes in bytes and entry counts;
* per-kind (DEF, PCX, TXT) counts of ok / failed / skipped members and the
  *type names* of the exceptions;
* for ``*.h3m``: header and object parse ok / failed, the format name, map
  size and level count, the exception type name, a fixed-vocabulary reason
  code, the reader's fixed field label, and for an unsupported object its
  class id and subid;
* for the Android sprite loader: whether H3sprite.lod and H3ab_spr.lod are
  present and open, and for the DEF names it asks for (the only member names
  ever reported) whether each is found, decodes and has an idle frame.

It never contains file contents, pixel data, text, map names or other strings
read from a file, member names other than the three requested DEFs, or any
hash of a file. Nothing is written except the optional ``--out`` file, and
every per-file failure is recorded rather than raised.

Stdlib only. This is a tool, not a simulation module: no state or event
reaches it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from . import defimg, h3m, lod, pcx, txt

REPORT_SCHEMA = 1

# Sampling and scan limits. They bound time and memory on a large install.
SAMPLE_PER_KIND = 5            # members decoded per kind per archive (--sample)
MAX_SAMPLE = 200
MAX_MEMBER_BYTES = 8 * 1024 * 1024
MAX_H3M_BYTES = 16 * 1024 * 1024
MAX_LOD_FILES = 200
MAX_H3M_FILES = 100
MAX_DEPTH = 6                  # directory levels below DATA_DIR that are walked

# The sprite loader contract. Keep in step with android/app SpriteLoader.LOD_NAMES
# and android/presenter SpriteLoadPlan.DEFAULT_TABLE (a test checks both).
SPRITE_LODS = ("H3sprite.lod", "H3ab_spr.lod")
SPRITE_DEFS = ("CPKMAN.DEF", "CLCBOW.DEF", "CGRIFF.DEF")
IDLE_GROUP = 2                 # DEF block position of the idle group

KINDS = (("def", ".def"), ("pcx", ".pcx"), ("txt", ".txt"))

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._ \-]")
_SAFE_LABEL = re.compile(r"^[a-z][a-z0-9 _()\-]{0,39}$")
_TRUNCATED = re.compile(r"^truncated data reading ([^:]*):")
_OBJECT_WRAP = re.compile(r"^object \d+ at offset \d+(?: \(class (\d+)\))?: (.*)$", re.S)
_FORMAT_ID = re.compile(r"^unsupported map format 0x([0-9A-Fa-f]{1,8})")


def _safe(name: str) -> str:
    return _SAFE_NAME.sub("?", name)[:120]


def _etype(exc: BaseException) -> str:
    name = type(exc).__name__
    return name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,60}", name) else "Exception"


def _h3re_version() -> str:
    """The package's ``__version__`` when it defines one (it does not yet)."""
    v = getattr(sys.modules.get(__package__ or "h3re"), "__version__", None)
    return v if isinstance(v, str) and re.fullmatch(r"[0-9A-Za-z.+\-]{1,32}", v) else "unversioned"


# ------------------------------------------------------------------ scanning


def _scan(root: Path) -> tuple[list[tuple[str, Path]], list[tuple[str, Path]], bool]:
    """Sorted ``(relative name, path)`` lists of LODs and of maps, and a truncated flag."""
    lods: list[tuple[str, Path]] = []
    maps: list[tuple[str, Path]] = []
    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda _e: None):
        dirnames.sort()
        rel_dir = Path(dirpath).relative_to(root).parts
        if len(rel_dir) >= MAX_DEPTH:
            dirnames[:] = []
        in_maps = any(p.lower() == "maps" for p in rel_dir)
        for fname in sorted(filenames):
            low = fname.lower()
            full = Path(dirpath) / fname
            rel = "/".join(_safe(p) for p in rel_dir + (fname,))
            if low.endswith(".lod"):
                lods.append((rel, full))
            elif low.endswith(".h3m") and in_maps:
                maps.append((rel, full))
    lods.sort(key=lambda t: t[0])
    maps.sort(key=lambda t: t[0])
    truncated = len(lods) > MAX_LOD_FILES or len(maps) > MAX_H3M_FILES
    return lods[:MAX_LOD_FILES], maps[:MAX_H3M_FILES], truncated


def _size(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------ archives


def _decode(kind: str, data: bytes) -> None:
    if kind == "def":
        defimg.parse_def(data)
    elif kind == "pcx":
        pcx.parse_pcx(data)
    else:
        txt.parse_txt(data)


def _count_errors(errors: dict[str, int]) -> list[dict]:
    return [{"type": t, "count": errors[t]} for t in sorted(errors)]


def _kind_report(arc: lod.LodArchive, names: list[str], kind: str, ext: str, sample: int) -> dict:
    members = sorted(n for n in names if n.lower().endswith(ext))
    ok = failed = skipped = 0
    errors: dict[str, int] = {}
    picked = 0
    for name in members:
        if picked >= sample:
            break
        try:
            if arc.entry(name).size > MAX_MEMBER_BYTES:
                skipped += 1
                continue
        except Exception:  # noqa: BLE001
            pass
        picked += 1
        try:
            _decode(kind, arc.read(name))
            ok += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            t = _etype(exc)
            errors[t] = errors.get(t, 0) + 1
    return {"kind": kind, "total": len(members), "sampled": ok + failed,
            "ok": ok, "failed": failed, "skipped_large": skipped,
            "errors": _count_errors(errors)}


def _archive_report(rel: str, path: Path, sample: int) -> dict:
    rep: dict = {"name": rel, "size_bytes": _size(path), "opens": False,
                 "error_type": None, "entries": None, "members": None, "kinds": []}
    try:
        with lod.LodArchive.open(path) as arc:
            names = arc.list()
            rep["opens"] = True
            rep["entries"] = len(names)
            counts = {k: sum(1 for n in names if n.lower().endswith(e)) for k, e in KINDS}
            counts["other"] = len(names) - sum(counts.values())
            rep["members"] = counts
            rep["kinds"] = [_kind_report(arc, names, k, e, sample) for k, e in KINDS]
    except Exception as exc:  # noqa: BLE001
        rep["error_type"] = _etype(exc)
    return rep


# ---------------------------------------------------------------------- maps


def _h3m_error(phase: str, exc: BaseException) -> dict:
    """A fixed-vocabulary description of a map failure; never the message text."""
    err = {"phase": phase, "type": _etype(exc), "reason": "other", "stage": None,
           "format_id": None, "class_id": None, "subid": None}
    if isinstance(exc, h3m.H3mUnsupportedObject):
        err["reason"] = "unsupported_object"
        err["class_id"] = int(exc.class_id)
        err["subid"] = int(exc.subid)
        return err
    if isinstance(exc, OSError):
        err["reason"] = "io"
        return err
    if not isinstance(exc, h3m.H3mError):
        return err
    msg = str(exc)
    m = _OBJECT_WRAP.match(msg)
    if m:
        err["stage"] = "object_body"
        if m.group(1) is not None:
            err["class_id"] = int(m.group(1))
        msg = m.group(2)
    m = _FORMAT_ID.match(msg)
    if m:
        err["reason"] = "unsupported_format"
        err["format_id"] = int(m.group(1), 16)
    elif "gzip" in msg or msg.startswith("decompressed map"):
        err["reason"] = "gzip"
    elif msg.startswith("truncated"):
        err["reason"] = "truncated"
        m = _TRUNCATED.match(msg)
        if m and err["stage"] is None:
            err["stage"] = m.group(1) if _SAFE_LABEL.match(m.group(1)) else "unknown"
    elif "implausible" in msg:
        err["reason"] = "implausible_value"
    elif "not supported" in msg:
        err["reason"] = "unsupported_feature"
    elif msg.startswith(("invalid", "unknown")):
        err["reason"] = "invalid_value"
    return err


def _map_report(rel: str, path: Path) -> dict:
    rep: dict = {"name": rel, "size_bytes": _size(path), "skipped_too_large": False,
                 "header_ok": False, "objects_ok": None, "format": None,
                 "map_size": None, "levels": None, "error": None}
    size = rep["size_bytes"]
    if size is not None and size > MAX_H3M_BYTES:
        rep["skipped_too_large"] = True
        return rep
    try:
        data = path.read_bytes()
    except Exception as exc:  # noqa: BLE001
        rep["error"] = _h3m_error("read", exc)
        return rep
    try:
        header = h3m.parse_h3m(data)
    except Exception as exc:  # noqa: BLE001
        rep["error"] = _h3m_error("header", exc)
        return rep
    rep["header_ok"] = True
    rep["format"] = header.version if header.version in h3m.VERSION_NAMES.values() else "unknown"
    rep["map_size"] = int(header.size)
    rep["levels"] = int(header.levels)
    try:
        h3m.parse_h3m(data, objects=True)
        rep["objects_ok"] = True
    except Exception as exc:  # noqa: BLE001
        rep["objects_ok"] = False
        rep["error"] = _h3m_error("objects", exc)
    return rep


# ------------------------------------------------------------------- sprites


def _find_sprite_lods(root: Path, lods: list[tuple[str, Path]]) -> tuple[str, dict[str, Path]]:
    """Locate the sprite archives the way SpriteLoader does (root/Data, then root)."""
    wanted = {n.lower(): n for n in SPRITE_LODS}
    by_dir: dict[tuple[str, ...], dict[str, Path]] = {}
    for _rel, full in lods:
        n = wanted.get(full.name.lower())
        if n is None:
            continue
        parts = tuple(p.lower() for p in full.parent.relative_to(root).parts)
        by_dir.setdefault(parts, {})[n] = full
    for layout, key in (("data", ("data",)), ("root", ())):
        if key in by_dir:
            return layout, by_dir[key]
    if by_dir:
        first = sorted(by_dir)[0]
        return "nested", by_dir[first]
    return "absent", {}


def _def_report(name: str, archives: list[lod.LodArchive], lod_names: list[str]) -> dict:
    rep = {"name": name, "found_in": None, "decodes": False, "error_type": None,
           "blocks": None, "idle_block_present": False, "idle_frames": None,
           "idle_frame0_nonempty": False}
    for arc, lname in zip(archives, lod_names):
        if name in arc:
            rep["found_in"] = lname
            try:
                d = defimg.parse_def(arc.read(name))
            except Exception as exc:  # noqa: BLE001
                rep["error_type"] = _etype(exc)
                return rep
            rep["decodes"] = True
            rep["blocks"] = len(d.blocks)
            if len(d.blocks) > IDLE_GROUP:
                frames = d.blocks[IDLE_GROUP].frames
                rep["idle_block_present"] = True
                rep["idle_frames"] = len(frames)
                rep["idle_frame0_nonempty"] = bool(
                    frames and frames[0].width > 0 and frames[0].height > 0)
            return rep
    return rep


def _sprite_report(root: Path, lods: list[tuple[str, Path]]) -> dict:
    layout, found = _find_sprite_lods(root, lods)
    lod_reports = []
    archives: list[lod.LodArchive] = []
    opened_names: list[str] = []
    try:
        for n in SPRITE_LODS:
            r = {"name": n, "present": n in found, "opens": False, "error_type": None}
            if n in found:
                try:
                    arc = lod.LodArchive.open(found[n])
                    archives.append(arc)
                    opened_names.append(n)
                    r["opens"] = True
                except Exception as exc:  # noqa: BLE001
                    r["error_type"] = _etype(exc)
            lod_reports.append(r)
        defs = [_def_report(d, archives, opened_names) for d in SPRITE_DEFS]
    finally:
        for arc in archives:
            try:
                arc.close()
            except Exception:  # noqa: BLE001
                pass
    return {"layout": layout, "lods": lod_reports, "defs": defs}


# -------------------------------------------------------------------- report


def _findings(rep: dict) -> list[str]:
    f: set[str] = set()
    if not rep["data_dir"]["is_dir"]:
        f.add("DATA_DIR_INVALID")
    if rep["scan_truncated"]:
        f.add("SCAN_TRUNCATED")
    if rep["data_dir"]["is_dir"] and not rep["archives"]:
        f.add("NO_LOD_FOUND")
    if rep["data_dir"]["is_dir"] and not rep["maps"]:
        f.add("NO_MAPS_FOUND")
    for a in rep["archives"]:
        if not a["opens"]:
            f.add("LOD_OPEN_FAILED")
        for k in a["kinds"]:
            if k["failed"]:
                f.add({"def": "DEF_DECODE_FAILED", "pcx": "PCX_DECODE_FAILED",
                       "txt": "TXT_PARSE_FAILED"}[k["kind"]])
    for m in rep["maps"]:
        err = m["error"]
        if err and err["reason"] == "unsupported_format":
            f.add("MAP_UNSUPPORTED_FORMAT")
        elif not m["header_ok"] and not m["skipped_too_large"]:
            f.add("MAP_HEADER_FAILED")
        elif m["objects_ok"] is False:
            f.add("MAP_OBJECTS_FAILED")
    sp = rep["sprites"]
    for r in sp["lods"]:
        if not r["present"]:
            f.add("SPRITE_LOD_MISSING")
        elif not r["opens"]:
            f.add("SPRITE_LOD_BAD")
    for d in sp["defs"]:
        if d["found_in"] is None:
            f.add("SPRITE_DEF_MISSING")
        elif not d["decodes"]:
            f.add("SPRITE_DEF_BAD")
        elif not d["idle_frame0_nonempty"]:
            f.add("SPRITE_NO_IDLE")
    return sorted(f)


def build_report(data_dir: str | os.PathLike[str], sample: int = SAMPLE_PER_KIND) -> dict:
    """The sanitized report for ``data_dir``. Never raises."""
    sample = max(0, min(int(sample), MAX_SAMPLE))
    root = Path(data_dir)
    try:
        exists, is_dir = root.exists(), root.is_dir()
    except Exception:  # noqa: BLE001
        exists = is_dir = False
    rep: dict = {
        "report_schema": REPORT_SCHEMA,
        "h3re_version": _h3re_version(),
        "python": ".".join(str(x) for x in sys.version_info[:3]),
        "platform": sys.platform,
        "sample_per_kind": sample,
        "data_dir": {"exists": exists, "is_dir": is_dir},
        "scan_truncated": False,
        "archives": [],
        "maps": [],
        "sprites": {"layout": "absent", "lods": [], "defs": []},
        "summary": {},
        "findings": [],
    }
    lods: list[tuple[str, Path]] = []
    maps: list[tuple[str, Path]] = []
    if is_dir:
        try:
            lods, maps, rep["scan_truncated"] = _scan(root)
        except Exception:  # noqa: BLE001
            rep["scan_truncated"] = True
        rep["archives"] = [_archive_report(r, p, sample) for r, p in lods]
        rep["maps"] = [_map_report(r, p) for r, p in maps]
        try:
            rep["sprites"] = _sprite_report(root, lods)
        except Exception:  # noqa: BLE001
            pass
    if not rep["sprites"]["lods"]:
        rep["sprites"] = {
            "layout": "absent",
            "lods": [{"name": n, "present": False, "opens": False, "error_type": None}
                     for n in SPRITE_LODS],
            "defs": [{"name": d, "found_in": None, "decodes": False, "error_type": None,
                      "blocks": None, "idle_block_present": False, "idle_frames": None,
                      "idle_frame0_nonempty": False} for d in SPRITE_DEFS],
        }
    rep["summary"] = {
        "archives_found": len(rep["archives"]),
        "archives_open": sum(1 for a in rep["archives"] if a["opens"]),
        "maps_found": len(rep["maps"]),
        "maps_header_ok": sum(1 for m in rep["maps"] if m["header_ok"]),
        "maps_objects_ok": sum(1 for m in rep["maps"] if m["objects_ok"]),
    }
    rep["findings"] = _findings(rep)
    return rep


def render(report: dict) -> str:
    return json.dumps(report, indent=2, sort_keys=True) + "\n"


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except Exception:  # noqa: BLE001
        return False


def cmd(args: argparse.Namespace) -> int:
    """CLI entry (wired from __main__). Exit 0 when a report was produced, 1 otherwise."""
    report = build_report(args.data_dir, args.sample)
    text = render(report)
    status = 0 if report["data_dir"]["is_dir"] else 1
    if status:
        print("h3re: error: data_dir is not a readable directory", file=sys.stderr)
    out = getattr(args, "out", None)
    if not out:
        sys.stdout.write(text)
        return status
    try:
        if _inside(Path(out), Path(args.data_dir)):
            raise OSError("refusing to write the report inside the game directory")
        Path(out).write_text(text, encoding="utf-8", newline="\n")
    except Exception as exc:  # noqa: BLE001
        print(f"h3re: error: cannot write report: {_etype(exc)}", file=sys.stderr)
        sys.stdout.write(text)
        return 1
    findings = ",".join(report["findings"]) or "none"
    print(f"wrote {out}: {report['summary']['archives_found']} archive(s), "
          f"{report['summary']['maps_found']} map(s); findings: {findings}")
    return status
