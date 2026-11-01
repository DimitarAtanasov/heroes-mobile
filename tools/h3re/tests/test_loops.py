"""Tests for tools/skills/validate.py: loop contracts, skills and project memory."""
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "skills"))
import validate as V  # noqa: E402

GOOD = """# Loop: x
## Goal and input
a
## State
a
## Actions
a
## Observation
a
## Verification
a
## Stop and escalation
a
## Evidence
a
## Budget
- budget rework: 2
```mermaid
flowchart LR
    start --> work
    work --> check
    check -->|pass| done
    check -->|fail| work
    check -->|spent| escalated
```
"""


def without(text, marker):
    return text.replace(marker, "")


class LoopCheck(unittest.TestCase):
    def errs(self, text):
        return V.check_loop(text, "t")

    def test_good_loop_has_no_problems(self):
        self.assertEqual(self.errs(GOOD), [])

    def test_each_contract_section_is_required(self):
        for f in ("## Goal and input", "## State", "## Actions", "## Observation",
                  "## Verification", "## Stop and escalation", "## Evidence", "## Budget"):
            with self.subTest(section=f):
                self.assertTrue(self.errs(GOOD.replace(f, "## Other")), f)

    def test_missing_graph(self):
        self.assertTrue(any("mermaid" in e for e in self.errs(GOOD.split("```mermaid")[0])))

    def test_no_done_terminal(self):
        bad = GOOD.replace("check -->|pass| done", "check -->|pass| failed")
        self.assertTrue(any("'done'" in e for e in self.errs(bad)))

    def test_terminal_with_exit(self):
        bad = GOOD.replace("```\n", "    done --> work\n```\n", 1) if False else GOOD.replace(
            "    check -->|spent| escalated\n", "    check -->|spent| escalated\n    done --> work\n")
        self.assertTrue(any("terminal 'done' has outgoing" in e for e in self.errs(bad)))

    def test_dead_end_node(self):
        bad = GOOD.replace("    check -->|spent| escalated\n", "    check -->|spent| escalated\n    work --> orphan\n")
        self.assertTrue(any("'orphan' has no exit" in e for e in self.errs(bad)))

    def test_unreachable_node(self):
        bad = GOOD.replace("    check -->|spent| escalated\n", "    check -->|spent| escalated\n    island --> done\n")
        self.assertTrue(any("'island' is unreachable" in e for e in self.errs(bad)))

    def test_node_that_cannot_reach_a_terminal(self):
        bad = GOOD.replace("    check -->|spent| escalated\n",
                           "    check -->|spent| escalated\n    work --> loop_a\n    loop_a --> loop_b\n    loop_b --> loop_a\n")
        self.assertTrue(any("cannot reach any terminal" in e for e in self.errs(bad)))

    def test_cycle_needs_a_budget(self):
        bad = GOOD.replace("- budget rework: 2", "- nothing")
        self.assertTrue(any("cycle but no" in e for e in self.errs(bad)))

    def test_acyclic_graph_needs_no_budget_entry(self):
        acyclic = GOOD.replace("    check -->|fail| work\n", "").replace("- budget rework: 2", "- none")
        self.assertEqual(self.errs(acyclic), [])


class SkillCheck(unittest.TestCase):
    def test_good_skill(self):
        self.assertEqual(V.check_skill("---\nname: a\ndescription: does a thing\n---\nbody\n", "a"), [])

    def test_name_must_match_directory(self):
        self.assertTrue(V.check_skill("---\nname: b\ndescription: d\n---\n", "a"))

    def test_missing_frontmatter_empty_and_long_description(self):
        self.assertTrue(V.check_skill("no frontmatter", "a"))
        self.assertTrue(V.check_skill("---\nname: a\ndescription:\n---\n", "a"))
        self.assertTrue(V.check_skill("---\nname: a\ndescription: " + "x" * 401 + "\n---\n", "a"))

    def test_skill_length_cap(self):
        self.assertTrue(V.check_skill("---\nname: a\ndescription: d\n---\n" + "x\n" * 230, "a"))


class MemoryCheck(unittest.TestCase):
    def make(self, index, notes):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "docs", "memory"))
        with open(os.path.join(d, "docs", "memory", "MEMORY.md"), "w") as f:
            f.write(index)
        for n, t in notes.items():
            with open(os.path.join(d, "docs", "memory", n), "w") as f:
                f.write(t)
        return d

    NOTE = "---\nname: a\ntype: lesson\nupdated: 2026-11-01\nevidence: x\n---\nbody\n"

    def test_good_memory(self):
        d = self.make("- [a](a.md) - hook\n", {"a.md": self.NOTE})
        self.assertEqual(V.check_memory(d), [])

    def test_dead_link_and_unlisted_note(self):
        d = self.make("- [b](b.md) - hook\n", {"a.md": self.NOTE})
        e = V.check_memory(d)
        self.assertTrue(any("dead link b.md" in x for x in e))
        self.assertTrue(any("a.md: not listed" in x for x in e))

    def test_frontmatter_fields(self):
        for bad in (self.NOTE.replace("name: a", "name: z"), self.NOTE.replace("lesson", "story"),
                    self.NOTE.replace("2026-11-01", "yesterday"), self.NOTE.replace("evidence: x", "evidence:")):
            with self.subTest(bad=bad[:40]):
                d = self.make("- [a](a.md) - h\n", {"a.md": bad})
                self.assertTrue(V.check_memory(d))

    def test_index_length_cap(self):
        d = self.make("- [a](a.md) - h\n" + "x\n" * 160, {"a.md": self.NOTE})
        self.assertTrue(any("150 lines" in x for x in V.check_memory(d)))


class RepoFiles(unittest.TestCase):
    def test_repo_loops_skills_and_memory_are_valid(self):
        self.assertEqual(V.validate_repo(ROOT), [])

    def test_expected_artifacts_exist(self):
        for p in (".claude/skills/loop-graph-builder/SKILL.md", ".claude/skills/second-brain/SKILL.md",
                  "docs/loops/agent-round.md", "docs/memory/MEMORY.md"):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, p)), p)


if __name__ == "__main__":
    unittest.main()
