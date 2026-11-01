"""Generic reader for HoMM3-style tab-separated TXT tables.

The format is deliberately simple: cp1252 text, fields separated by TAB,
records terminated by CRLF or LF. There is no quoting; quote characters are
ordinary data. Rows are returned exactly as found (ragged rows are not padded
or truncated). Column meanings are not interpreted here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = ["TxtError", "TxtTable", "parse_txt", "read_txt", "MAX_BYTES", "MAX_LINES"]

MAX_BYTES = 16 * 1024 * 1024
MAX_LINES = 200_000
_BOM = b"\xef\xbb\xbf"


class TxtError(ValueError):
    """Raised for oversized, undecodable, or otherwise invalid TXT input."""


@dataclass(frozen=True)
class TxtTable:
    header: tuple[tuple[str, ...], ...]
    rows: tuple[tuple[str, ...], ...]


def parse_txt(
    data: bytes,
    header_rows: int = 0,
    *,
    max_bytes: int = MAX_BYTES,
    max_lines: int = MAX_LINES,
) -> TxtTable:
    """Parse tab-separated TXT bytes into a TxtTable.

    The first ``header_rows`` lines become ``header``; the rest are ``rows``.
    """
    if not isinstance(header_rows, int) or isinstance(header_rows, bool) or header_rows < 0:
        raise TxtError(f"header_rows must be a non-negative int, got {header_rows!r}")
    data = bytes(data)
    if len(data) > max_bytes:
        raise TxtError(f"input is {len(data)} bytes, exceeds cap of {max_bytes}")
    if data.startswith(_BOM):
        data = data[len(_BOM):]
    try:
        text = data.decode("cp1252")
    except UnicodeDecodeError as exc:
        raise TxtError(f"not valid cp1252: {exc}") from exc
    if not text:
        return TxtTable((), ())
    lines = text.split("\n")
    if lines[-1] == "":  # final line terminator, not an extra record
        lines.pop()
    if len(lines) > max_lines:
        raise TxtError(f"input has {len(lines)} lines, exceeds cap of {max_lines}")
    parsed = []
    for line in lines:
        if line.endswith("\r"):
            line = line[:-1]
        parsed.append(tuple(line.split("\t")))
    return TxtTable(tuple(parsed[:header_rows]), tuple(parsed[header_rows:]))


def read_txt(
    path: str | Path,
    header_rows: int = 0,
    *,
    max_bytes: int = MAX_BYTES,
    max_lines: int = MAX_LINES,
) -> TxtTable:
    """Read a TXT file from disk; the size cap is checked before reading."""
    p = Path(path)
    size = p.stat().st_size
    if size > max_bytes:
        raise TxtError(f"{p} is {size} bytes, exceeds cap of {max_bytes}")
    return parse_txt(p.read_bytes(), header_rows, max_bytes=max_bytes, max_lines=max_lines)
