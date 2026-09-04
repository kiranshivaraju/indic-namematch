"""The contracts every matcher must satisfy.

These are the tests that matter most. A matcher that violates any of them is unsafe to put
in a KYC pipeline regardless of how well it scores on the benchmark.
"""

from __future__ import annotations

import pytest

from indic_namematch import NameMatcher, RarityTable
from indic_namematch.matchers import REGISTRY
from indic_namematch.normalize import tokenize

MATCHERS = sorted(REGISTRY.items())


@pytest.mark.parametrize("name,fn", MATCHERS, ids=[n for n, _ in MATCHERS])
def test_symmetric_on_benchmark(name, fn, pairs):
    """score(a, b) == score(b, a) for every benchmark pair.

    Neither document in a KYC pair is authoritative and you do not control which one arrives
    first, so an order-dependent matcher will silently give two different answers to the
    same question.
    """
    for p in pairs:
        ab, ba = fn(p["name_a"], p["name_b"]), fn(p["name_b"], p["name_a"])
        assert ab == pytest.approx(ba, abs=1e-12), (
            f"{name} is asymmetric on row {p['id']}: "
            f"{p['name_a']!r}/{p['name_b']!r} -> {ab} but reversed -> {ba}"
        )


@pytest.mark.parametrize("name,fn", MATCHERS, ids=[n for n, _ in MATCHERS])
def test_symmetric_on_adversarial_input(name, fn, names):
    """Symmetry must survive empty strings, punctuation and unicode, not just clean data."""
    for a in names[:40]:
        for b in names[:40]:
            assert fn(a, b) == pytest.approx(fn(b, a), abs=1e-12), \
                f"{name} is asymmetric on {a!r} vs {b!r}"


@pytest.mark.parametrize("name,fn", MATCHERS, ids=[n for n, _ in MATCHERS])
def test_bounded(name, fn, names):
    """Scores stay inside [0, 1] so that thresholds are comparable across matchers."""
    for a in names:
        for b in names[:30]:
            s = fn(a, b)
            assert 0.0 <= s <= 1.0, f"{name}({a!r}, {b!r}) = {s} is out of range"


@pytest.mark.parametrize("name,fn", MATCHERS, ids=[n for n, _ in MATCHERS])
def test_reflexive(name, fn, names):
    """A name with actual content scores 1.0 against itself."""
    for a in names:
        if tokenize(a):
            assert fn(a, a) == pytest.approx(1.0), f"{name}({a!r}, {a!r}) != 1.0"


@pytest.mark.parametrize("name,fn", MATCHERS, ids=[n for n, _ in MATCHERS])
def test_contentless_names_never_match(name, fn):
    """A string that normalises to nothing must not match anything, including itself.

    Extraction can hand you a field holding only an honorific, a relationship marker or
    punctuation. Scoring those 1.0 against each other would auto-approve two documents that
    carry no name at all, which is the worst possible failure in this system.
    """
    contentless = ["", "  ", ".", "s/o", "S/O", "w/o", "Smt.", "Dr.", "Jr.", "-", "/"]
    for a in contentless:
        assert tokenize(a) == [], f"test assumption broken: {a!r} still has tokens"
        assert fn(a, a) == 0.0, f"{name} scored contentless {a!r} against itself as a match"
        for b in contentless + ["Suresh Kumar"]:
            assert fn(a, b) == 0.0, f"{name} matched contentless {a!r} against {b!r}"


@pytest.mark.parametrize("name,fn", MATCHERS, ids=[n for n, _ in MATCHERS])
def test_never_raises(name, fn, names):
    """No input in the adversarial set may raise."""
    for a in names:
        for b in names[:20]:
            fn(a, b)


@pytest.mark.parametrize("name,fn", MATCHERS, ids=[n for n, _ in MATCHERS])
def test_case_and_whitespace_invariant(name, fn):
    """Cosmetic differences must never change a score."""
    a, b = "Rajesh Kumar Sharma", "Ramesh Kumar Sharma"
    baseline = fn(a, b)
    for va, vb in [(a.upper(), b), (a.lower(), b), (f"  {a}  ", b), (a.replace(" ", "  "), b)]:
        assert fn(va, vb) == pytest.approx(baseline), \
            f"{name} changed score for a cosmetic variation of {a!r}"


def test_rarity_weighting_is_the_only_difference_between_hybrid_and_weighted():
    """With a uniform rarity table, rarity_weighted must reduce exactly to hybrid."""
    from indic_namematch.matchers import hybrid, rarity_weighted

    uniform = RarityTable.uniform()
    for a, b in [("Rajesh Kumar Sharma", "Ramesh Kumar Sharma"),
                 ("S. Kumar", "Suresh Kumar"),
                 ("Lakshmi Narayanan", "Laxmi Narayanan"),
                 ("Ram Kumar", "Ramkumar"),
                 ("Priya Lakshmi Menon", "Priya Menon")]:
        assert rarity_weighted(a, b, uniform) == pytest.approx(hybrid(a, b)), \
            f"uniform-weighted score diverged from hybrid on {a!r}/{b!r}"


def test_matcher_respects_injected_rarity():
    """Marking a token common must lower the score of a pair that agrees on it."""
    a, b = "Rajesh Kumar Sharma", "Ramesh Kumar Sharma"
    common = RarityTable.from_counts({"kumar": 100_000, "sharma": 90_000, "rajesh": 100,
                                      "ramesh": 100})
    assert NameMatcher(rarity=common).score(a, b) < NameMatcher(rarity=RarityTable.uniform()).score(a, b)
