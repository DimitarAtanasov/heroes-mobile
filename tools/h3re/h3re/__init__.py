"""h3re: clean-room readers for Heroes of Might and Magic 3 file formats."""

from .lod import LodArchive, LodEntry, LodError, LodFormatError

__all__ = ["LodArchive", "LodEntry", "LodError", "LodFormatError"]
