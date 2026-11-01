import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "lint")))

import kotlin_banned_api_lint as K  # noqa: E402


def rules(src):
    return sorted({v.rule for v in K.lint_source(src)})


GOOD = '''
package h3.sim

import java.math.BigInteger
import java.nio.charset.StandardCharsets
import java.util.Locale
import kotlin.math.abs
import kotlin.math.max

// Double x = 1.0 in a comment; System.currentTimeMillis(); HashMap
/* block /* nested */ Thread.sleep(1) println("x") */
object Ok {
    val hex = 0x1F + 0b101
    val big = 1_000L
    fun f(a: Int, b: Int): Int {
        val m = LinkedHashMap<Int, Int>()
        val s = linkedSetOf(3, 1)
        val range = 1..5
        val t = "1.5 Double HashMap println(x) \\" Thread"
        val raw = """Math.sqrt(2.0) System.getenv("A")"""
        val c = '"'
        val bytes = "abc".toByteArray(StandardCharsets.UTF_8)
        val str = String(bytes, Charsets.UTF_8)
        val u = "a".uppercase() + "b".toUpperCase(Locale.ROOT)
        val fm = "%d".format(Locale.ROOT, a)
        return Math.floorDiv(a, b) + Math.addExact(a, b) + abs(a) + max(a, b) + m.size + s.size
    }
}
'''

BAD = [
    ("KT_FLOAT", "val x: Double = 0"),
    ("KT_FLOAT", "val x: Float = 0"),
    ("KT_FLOAT", "val x = 1.5"),
    ("KT_FLOAT", "val x = 1f"),
    ("KT_FLOAT", "val x = 2e3"),
    ("KT_FLOAT", "val x = .5"),
    ("KT_FLOAT", "val x = a.toDouble()"),
    ("KT_FLOAT", "val x = a.toFloat()"),
    ("KT_FLOAT", "val x = DoubleArray(3)"),
    ("KT_FLOAT", 'val x = "${1.5}"'),
    ("KT_MATH", "val x = Math.sqrt(a)"),
    ("KT_MATH", "val x = java.lang.Math.pow(a, b)"),
    ("KT_MATH", "val x = kotlin.math.floor(a)"),
    ("KT_MATH", "import kotlin.math.sqrt"),
    ("KT_MATH", "import kotlin.math.*"),
    ("KT_CLOCK", "val t = System.currentTimeMillis()"),
    ("KT_CLOCK", "val t = System.nanoTime()"),
    ("KT_CLOCK", "import java.time.Instant"),
    ("KT_CLOCK", "val t = java.time.LocalDate.now()"),
    ("KT_RANDOM", "val r = java.util.Random(1)"),
    ("KT_RANDOM", "import kotlin.random.Random"),
    ("KT_RANDOM", "val r = Math.random()"),
    ("KT_THREAD", "val t = Thread { }"),
    ("KT_THREAD", "val e = Executors.newFixedThreadPool(2)"),
    ("KT_THREAD", "import kotlinx.coroutines.launch"),
    ("KT_UNORDERED", "val m = HashMap<Int, Int>()"),
    ("KT_UNORDERED", "val s = HashSet<Int>()"),
    ("KT_UNORDERED", "val m = mutableMapOf<Int, Int>()"),
    ("KT_UNORDERED", "val s = mutableSetOf<Int>()"),
    ("KT_CHARSET", "val b = s.toByteArray()"),
    ("KT_CHARSET", "val s = String(bytes)"),
    ("KT_CHARSET", "val s = f.readText()"),
    ("KT_CHARSET", "val s = InputStreamReader(ins)"),
    ("KT_LOCALE", 'val s = String.format("%d", a)'),
    ("KT_LOCALE", 'val s = "%d".format(a)'),
    ("KT_LOCALE", "val s = x.toUpperCase()"),
    ("KT_LOCALE", "val s = x.toLowerCase()"),
    ("KT_ENV", 'val s = System.getenv("A")'),
    ("KT_ENV", 'val s = System.getProperty("a")'),
    ("KT_PRINT", 'fun f() { println("x") }'),
    ("KT_PRINT", "val s = System.out"),
]


