"""Shared fixtures."""

from __future__ import annotations

import csv
import os
from typing import Dict, List

import pytest

BENCHMARK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "benchmark", "name_pairs.csv")

#: Strings chosen to break careless implementations rather than to be realistic.
ADVERSARIAL: List[str] = [
    "", " ", "  ", "\t", ".", "...", "'", "-", "/", "s/o", "S/O",
    "a", "A.", "x y", "Smt.", "Dr. Jr.",
    "Ramesh", "RAMESH", "ramesh", "  Ramesh  ",
    "Ram-esh", "Ram'esh", "Ram.esh", "Ram/esh",
    "Ramesh Kumar Sharma Verma Gupta Iyer Menon",
    "Zoë Kapoor", "José Fernandes", "Ramesh​Kumar",
    "A B C D E", "kumar", "kumar kumar", "राम",
]


@pytest.fixture(scope="session")
def pairs() -> List[Dict]:
    """The 120 labelled benchmark pairs."""
    with open(BENCHMARK, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["id"] = int(r["id"])
        r["is_match"] = r["label"] == "match"
        r["decidable"] = r["resolvable"] == "yes"
    return rows


@pytest.fixture(scope="session")
def names(pairs) -> List[str]:
    """Every distinct name string in the benchmark, plus adversarial input."""
    seen = {p["name_a"] for p in pairs} | {p["name_b"] for p in pairs}
    return sorted(seen) + ADVERSARIAL
