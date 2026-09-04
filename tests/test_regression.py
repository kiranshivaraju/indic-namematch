"""Pins the benchmark results.

A refactor that changes any published number will fail here. If a change is intentional,
regenerate ``tests/expected_benchmark.json`` in the same commit so the diff shows exactly
which numbers moved and by how much.
"""

from __future__ import annotations

import json
import os

import pytest

from indic_namematch.bands import derive
from indic_namematch.matchers import REGISTRY

EXPECTED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "expected_benchmark.json")

with open(EXPECTED, encoding="utf-8") as _fh:
    PINNED = json.load(_fh)


def _evaluate(name, pairs):
    fn = REGISTRY[name]
    scores = [fn(p["name_a"], p["name_b"]) for p in pairs]
    bands = derive([(s, p["is_match"]) for s, p in zip(scores, pairs)],
                   [p["decidable"] for p in pairs])
    approve = [i for i, s in enumerate(scores) if s >= bands.approve_at]
    reject = [i for i, s in enumerate(scores) if s < bands.reject_below]
    review = [i for i in range(len(scores)) if i not in set(approve) | set(reject)]
    n_pos = sum(p["is_match"] for p in pairs)
    return {
        "bands": bands,
        "approve_rate": sum(1 for i in approve if pairs[i]["is_match"]) / n_pos,
        "review_rate": len(review) / len(pairs),
        "unavoidable_fp_ids": sorted(pairs[i]["id"] for i in approve
                                     if not pairs[i]["is_match"] and not pairs[i]["decidable"]),
        "unavoidable_fn_ids": sorted(pairs[i]["id"] for i in reject
                                     if pairs[i]["is_match"] and not pairs[i]["decidable"]),
    }


@pytest.mark.parametrize("name", sorted(PINNED))
def test_thresholds_unchanged(name, pairs):
    got = _evaluate(name, pairs)
    assert got["bands"].approve_at == pytest.approx(PINNED[name]["approve_at"], abs=1e-9)
    assert got["bands"].reject_below == pytest.approx(PINNED[name]["reject_below"], abs=1e-9)


@pytest.mark.parametrize("name", sorted(PINNED))
def test_band_rates_unchanged(name, pairs):
    got = _evaluate(name, pairs)
    assert got["approve_rate"] == pytest.approx(PINNED[name]["approve_rate"], abs=1e-9)
    assert got["review_rate"] == pytest.approx(PINNED[name]["review_rate"], abs=1e-9)


@pytest.mark.parametrize("name", sorted(PINNED))
def test_the_same_pairs_remain_unavoidable(name, pairs):
    """Which rows no algorithm can get right is the most important claim in the project."""
    got = _evaluate(name, pairs)
    assert got["unavoidable_fp_ids"] == PINNED[name]["unavoidable_fp_ids"]
    assert got["unavoidable_fn_ids"] == PINNED[name]["unavoidable_fn_ids"]


def test_rarity_weighted_is_still_the_best_choice(pairs):
    """The recommendation itself, as a test.

    It ships because it makes the fewest automatic errors, not because it approves the most.
    If another matcher ever beats it on that count, the README needs updating.
    """
    errors = {
        name: len(_evaluate(name, pairs)["unavoidable_fp_ids"])
              + len(_evaluate(name, pairs)["unavoidable_fn_ids"])
        for name in REGISTRY
    }
    composites = {n: e for n, e in errors.items() if n in ("hybrid", "rarity_weighted",
                                                          "token_set", "phonetic")}
    assert min(composites, key=composites.get) == "rarity_weighted"
    assert errors["rarity_weighted"] == 4


# --------------------------------------------------------------------------------------
# Score-level pin.
#
# The aggregate pins above are too coarse on their own: nudging an evidence weight moves
# every score slightly without necessarily moving a derived threshold or an error count, so
# a real behaviour change can slip through. This pins all 120 x 7 individual scores, which
# is the only version of this test that catches every change.
# --------------------------------------------------------------------------------------

SCORES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "expected_scores.json")

with open(SCORES_FILE, encoding="utf-8") as _fh:
    PINNED_SCORES = json.load(_fh)


@pytest.mark.parametrize("name", sorted(PINNED_SCORES))
def test_every_score_unchanged(name, pairs):
    """Any change to what a matcher outputs, on any pair, fails here.

    To accept an intentional change, regenerate ``tests/expected_scores.json`` in the same
    commit. The diff then shows precisely which pairs moved and by how much, which is the
    review you want before publishing a new set of numbers.
    """
    fn = REGISTRY[name]
    expected = PINNED_SCORES[name]
    drifted = []
    for p in pairs:
        got = fn(p["name_a"], p["name_b"])
        want = expected[str(p["id"])]
        if abs(got - want) > 1e-9:
            drifted.append(f"  id={p['id']:>3} {p['name_a']!r} vs {p['name_b']!r}: "
                           f"{want:.6f} -> {got:.6f}")
    assert not drifted, (
        f"{name} changed on {len(drifted)} of {len(pairs)} pairs:\n" + "\n".join(drifted[:15])
    )
