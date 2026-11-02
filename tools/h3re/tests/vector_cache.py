"""Per-process memoised vector generation shared by the test_vectors* modules.

Generation is a pure function of the code, so each vector set is computed once per
test process. fresh_all() is the single independent second generation that the
determinism checks compare against; it is computed at most once.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from h3re import vectors as V  # noqa: E402

_FRESH = []


def module_doc(mod):
    """Memoised generate() of a vectors_* module (returns {file name: doc})."""
    return V.module_outputs(mod.__name__.rsplit(".", 1)[1])


def fresh_all():
    """One independent full regeneration ({file name: bytes}), computed once per process."""
    if not _FRESH:
        _FRESH.append(V.generate_fresh())
    return _FRESH[0]


def assert_module_deterministic(test, mod):
    """Cached module output must serialise to the same bytes as the independent regeneration."""
    fresh = fresh_all()
    docs = module_doc(mod)
    test.assertTrue(docs)
    for name, doc in docs.items():
        test.assertEqual(V._dump(doc), fresh[name], name)
