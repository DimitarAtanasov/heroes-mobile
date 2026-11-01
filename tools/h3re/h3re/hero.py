"""Reference simulation core for heroes: experience, levels, primary and
secondary skill gain.

Spec: docs/specs/hero.md (built on rules.md section 5 and engine-design.md
section 1.3). Clean-room: written from those specs only.

Design (same as battle.py / adventure.py):

* State is immutable (frozen dataclasses, tuples, ints, strings, bools). The
  hero rules and the hero's class (loaded from a JSON pack such as
  ``data/hero_test.json``) are part of the state, so they are part of the hash.
* ``apply(state, cmd, rng) -> (state', events)`` is the only way to advance a
  hero. An illegal command raises ``IllegalCommand`` before any draw.
* ``rng`` is the hero's own named stream ``hero:<hero_id>``
  (``hero_rng(master_seed, hero_id)``); one state holds one hero, so a stream
  is never shared between heroes or with another feature.
* Integers only. Weighted choices draw one ``rng.range(0, total)`` each.
"""

import hashlib
import json
from dataclasses import asdict, dataclass, replace

from .datapack import MAX_INT, SCHEMA_VERSION, DataPackError, _int, _list, _obj, _read
from .rng import derive_stream

__all__ = [
    "PRIMARY", "HeroPolicy", "DEFAULT_POLICY", "HeroRules", "HeroClass", "HeroContent",
    "SecondarySkill", "SkillOffer", "Hero", "HeroState", "IllegalCommand",
    "GainXP", "ChooseSkill",
    "XPGained", "LevelGained", "PrimaryGained", "SkillOffered", "SkillLearned",
    "parse_hero_pack", "load_hero_pack", "content_hash", "find_class",
    "hero_rng", "level_for_xp", "create_hero", "apply", "canonical", "state_hash",
]

PRIMARY = ("attack", "defense", "power", "knowledge")   # rules.md 5.1, draw order

_OFFER_MODES = ("upgrade_and_new", "weighted_pair")
_OFFER_FILLS = ("other_kind", "single")


# --------------------------------------------------------------------------
# Policy
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class HeroPolicy:
    """Switchable rules for [uncertain] items (docs/specs/hero.md section 6)."""

    # rules.md 5.3: how the two level-up offers are generated.
    # "upgrade_and_new": one upgrade of a held skill, then one new skill, each
    # drawn by class weight. "weighted_pair": two distinct draws by class
    # weight from all upgrades and new skills together.
    offer_mode: str = "upgrade_and_new"
    # upgrade_and_new only: when one kind has no candidate, offer two of the
    # other kind ("other_kind") or just one ("single").
    offer_fill: str = "other_kind"

    def __post_init__(self):
        if self.offer_mode not in _OFFER_MODES:
            raise ValueError("bad offer_mode %r" % (self.offer_mode,))
        if self.offer_fill not in _OFFER_FILLS:
            raise ValueError("bad offer_fill %r" % (self.offer_fill,))


DEFAULT_POLICY = HeroPolicy()


# --------------------------------------------------------------------------
# Content (loaded from a hero pack; stored in the state)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class HeroRules:
    xp_table: tuple                 # total XP for level 1, 2, ... (strictly increasing)
    max_secondary: int              # secondary skill slots
    skill_levels: int               # Basic .. Expert
    primary_high_from_level: int    # first level that uses primary_high
    skills: tuple                   # secondary skill ids, sorted


@dataclass(frozen=True)
class HeroClass:
    id: str
    start_primary: tuple            # in PRIMARY order
    primary_low: tuple              # weights, in PRIMARY order
    primary_high: tuple
    secondary_weights: tuple        # (skill, weight) pairs in HeroRules.skills order


@dataclass(frozen=True)
class HeroContent:
    rules: HeroRules
    classes: tuple                  # HeroClass, sorted by id


