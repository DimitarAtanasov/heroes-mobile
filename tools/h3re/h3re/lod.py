"""Clean-room reader for Heroes of Might and Magic 3 .LOD archives.

Stdlib only. The layout implemented here is described in docs/specs/lod.md.
Every offset and size read from the file is bounds-checked against the
real file size before use, and member names are validated before anything
is written to disk.
"""

from __future__ import annotations

import os
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import BinaryIO

__all__ = [
    "LodArchive",
    "LodEntry",
    "LodError",
    "LodFormatError",
]

MAGIC = b"LOD\x00"
HEADER_SIZE = 92  # magic(4) + version(4) + count(4) + 80 reserved bytes
ENTRY_SIZE = 32  # directory entry stride
NAME_SIZE = 16
MAX_ENTRIES = 1 << 20  # sanity cap on the directory length

_HEADER_COUNT = struct.Struct("<I")
# offset, uncompressed size, type, compressed size (each uint32 LE),
# starting right after the 16-byte name. Each entry is exactly 32 bytes
# (ENTRY_SIZE), so no bytes trail these fields.
_ENTRY_FIELDS = struct.Struct("<IIII")


class LodError(Exception):
    """Base class for LOD archive errors."""


class LodFormatError(LodError, ValueError):
    """The archive is malformed, truncated, or fails a bounds check."""


@dataclass(frozen=True)
class LodEntry:
    name: str
    offset: int
    size: int  # uncompressed size of the member
    type: int  # opaque 32-bit type field from the directory
    packed_size: int  # 0 means the payload is stored raw

    @property
    def compressed(self) -> bool:
        return self.packed_size != 0

    @property
    def stored_size(self) -> int:
        """Number of bytes occupied by the payload in the file."""
        return self.packed_size if self.compressed else self.size


def _key(name: str) -> str:
    # HoMM3 member names are matched case-insensitively.
    return name.upper()


def _decode_name(raw: bytes) -> str:
    end = raw.find(b"\x00")
    if end != -1:
        raw = raw[:end]
    return raw.decode("latin-1")


def _check_member_name(name: str) -> str:
    """Return name if it is safe to use as a single file name, else raise."""
    if not name or name in (".", ".."):
        raise LodFormatError(f"unsafe member name {name!r}")
    for ch in name:
        if ch in "/\\:" or ch == "\x00" or ord(ch) < 0x20:
            raise LodFormatError(f"unsafe member name {name!r}")
    if name != name.strip():
        raise LodFormatError(f"unsafe member name {name!r}")
    return name


