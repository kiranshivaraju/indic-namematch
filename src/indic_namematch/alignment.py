"""Pairing the words of one name against the words of another.

A name is treated as an unordered bag of tokens, which is what makes surname-first ordering
and dropped middle names cost nothing. Two tokens are paired at most once, best evidence
first, and the result is scored by how much of each name got covered.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

#: A token comparison returns how similar the tokens are and *why*, so that a score can be
#: explained after the fact. ``kind`` is one of "identical", "phonetic", "initial",
#: "character", or "" when nothing fired.
Similarity = Tuple[float, str]

#: Compares two tokens.
SimilarityFn = Callable[[str, str], Similarity]

#: Returns how much evidence a token's agreement carries.
WeightFn = Callable[[str], float]


@dataclass(frozen=True)
class TokenMatch:
    """One aligned pair of tokens and what it contributed to the score."""

    token_a: str
    token_b: str
    similarity: float
    kind: str
    weight: float

    @property
    def contribution(self) -> float:
        """Evidence this pair added: how alike, times how much it matters."""
        return self.similarity * self.weight


@dataclass(frozen=True)
class Alignment:
    """The result of pairing two token lists."""

    matches: List[TokenMatch] = field(default_factory=list)
    unmatched_a: List[str] = field(default_factory=list)
    unmatched_b: List[str] = field(default_factory=list)
    evidence: float = 0.0
    available_a: float = 0.0
    available_b: float = 0.0

    @property
    def coverage(self) -> float:
        """How much of each name was matched, combined as an F1 of the two coverages.

        F1 rather than ``evidence / max(available)`` on purpose: a dropped middle name
        should not be punished as hard as one name being a bare fragment of the other.
        """
        if not self.available_a or not self.available_b:
            return 0.0
        ca = self.evidence / self.available_a
        cb = self.evidence / self.available_b
        return 0.0 if ca + cb == 0 else 2 * ca * cb / (ca + cb)


def is_initial_of(short: str, long: str) -> bool:
    """True when *short* is a single letter that *long* starts with.

    >>> is_initial_of("s", "suresh")
    True
    >>> is_initial_of("su", "suresh")
    False
    """
    return len(short) == 1 and len(long) > 1 and long.startswith(short)


def _unit_weight(_token: str) -> float:
    return 1.0


def align(
    tokens_a: List[str],
    tokens_b: List[str],
    similarity: SimilarityFn,
    weight: Optional[WeightFn] = None,
) -> Alignment:
    """Greedily pair tokens one-to-one, strongest evidence first.

    Candidates are sorted by score with an order-independent tie-break, so the alignment is
    identical whichever name is passed first. That matters: neither document in a KYC pair
    is authoritative and you do not control which one arrives first.

    Names have single-digit token counts, so greedy is indistinguishable from an optimal
    assignment in practice and far easier to read than Hungarian.

    When *weight* is given, each pair contributes its similarity times the weight of the
    **rarer** side, so matching a rare token against a common one is not credited as rare
    evidence.
    """
    wfn = weight or _unit_weight

    candidates = []
    for i, x in enumerate(tokens_a):
        for j, y in enumerate(tokens_b):
            score, kind = similarity(x, y)
            if score > 0:
                # min/max on the tokens keeps the tie-break symmetric.
                candidates.append((-score, min(x, y), max(x, y), i, j, kind))
    candidates.sort()

    used_a, used_b = set(), set()
    matches: List[TokenMatch] = []
    evidence = 0.0
    for neg_score, _, _, i, j, kind in candidates:
        if i in used_a or j in used_b:
            continue
        used_a.add(i)
        used_b.add(j)
        pair_weight = min(wfn(tokens_a[i]), wfn(tokens_b[j]))
        match = TokenMatch(tokens_a[i], tokens_b[j], -neg_score, kind, pair_weight)
        matches.append(match)
        evidence += match.contribution

    return Alignment(
        matches=matches,
        unmatched_a=[t for i, t in enumerate(tokens_a) if i not in used_a],
        unmatched_b=[t for j, t in enumerate(tokens_b) if j not in used_b],
        evidence=evidence,
        available_a=sum(wfn(t) for t in tokens_a),
        available_b=sum(wfn(t) for t in tokens_b),
    )