def _weights(v, path):
    w = tuple(_int(x, "%s[%d]" % (path, i), 0, MAX_INT)
              for i, x in enumerate(_list(v, path, len(PRIMARY))))
    if sum(w) <= 0:
        raise DataPackError("%s: weights must have a positive total" % path)
    return w


def _check_class(c, path, skills):
    _obj(c, path, ("id", "start_primary", "primary_low", "primary_high", "secondary"))
    cid = c["id"]
    if type(cid) is not str or not cid.strip():
        raise DataPackError("%s.id: expected non-empty string" % path)
    start = tuple(_int(x, "%s.start_primary[%d]" % (path, i), 0, 1000)
                  for i, x in enumerate(_list(c["start_primary"], path + ".start_primary",
                                              len(PRIMARY))))
    sec = _obj(c["secondary"], path + ".secondary", skills)
    pairs = tuple((s, _int(sec[s], "%s.secondary.%s" % (path, s), 0, MAX_INT)) for s in skills)
    return HeroClass(cid, start, _weights(c["primary_low"], path + ".primary_low"),
                     _weights(c["primary_high"], path + ".primary_high"), pairs)


_KEYS = ("schema_version", "xp_table", "max_secondary", "skill_levels",
         "primary_high_from_level", "skills", "classes")


def parse_hero_pack(obj):
    """Validate an already-decoded hero pack and return a HeroContent."""
    _obj(obj, "hero", _KEYS)
    if _int(obj["schema_version"], "hero.schema_version", 0, MAX_INT) != SCHEMA_VERSION:
        raise DataPackError("hero.schema_version: unsupported")
    xp = tuple(_int(x, "hero.xp_table[%d]" % i, 0, MAX_INT)
               for i, x in enumerate(_list(obj["xp_table"], "hero.xp_table")))
    if not xp:
        raise DataPackError("hero.xp_table: must not be empty")
    if xp[0] != 0:
        raise DataPackError("hero.xp_table: must start at 0")
    if any(a >= b for a, b in zip(xp, xp[1:])):
        raise DataPackError("hero.xp_table: must be strictly increasing")
    raw_skills = _list(obj["skills"], "hero.skills")
    for i, s in enumerate(raw_skills):
        if type(s) is not str or not s.strip():
            raise DataPackError("hero.skills[%d]: expected non-empty string" % i)
    if len(set(raw_skills)) != len(raw_skills):
        raise DataPackError("hero.skills: duplicate skill")
    skills = tuple(sorted(raw_skills))
    rules = HeroRules(
        xp_table=xp,
        max_secondary=_int(obj["max_secondary"], "hero.max_secondary", 0, 1000),
        skill_levels=_int(obj["skill_levels"], "hero.skill_levels", 1, 100),
        primary_high_from_level=_int(obj["primary_high_from_level"],
                                     "hero.primary_high_from_level", 2, MAX_INT),
        skills=skills)
    by_id = {}
    for i, c in enumerate(_list(obj["classes"], "hero.classes")):
        hc = _check_class(c, "hero.classes[%d]" % i, skills)
        if hc.id in by_id:
            raise DataPackError("hero.classes: duplicate class %r" % (hc.id,))
        by_id[hc.id] = hc
    if not by_id:
        raise DataPackError("hero.classes: must not be empty")
    return HeroContent(rules, tuple(by_id[k] for k in sorted(by_id)))


def load_hero_pack(path):
    """Read and validate a hero pack file (floats and duplicate keys rejected)."""
    return parse_hero_pack(_read((path,))[0])


def _canon_bytes(obj):
    return json.dumps(asdict(obj), sort_keys=True, separators=(",", ":")).encode("utf-8")


def content_hash(content):
    """SHA-256 of the canonical JSON of validated content (logs and tests)."""
    return hashlib.sha256(_canon_bytes(content)).hexdigest()


def find_class(content, class_id):
    for c in content.classes:
        if c.id == class_id:
            return c
    raise KeyError(class_id)