class KotlinLintTests(unittest.TestCase):
    def test_good_fixture_is_clean(self):
        self.assertEqual([str(v) for v in K.lint_source(GOOD)], [])

    def test_every_rule_has_a_bad_fixture(self):
        self.assertEqual(sorted({r for r, _ in BAD}), sorted(K.RULES))

    def test_bad_fixtures_each_flag_their_rule(self):
        for rule, src in BAD:
            with self.subTest(rule=rule, src=src):
                self.assertIn(rule, rules("object A {\n%s\n}\n" % src))

    def test_bad_fixtures_via_temp_files(self):
        with tempfile.TemporaryDirectory() as d:
            for i, (rule, src) in enumerate(BAD):
                p = os.path.join(d, "F%d.kt" % i)
                with open(p, "w", encoding="utf-8") as f:
                    f.write("object A {\n%s\n}\n" % src)
                viol = K.lint_paths([p])
                self.assertIn(rule, {v.rule for v in viol}, src)
                self.assertTrue(all(v.line == 2 for v in viol), src)

    def test_comments_and_strings_do_not_trigger(self):
        for src in ('// val x = 1.5 Double\n', '/* HashMap println(1) */\n',
                    '/* a /* nested */ Thread */ val x = 1\n',
                    'val s = "Double 1.5 System.nanoTime() HashMap"\n',
                    'val s = """\nMath.sqrt(2.0)\nprintln(1)\n"""\n',
                    'val s = "esc \\" Thread \\\\"\n', "val c = '\"'; val d = '\\''\n",
                    'val s = "${a} HashMap"\n'):
            with self.subTest(src=src):
                self.assertEqual(rules(src), [])

    def test_template_code_is_still_scanned(self):
        self.assertEqual(rules('val s = "x ${System.nanoTime()} y"\n'), ["KT_CLOCK"])

    def test_strip_preserves_layout(self):
        src = 'val a = "x\\"y" // c\n/* m\nn */ val b = \'z\'\n"""r\nr"""\n'
        out = K.strip_source(src)
        self.assertEqual(len(out), len(src))
        self.assertEqual(out.count("\n"), src.count("\n"))

    def test_line_numbers(self):
        v = K.lint_source("a\nb\n\nval x = 1.5\n")
        self.assertEqual([(x.line, x.rule) for x in v], [(4, "KT_FLOAT")])

    def test_allowed_math_and_collections(self):
        for src in ("val a = Math.floorDiv(x, y)", "val a = Math.addExact(x, y)",
                    "val a = Math.multiplyExact(x, y)", "val a = LinkedHashMap<Int, Int>()",
                    "val a = linkedMapOf<Int, Int>()", "val a = m.toSortedMap()",
                    "val s = x.uppercase()", 'val s = "%d".format(Locale.ROOT, 1)',
                    "val b = s.toByteArray(Charsets.UTF_8)", "val r = 1..5", "val h = 0xFF"):
            with self.subTest(src=src):
                self.assertEqual(rules("object A { %s }\n" % src), [])

    def test_inline_allow(self):
        ok = "val m = HashMap<Int, Int>() // det-lint-allow: KT_UNORDERED -- lookup only\n"
        self.assertEqual(rules(ok), [])
        self.assertEqual(rules("val m = HashMap<Int, Int>() // det-lint-allow: KT_UNORDERED\n"),
                         ["KT_UNORDERED"])
        self.assertEqual(rules("val m = HashMap<Int, Int>() // det-lint-allow: KT_FLOAT -- x\n"),
                         ["KT_UNORDERED"])


class AllowlistTests(unittest.TestCase):
    SRC = ("object A {\n"
           "    fun f() {\n"
           "        val seen = HashSet<Int>()\n"
           "        val other = HashSet<Int>()\n"
           "    }\n"
           "    fun g() {\n"
           "        val seen = HashSet<Int>()\n"
           "    }\n"
           "}\n")

    def entry(self, **kw):
        e = {"file": "A.kt", "rule": "KT_UNORDERED", "line": "val seen = HashSet<Int>()",
             "justification": "membership only"}
        e.update(kw)
        return e

    def run_lint(self, entries):
        unused = []
        v = K.apply_allowlist(K.lint_source(self.SRC, "/x/A.kt"), entries, unused)
        return v, unused

    def test_line_scoped_entry_absorbs_only_count(self):
        v, unused = self.run_lint([self.entry()])
        # two identical lines (f and g): count 1 absorbs one, the other is reported
        self.assertEqual(sorted(x.line for x in v), [4, 7])
        self.assertEqual(unused, [])

    def test_count_two_absorbs_both_identical_lines_but_not_new_ones(self):
        v, _ = self.run_lint([self.entry(count=2)])
        self.assertEqual([x.line for x in v], [4])

    def test_new_violation_in_allowlisted_function_is_flagged(self):
        v, _ = self.run_lint([self.entry(count=2)])
        self.assertEqual(len(v), 1)
        self.assertIn("other", v[0].text)

    def test_other_rule_or_file_not_covered(self):
        self.assertEqual(len(self.run_lint([self.entry(rule="KT_FLOAT")])[0]), 3)
        self.assertEqual(len(self.run_lint([self.entry(file="B.kt")])[0]), 3)

    def test_unused_entry_reported(self):
        _, unused = self.run_lint([self.entry(line="val nothing = 1")])
        self.assertEqual(len(unused), 1)

    def test_validation(self):
        with tempfile.TemporaryDirectory() as d:
            for bad in ([self.entry(justification="")], [self.entry(line="")],
                        [self.entry(rule="NOPE")], [self.entry(count=0)], {"a": 1}):
                p = os.path.join(d, "al.json")
                with open(p, "w") as f:
                    json.dump(bad, f)
                with self.assertRaises(ValueError):
                    K.load_allowlist(p)
            p = os.path.join(d, "ok.json")
            with open(p, "w") as f:
                json.dump([self.entry()], f)
            self.assertEqual(len(K.load_allowlist(p)), 1)


class RealSourcesTests(unittest.TestCase):
    def test_real_sources_clean_with_committed_allowlist(self):
        paths = K.default_paths(K.DEFAULT_ROOT)
        self.assertTrue(paths, "no Kotlin sources found")
        unused = []
        viol = K.lint_paths(paths, K.load_allowlist(K.DEFAULT_ALLOWLIST), unused)
        self.assertEqual([str(v) for v in viol], [])
        self.assertEqual(unused, [], "stale allowlist entries")

    def test_main_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "Bad.kt")
            with open(p, "w") as f:
                f.write("val x = 1.5\n")
            self.assertEqual(K.main([p, "--allowlist", os.path.join(d, "none.json")]), 1)
            with open(p, "w") as f:
                f.write("val x = 1\n")
            self.assertEqual(K.main([p, "--allowlist", os.path.join(d, "none.json")]), 0)


if __name__ == "__main__":
    unittest.main()
