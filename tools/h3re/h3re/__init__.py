"""h3re: clean-room readers for Heroes of Might and Magic 3 file formats.

Importing this package has no side effects: no files are opened and nothing
is printed. Each submodule only depends on the standard library or on
``defimg`` (used by ``pcx``), so there are no circular imports.
"""

from . import battle
from .defimg import (
    Block,
    DefError,
    DefFile,
    EmptyImageError,
    Frame,
    frame_is_empty,
    frame_to_canvas,
    frame_to_png,
    parse_def,
    to_rgb,
    to_rgba,
    write_png,
    write_ppm,
)
from .h3m import H3mError, H3mHeader, PlayerInfo, parse_h3m, parse_h3m_bytes
from .lod import LodArchive, LodEntry, LodError, LodFormatError
from .pcx import PcxError, PcxImage, parse_pcx
from .rng import Pcg32, RngStreams, derive_stream
from .rules import (
    apply_damage,
    attack_defense_factor,
    bad_morale_chance,
    base_damage,
    damage_from_base,
    damage_range,
    good_morale_chance,
    luck_chance,
)
from .txt import TxtError, TxtTable, parse_txt, read_txt

__all__ = [
    # submodule (its names are generic, e.g. apply/Stack, so not re-exported)
    "battle",
    # defimg
    "Block",
    "DefError",
    "DefFile",
    "EmptyImageError",
    "Frame",
    "frame_is_empty",
    "frame_to_canvas",
    "frame_to_png",
    "parse_def",
    "to_rgb",
    "to_rgba",
    "write_png",
    "write_ppm",
    # h3m
    "H3mError",
    "H3mHeader",
    "PlayerInfo",
    "parse_h3m",
    "parse_h3m_bytes",
    # lod
    "LodArchive",
    "LodEntry",
    "LodError",
    "LodFormatError",
    # pcx
    "PcxError",
    "PcxImage",
    "parse_pcx",
    # rng
    "Pcg32",
    "RngStreams",
    "derive_stream",
    # rules
    "apply_damage",
    "attack_defense_factor",
    "bad_morale_chance",
    "base_damage",
    "damage_from_base",
    "damage_range",
    "good_morale_chance",
    "luck_chance",
    # txt
    "TxtError",
    "TxtTable",
    "parse_txt",
    "read_txt",
]