# --------------------------------------------------------------------------
# State, commands, events
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class SecondarySkill:
    skill: str
    level: int                      # 1 = Basic .. skill_levels = Expert


@dataclass(frozen=True)
class SkillOffer:
    skill: str
    level: int                      # the level the hero would have: 1 = new skill


@dataclass(frozen=True)
class Hero:
    id: str
    hero_class: str
    level: int
    xp: int
    attack: int
    defense: int
    power: int
    knowledge: int
    secondary: tuple = ()           # SecondarySkill, in the order learned
    offer: tuple = ()               # pending SkillOffer choices (empty = none)


@dataclass(frozen=True)
class HeroState:
    policy: HeroPolicy
    rules: HeroRules
    class_def: HeroClass
    hero: Hero


class IllegalCommand(ValueError):
    """Command rejected; state untouched, no RNG draw."""


@dataclass(frozen=True)
class GainXP:
    hero: str
    amount: int


@dataclass(frozen=True)
class ChooseSkill:
    hero: str
    index: int                      # into Hero.offer


@dataclass(frozen=True)
class XPGained:
    hero: str
    amount: int
    xp: int


@dataclass(frozen=True)
class LevelGained:
    hero: str
    level: int


@dataclass(frozen=True)
class PrimaryGained:
    hero: str
    skill: str
    value: int


@dataclass(frozen=True)
class SkillOffered:
    hero: str
    level: int
    offers: tuple


@dataclass(frozen=True)
class SkillLearned:
    hero: str
    skill: str
    level: int


# --------------------------------------------------------------------------
# Rules
# --------------------------------------------------------------------------

def hero_rng(master_seed, hero_id):
    """The hero's named stream: ``hero:<hero_id>``."""
    return derive_stream(master_seed, "hero:%s" % (hero_id,))


def level_for_xp(xp, xp_table):
    """Highest level whose XP threshold is reached. Beyond the table's last
    entry the level stays at the table's top (rules.md 9.9 is open)."""
    return sum(1 for t in xp_table if t <= xp)


def _weighted_index(rng, weights):
    """One draw: index i with probability weights[i] / sum(weights)."""
    r = rng.range(0, sum(weights))
    for i, w in enumerate(weights):
        if r < w:
            return i
        r -= w
    raise AssertionError("unreachable")


def _draw(rng, cands, weight, n):
    """Up to ``n`` distinct candidates, weighted, without replacement."""
    pool, out = list(cands), []
    while pool and len(out) < n:
        out.append(pool.pop(_weighted_index(rng, [weight[c.skill] for c in pool])))
    return out


def _offers(state, h, rng):
    rules, pol = state.rules, state.policy
    weight = dict(state.class_def.secondary_weights)
    held = {s.skill: s.level for s in h.secondary}
    ups = tuple(SkillOffer(s, held[s] + 1) for s in rules.skills
                if s in held and held[s] < rules.skill_levels and weight[s] > 0)
    news = ()
    if len(h.secondary) < rules.max_secondary:
        news = tuple(SkillOffer(s, 1) for s in rules.skills if s not in held and weight[s] > 0)
    if pol.offer_mode == "weighted_pair":
        return tuple(_draw(rng, ups + news, weight, 2))
    if ups and news:
        return (_draw(rng, ups, weight, 1)[0], _draw(rng, news, weight, 1)[0])
    return tuple(_draw(rng, ups or news, weight, 2 if pol.offer_fill == "other_kind" else 1))


