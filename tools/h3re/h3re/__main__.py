"""Command-line interface for the h3re readers.

Usage (from the directory that contains the ``h3re`` package)::

    python3 -m h3re lod-list FILE.LOD
    python3 -m h3re lod-extract FILE.LOD DESTDIR
    python3 -m h3re def-to-png FILE.DEF OUTDIR
    python3 -m h3re h3m-info FILE.H3M
    python3 -m h3re battle-sim SCENARIO.json --seed N [--chooser CHOOSER] [--pretty [--board-every N] [--color]]
    python3 -m h3re replay record SCENARIO.json --seed N [--chooser C] -o OUT.h3r
    python3 -m h3re replay <verify|info> FILE.h3r

Exit status: 0 on success, 1 for malformed input or I/O errors, 2 for
command-line usage errors. Errors are reported as one line on stderr.

Stdlib only.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from . import battle_cli, defimg, h3m, lod, replay

EXIT_OK = 0
EXIT_FAILURE = 1
# Usage errors exit with 2; argparse does this itself.

# Exceptions that mean the input is malformed or cannot be read or written.
# Every reader raises one of these, so none of them should reach the user as
# a traceback.
_INPUT_ERRORS = (lod.LodError, defimg.DefError, h3m.H3mError, ValueError, OSError)

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]")


def _show(text: str) -> str:
    """Escape text taken from a game file so it is safe to print."""
    return text.encode("unicode_escape").decode("ascii")


def _yes_no(flag: bool) -> str:
    return "yes" if flag else "no"


def _condition(cond: dict | None) -> str:
    return "none" if cond is None else f"type {cond['type']}"


def _describe_error(exc: BaseException) -> str:
    if isinstance(exc, OSError) and exc.strerror:
        return f"{exc.filename}: {exc.strerror}" if exc.filename else exc.strerror
    return str(exc) or type(exc).__name__


# ----------------------------------------------------------------- commands


def cmd_lod_list(args: argparse.Namespace) -> int:
    with lod.LodArchive.open(args.file) as arc:
        for name in arc.list():
            print(_show(name))
    return EXIT_OK


def cmd_lod_extract(args: argparse.Namespace) -> int:
    with lod.LodArchive.open(args.file) as arc:
        written = arc.extract_all(args.destdir)
    print(f"extracted {len(written)} member(s) to {args.destdir}")
    return EXIT_OK


def cmd_def_to_png(args: argparse.Namespace) -> int:
    deffile = defimg.parse_def(Path(args.file).read_bytes())
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    written = 0
    skipped = 0
    for bi, block in enumerate(deffile.blocks):
        for fi, frame in enumerate(block.frames):
            if frame.full_width == 0 or frame.full_height == 0:
                # A PNG needs a non-empty canvas.
                skipped += 1
                continue
            canvas = defimg.frame_to_canvas(frame)
            rgba = defimg.to_rgba(canvas, deffile.palette)
            png = defimg.write_png(frame.full_width, frame.full_height, rgba, channels=4)
            # The index prefix keeps names unique across blocks and stops
            # frame names from producing odd or escaping file names.
            stem = _UNSAFE_FILENAME_CHARS.sub("_", frame.name) or "frame"
            (outdir / f"{bi:02d}_{fi:03d}_{stem}.png").write_bytes(png)
            written += 1

    if skipped:
        print(
            f"h3re: warning: skipped {skipped} frame(s) with an empty canvas",
            file=sys.stderr,
        )
    print(f"wrote {written} PNG file(s) to {outdir}")
    return EXIT_OK


def cmd_h3m_info(args: argparse.Namespace) -> int:
    hdr = h3m.parse_h3m(Path(args.file).read_bytes())
    active = [p for p in hdr.players if p.active]
    max_level = "n/a (RoE)" if hdr.max_hero_level is None else str(hdr.max_hero_level)
    teams = "none" if not hdr.teams else " ".join(str(t) for t in hdr.teams)

    rows = [
        ("format", f"{hdr.version} (0x{hdr.format:02X})"),
        ("size", f"{hdr.size}x{hdr.size}"),
        ("two levels", _yes_no(hdr.two_levels)),
        ("has hero", _yes_no(hdr.has_hero)),
        ("name", _show(hdr.name)),
        ("description", _show(hdr.description)),
        ("difficulty", str(hdr.difficulty)),
        ("max hero level", max_level),
        ("players", f"{len(active)} active of {len(hdr.players)}"),
    ]
    for p in active:
        rows.append(
            (
                f"  player {p.index + 1}",
                f"human={_yes_no(p.can_human)} computer={_yes_no(p.can_computer)}",
            )
        )
    rows += [
        ("victory", _condition(hdr.victory)),
        ("loss", _condition(hdr.loss)),
        ("teams", teams),
    ]

    width = max(len(label) for label, _ in rows) + 1
    for label, value in rows:
        print(f"{label + ':':<{width}} {value}")
    return EXIT_OK


def cmd_battle_sim(args: argparse.Namespace) -> int:
    return battle_cli.run(args.scenario, args.seed, args.chooser,
                          pretty=args.pretty, board_every=args.board_every,
                          color=args.color)


def cmd_replay(args: argparse.Namespace) -> int:
    try:
        if args.replay_command == "record":
            scenario = battle_cli._load_json(args.scenario)
            commands = replay.run_chooser(scenario, args.seed, args.chooser)
            data = replay.record(scenario, commands, args.seed)
            Path(args.output).write_bytes(data)
            print(f"recorded {len(commands)} command(s) to {args.output}")
            return EXIT_OK
        data = Path(args.file).read_bytes()
        if args.replay_command == "verify":
            header = replay.verify(data)
            print(f"ok: {header['command_count']} command(s), final {header['final_hash']}")
        else:
            header = replay.info(data)
            for key in sorted(header):
                print(f"{key}: {header[key]}")
        return EXIT_OK
    except (replay.ReplayError, battle_cli.CliError) as exc:
        print(f"h3re: error: {type(exc).__name__}: {' '.join(str(exc).split())}",
              file=sys.stderr)
        return EXIT_FAILURE


# ------------------------------------------------------------------ plumbing


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="h3re",
        description="Inspect and extract Heroes of Might and Magic 3 files.",
        epilog="exit status: 0 success, 1 malformed input or I/O error, 2 usage error",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    p = sub.add_parser("lod-list", help="list the members of a .LOD archive")
    p.add_argument("file", help="path to a .LOD archive")
    p.set_defaults(func=cmd_lod_list)

    p = sub.add_parser("lod-extract", help="extract every member of a .LOD archive")
    p.add_argument("file", help="path to a .LOD archive")
    p.add_argument("destdir", help="directory to write the members into (created if missing)")
    p.set_defaults(func=cmd_lod_extract)

    p = sub.add_parser("def-to-png", help="write one PNG per frame of a .DEF sprite")
    p.add_argument("file", help="path to a .DEF file")
    p.add_argument("outdir", help="directory for the PNG files (created if missing)")
    p.set_defaults(func=cmd_def_to_png)

    p = sub.add_parser("h3m-info", help="print the header summary of an .H3M map")
    p.add_argument("file", help="path to an .H3M map (gzip-wrapped or raw)")
    p.set_defaults(func=cmd_h3m_info)

    p = sub.add_parser("battle-sim", help="simulate a field battle from a JSON scenario")
    p.add_argument("scenario", help="path to a battle scenario JSON file "
                                    "(see docs/specs/battle-scenario.md)")
    p.add_argument("--seed", type=int, required=True,
                   help="master seed for the battle's RNG stream")
    p.add_argument("--chooser", choices=battle_cli.CHOOSERS, default="first-legal",
                   help="who picks each command (default: first-legal)")
    p.add_argument("--pretty", action="store_true",
                   help="render a text hex board, aligned event log and summary table")
    p.add_argument("--board-every", type=int, default=0, metavar="N",
                   help="with --pretty, also print the board every N commands")
    p.add_argument("--color", action="store_true",
                   help="with --pretty, use ANSI colour when stdout is a terminal")
    p.set_defaults(func=cmd_battle_sim)

    p = sub.add_parser("replay", help="record, verify or inspect a battle replay file")
    rsub = p.add_subparsers(dest="replay_command", required=True, metavar="ACTION")
    r = rsub.add_parser("record", help="play a scenario and write a .h3r replay file")
    r.add_argument("scenario", help="path to a battle scenario JSON file")
    r.add_argument("--seed", type=int, required=True, help="master seed")
    r.add_argument("--chooser", choices=[c for c in battle_cli.CHOOSERS],
                   default="first-legal", help="who picks each command")
    r.add_argument("-o", "--output", required=True, help="replay file to write")
    r = rsub.add_parser("verify", help="replay a file and check all hashes")
    r.add_argument("file", help="path to a .h3r file")
    r = rsub.add_parser("info", help="print the header of a replay file")
    r.add_argument("file", help="path to a .h3r file")
    p.set_defaults(func=cmd_replay)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except _INPUT_ERRORS as exc:
        print(f"h3re: error: {_describe_error(exc)}", file=sys.stderr)
        return EXIT_FAILURE


if __name__ == "__main__":
    sys.exit(main())