class LodArchive:
    """Read-only view of a .LOD archive.

    Use ``LodArchive.open(path)`` for a file on disk, or pass any seekable
    binary file object (with its size) to the constructor. Instances are
    context managers; ``close()`` releases the underlying file only if this
    instance opened it.
    """

    def __init__(
        self,
        fp: BinaryIO,
        size: int,
        *,
        owns_file: bool = False,
        strict: bool = False,
    ) -> None:
        self._fp = fp
        self._size = size
        self._owns_file = owns_file
        self._strict = strict
        # Keyed by upper-cased name. Insertion order = first appearance in the
        # directory; a later duplicate replaces the value in place (last wins).
        self._entries: dict[str, LodEntry] = {}
        try:
            self._parse()
        except BaseException:
            self.close()
            raise

    @classmethod
    def open(cls, path: str | os.PathLike[str], *, strict: bool = False) -> LodArchive:
        fp = open(path, "rb")
        try:
            size = os.fstat(fp.fileno()).st_size
            return cls(fp, size, owns_file=True, strict=strict)
        except BaseException:
            fp.close()
            raise

    def __enter__(self) -> LodArchive:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_file and self._fp is not None and not self._fp.closed:
            self._fp.close()

    # ----------------------------------------------------------------- parsing

    def _read_exact(self, offset: int, length: int) -> bytes:
        if offset < 0 or length < 0 or offset + length > self._size:
            raise LodFormatError(
                f"range [{offset}, {offset + length}) outside file of size {self._size}"
            )
        self._fp.seek(offset)
        data = self._fp.read(length)
        if len(data) != length:
            raise LodFormatError("unexpected end of file")
        return data

    def _parse(self) -> None:
        header = self._read_exact(0, HEADER_SIZE)
        if header[:4] != MAGIC:
            raise LodFormatError("bad magic: not a LOD archive")
        (count,) = _HEADER_COUNT.unpack_from(header, 8)
        if count > MAX_ENTRIES:
            raise LodFormatError(f"entry count {count} exceeds limit")

        directory = self._read_exact(HEADER_SIZE, count * ENTRY_SIZE)
        for index in range(count):
            base = index * ENTRY_SIZE
            name = _decode_name(directory[base : base + NAME_SIZE])
            offset, size, type_, packed = _ENTRY_FIELDS.unpack_from(
                directory, base + NAME_SIZE
            )
            if not name:
                raise LodFormatError(f"entry {index} has an empty name")
            entry = LodEntry(
                name=name,
                offset=offset,
                size=size,
                type=type_,
                packed_size=packed,
            )
            # Validate the payload range now so read() can trust the entry.
            if entry.offset + entry.stored_size > self._size:
                raise LodFormatError(
                    f"entry {name!r} payload [{entry.offset}, "
                    f"{entry.offset + entry.stored_size}) is outside the file"
                )
            key = _key(name)
            if key in self._entries:
                if self._strict:
                    raise LodFormatError(f"duplicate member name {name!r}")
                # Lenient default, matching the engine: the later entry wins.
                # dict assignment keeps the key's first-appearance position.
            self._entries[key] = entry

    # ------------------------------------------------------------------ public

    def list(self) -> list[str]:
        """Member names, one per name, in order of first appearance."""
        return [entry.name for entry in self._entries.values()]

    def entry(self, name: str) -> LodEntry:
        """Directory information for a member. Raises KeyError if absent."""
        return self._entries[_key(name)]

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and _key(name) in self._entries

    def __len__(self) -> int:
        return len(self._entries)

    def read(self, name: str) -> bytes:
        """Return the decompressed contents of a member.

        Raises KeyError if the member does not exist and LodFormatError if its
        payload is corrupt.
        """
        entry = self.entry(name)
        raw = self._read_exact(entry.offset, entry.stored_size)
        if not entry.compressed:
            return raw
        return _inflate(raw, entry)

    def extract_all(self, dest: str | os.PathLike[str]) -> list[Path]:
        """Write every member as a plain file directly inside ``dest``.

        All member names are validated before any file is written. Returns the
        paths written. Existing symlinks at target paths are refused rather
        than followed.
        """
        names = self.list()
        for name in names:
            _check_member_name(name)

        root = Path(dest)
        root.mkdir(parents=True, exist_ok=True)
        root_real = root.resolve()

        written: list[Path] = []
        for name in names:
            target = root / name
            if target.is_symlink():
                raise LodFormatError(f"refusing to write through symlink {target}")
            resolved = target.resolve()
            if os.path.commonpath([root_real, resolved]) != str(root_real):
                raise LodFormatError(f"member {name!r} escapes destination")
            data = self.read(name)
            with open(target, "wb") as out:
                out.write(data)
            written.append(target)
        return written


def _inflate(raw: bytes, entry: LodEntry) -> bytes:
    decomp = zlib.decompressobj()
    try:
        # Cap output at the declared size plus one byte so a stream that
        # expands beyond its declared size is detected without unbounded
        # memory use.
        out = decomp.decompress(raw, entry.size + 1)
    except zlib.error as exc:
        raise LodFormatError(f"entry {entry.name!r}: corrupt zlib data: {exc}") from exc
    if decomp.unconsumed_tail or len(out) > entry.size:
        raise LodFormatError(
            f"entry {entry.name!r}: decompressed data exceeds declared size {entry.size}"
        )
    if not decomp.eof:
        raise LodFormatError(f"entry {entry.name!r}: truncated zlib stream")
    if len(out) != entry.size:
        raise LodFormatError(
            f"entry {entry.name!r}: decompressed to {len(out)} bytes, "
            f"expected {entry.size}"
        )
    return out