def _advance(state, rng, events):
    """Take every level the XP allows, stopping at the first pending offer.
    Per level, draw order: primary skill, then the offers (upgrade first)."""
    h, rules, cls = state.hero, state.rules, state.class_def
    target = level_for_xp(h.xp, rules.xp_table)
    while not h.offer and h.level < target:
        lvl = h.level + 1
        table = cls.primary_high if lvl >= rules.primary_high_from_level else cls.primary_low
        name = PRIMARY[_weighted_index(rng, table)]
        h = replace(h, level=lvl, **{name: getattr(h, name) + 1})
        events.append(LevelGained(h.id, lvl))
        events.append(PrimaryGained(h.id, name, getattr(h, name)))
        offers = _offers(state, h, rng)
        if offers:
            h = replace(h, offer=offers)
            events.append(SkillOffered(h.id, lvl, offers))
    return replace(state, hero=h)


# --------------------------------------------------------------------------
# Setup, canonical form, hash
# --------------------------------------------------------------------------

def create_hero(hero_id, class_id, content, secondary=(), policy=DEFAULT_POLICY):
    """A level-1 hero with 0 XP and the class's starting primary skills.
    ``secondary``: starting (skill, level) pairs, kept in the given order."""
    try:
        cls = find_class(content, class_id)
    except KeyError:
        raise ValueError("unknown hero class %r" % (class_id,)) from None
    rules = content.rules
    sec, seen = [], set()
    for entry in secondary:
        skill, level = tuple(entry) if not isinstance(entry, SecondarySkill) else (
            entry.skill, entry.level)
        if skill not in rules.skills:
            raise ValueError("unknown skill %r" % (skill,))
        if skill in seen:
            raise ValueError("duplicate skill %r" % (skill,))
        if not (type(level) is int and 1 <= level <= rules.skill_levels):
            raise ValueError("bad skill level %r for %r" % (level, skill))
        seen.add(skill)
        sec.append(SecondarySkill(skill, level))
    if len(sec) > rules.max_secondary:
        raise ValueError("at most %d secondary skills" % rules.max_secondary)
    a, d, p, k = cls.start_primary
    h = Hero(str(hero_id), cls.id, 1, 0, a, d, p, k, tuple(sec))
    return HeroState(policy, rules, cls, h)


def canonical(state):
    """Canonical byte form of the state (ADR-0001)."""
    return _canon_bytes(state)


def state_hash(state):
    return hashlib.sha256(canonical(state)).hexdigest()


# --------------------------------------------------------------------------
# apply
# --------------------------------------------------------------------------

def _validate(state, cmd):
    if not isinstance(cmd, (GainXP, ChooseSkill)):
        raise IllegalCommand("unknown command %r" % (cmd,))
    h = state.hero
    if cmd.hero != h.id:
        raise IllegalCommand("not hero %r" % (cmd.hero,))
    if isinstance(cmd, GainXP):
        if type(cmd.amount) is not int or cmd.amount <= 0:
            raise IllegalCommand("XP amount must be a positive integer")
        if h.offer:
            raise IllegalCommand("level-up offer pending: choose a skill first")
        return
    if not h.offer:
        raise IllegalCommand("no pending offer")
    if not (type(cmd.index) is int and 0 <= cmd.index < len(h.offer)):
        raise IllegalCommand("no such offer %r" % (cmd.index,))


def apply(state, cmd, rng):
    """Apply one command. Returns (new_state, events). ``rng`` must be the
    hero's stream ``hero_rng(master_seed, state.hero.id)``."""
    _validate(state, cmd)
    h = state.hero
    events = []
    if isinstance(cmd, GainXP):
        h = replace(h, xp=h.xp + cmd.amount)
        events.append(XPGained(h.id, cmd.amount, h.xp))
    else:
        o = h.offer[cmd.index]
        if o.level == 1:
            sec = h.secondary + (SecondarySkill(o.skill, 1),)
        else:
            sec = tuple(SecondarySkill(s.skill, o.level) if s.skill == o.skill else s
                        for s in h.secondary)
        h = replace(h, secondary=sec, offer=())
        events.append(SkillLearned(h.id, o.skill, o.level))
    state = _advance(replace(state, hero=h), rng, events)
    return state, tuple(events)
