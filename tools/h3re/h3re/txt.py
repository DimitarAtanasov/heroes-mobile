"""Generic reader for HoMM3-style tab-separated TXT tables.

Default semantics (see docs/specs/txt.md): text in a selectable encoding
(default cp1252), fields separated by TAB, records terminated by CR LF only
(a bare LF is data), and double-quote quoting (a field starting with a quote
runs to the closing quote; a doubled quote inside is one literal quote).
Rows are returned exactly as found (ragged rows are not padded or truncated).
Column meanings are not interpreted here.

Options ``lenient_newlines=True`` (bare LF also ends a record) and
``quoting=False`` (quote characters are ordinary data) restore the previous
behaviour of this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

__all__ = ["TxtError", "TxtTable", "parse_txt", "read_txt", "MAX_BYTES", "MAX_LINES"]

MAX_BYTES = 16 * 1024 * 1024
MAX_LINES = 200_000
_BOM = b"\xef\xbb\xbf"
DEFAULT_ENCODING = "cp1252"
_STRICT_SEP = re.compile(r"\t|\r\n")
_LENIENT_SEP = re.compile(r"\t|\r?\n")


class TxtError(ValueError):
    """Raised for oversized, undecodable, or otherwise invalid TXT input."""


@dataclass(frozen=True)
class TxtTable:
    header: tuple[tuple[str, ...], ...]
    rows: tuple[tuple[str, ...], ...]


def _scan(text: str, quoting: bool, lenient: bool, max_lines: int) -> list[tuple[str, ...]]:
    sep = (_LENIENT_SEP if lenient else _STRICT_SEP).search
    n = len(text)
    records: list[tuple[str, ...]] = []
    fields: list[str] = []
    i = 0
    while i < n:
        parts: list[str] = []
        if quoting and text[i] == '"':
            j = i + 1
            while True:
                k = text.find('"', j)
                if k == -1:
                    break  # unterminated: field ends at the next TAB / record end
                if text.startswith('"', k + 1):  # doubled quote -> literal quote
                    parts.append(text[j:k + 1])
                    j = k + 2
                    continue
                parts.append(text[j:k])
                j = k + 1
                break
            i = j
        m = sep(text, i)
        if m is None:
            parts.append(text[i:])
            fields.append("".join(parts))
            records.append(tuple(fields))
            fields = []
            i = n
            break
        parts.append(text[i:m.start()])
        fields.append("".join(parts))
        i = m.end()
        if m.group() != "\t":
            records.append(tuple(fields))
            fields = []
            if len(records) > max_lines:
                raise TxtError(f"input exceeds cap of {max_lines} lines")
        elif i >= n:  # trailing TAB at end of data: empty last field
            fields.append("")
            records.append(tuple(fields))
            fields = []
    if len(records) > max_lines:
        raise TxtError(f"input has {len(records)} lines, exceeds cap of {max_lines}")
    return records


def parse_txt(
    data: bytes,
    header_rows: int = 0,
    *,
    max_bytes: int = MAX_BYTES,
    max_lines: int = MAX_LINES,
    encoding: str = DEFAULT_ENCODING,
    lenient_newlines: bool = False,
    quoting: bool = True,
) -> TxtTable:
    """Parse tab-separated TXT bytes into a TxtTable.

    The first ``header_rows`` records become ``header``; the rest are ``rows``.
    ``encoding`` is any Python codec name (cp1252, cp1250, cp1251, gbk, utf-8...).
    ``lenient_newlines=True`` also accepts a bare LF as a record terminator.
    ``quoting=False`` treats double quotes as ordinary data.
    """
    if not isinstance(header_rows, int) or isinstance(header_rows, bool) or header_rows < 0:
        raise TxtError(f"header_rows must be a non-negative int, got {header_rows!r}")
    data = bytes(data)
    if len(data) > max_bytes:
        raise TxtError(f"input is {len(data)} bytes, exceeds cap of {max_bytes}")
    if data.startswith(_BOM):
        data = data[len(_BOM):]
    try:
        text = data.decode(encoding)
    except LookupError as exc:
        raise TxtError(f"unknown encoding {encoding!r}") from exc
    except UnicodeDecodeError as exc:
        raise TxtError(f"not valid {encoding}: {exc}") from exc
    if not text:
        return TxtTable((), ())
    parsed = _scan(text, bool(quoting), bool(lenient_newlines), max_lines)
    return TxtTable(tuple(parsed[:header_rows]), tuple(parsed[header_rows:]))


def read_txt(
    path: str | Path,
    header_rows: int = 0,
    *,
    max_bytes: int = MAX_BYTES,
    max_lines: int = MAX_LINES,
    encoding: str = DEFAULT_ENCODING,
    lenient_newlines: bool = False,
    quoting: bool = True,
) -> TxtTable:
    """Read a TXT file from disk; the size cap is checked before reading."""
    p = Path(path)
    size = p.stat().st_size
    if size > max_bytes:
        raise TxtError(f"{p} is {size} bytes, exceeds cap of {max_bytes}")
    return parse_txt(
        p.read_bytes(),
        header_rows,
        max_bytes=max_bytes,
        max_lines=max_lines,
        encoding=encoding,
        lenient_newlines=lenient_newlines,
        quoting=quoting,
    )
