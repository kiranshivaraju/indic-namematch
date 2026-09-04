"""The rarity table and its effect on scoring."""

from __future__ import annotations

import csv

from indic_namematch.rarity import MAX_WEIGHT, MIN_WEIGHT, RarityTable


def test_default_tiers():
    t = RarityTable()
    assert t.weight("kumar") < t.weight("sharma") < t.weight("padmanabhan")
    assert t.weight("padmanabhan") == MAX_WEIGHT


def test_unknown_tokens_are_assumed_rare():
    """A token you have never seen is more likely unusual than a Kumar you forgot."""
    assert RarityTable().weight("qwertyuiop") == MAX_WEIGHT


def test_initials_are_near_zero_regardless_of_letter():
    t = RarityTable()
    assert {t.weight(c) for c in "abcdefghijklmnopqrstuvwxyz"} == {t.weight("s")}
    assert t.weight("s") < t.weight("suresh")


def test_uniform_is_actually_uniform_including_initials():
    """Regression: the single-character rule used to bypass the table entirely."""
    t = RarityTable.uniform()
    assert t.weight("kumar") == t.weight("padmanabhan") == t.weight("s") == MAX_WEIGHT


def test_from_counts_orders_by_rarity():
    t = RarityTable.from_counts({"kumar": 50_000, "sharma": 9_000, "iyer": 3_000,
                                 "padmanabhan": 12})
    assert t.weight("kumar") < t.weight("sharma") < t.weight("iyer") < t.weight("padmanabhan")


def test_from_counts_stays_in_range():
    t = RarityTable.from_counts({"a": 1, "b": 10, "c": 100, "d": 100_000})
    for token in "abcd":
        assert MIN_WEIGHT <= t.weight(token) <= MAX_WEIGHT


def test_from_counts_handles_a_single_token():
    t = RarityTable.from_counts({"kumar": 5})
    assert MIN_WEIGHT <= t.weight("kumar") <= MAX_WEIGHT


def test_from_counts_empty_falls_back_to_defaults():
    assert RarityTable.from_counts({}).weight("kumar") == RarityTable().weight("kumar")


def test_from_csv(tmp_path):
    path = tmp_path / "counts.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["token", "count"])
        w.writerows([["kumar", 50_000], ["padmanabhan", 12]])
    t = RarityTable.from_csv(str(path))
    assert t.weight("kumar") < t.weight("padmanabhan")


def test_lookup_is_case_insensitive():
    t = RarityTable()
    assert t.weight("KUMAR") == t.weight("kumar")
