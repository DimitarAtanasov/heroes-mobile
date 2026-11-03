"""Battle roster built from a parsed CRTRAITS (docs/specs/roster-from-crtraits.md, slice 3).

Pure: no I/O, no hashing. Not a simulation module.
"""

from __future__ import annotations

from .content import ContentResult


def battle_roster(content: ContentResult) -> list:
    """Creatures offered for battle, in file order.

    Creatures with no fixed damage (dmg 0/0, ContentResult.no_fixed_damage) are left out
    (owner decision, 2026-11-02): battle creation refuses them. Weak creatures (dmg_min 0,
    dmg_max >= 1) are kept.
    """
    return [c for c in content.creatures if c["name"] not in content.no_fixed_damage]
