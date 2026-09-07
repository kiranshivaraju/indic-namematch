"""Matching person names across Indian identity documents.

The same person's name is written differently on a PAN card, an Aadhaar, a passport and a
utility bill. It gets abbreviated to initials, reordered surname-first, transliterated with
a different spelling, stripped of a middle name, prefixed with an honorific, or mangled by
OCR. Deciding whether two extracted strings refer to one human is the core of KYC name
matching, and general-purpose fuzzy matching handles it badly.

Quick start::

    from indic_namematch import NameMatcher

    m = NameMatcher()
    m.score("S. Kumar", "Suresh Kumar")     # 0.653
    m.decide("S. Kumar", "Suresh Kumar")    # Decision.REVIEW

Bring your own token frequencies, which is what turns the weakest part of the default
configuration into a measured one::

    from indic_namematch import NameMatcher, RarityTable

    table = RarityTable.from_counts({"kumar": 50_000, "padmanabhan": 12, ...})
    m = NameMatcher(rarity=table)

And when you need to know *why* a pair scored what it did::

    for e in m.explain("Rajesh Kumar Sharma", "Ramesh Kumar Sharma").matches:
        print(e.token_a, e.token_b, e.kind, e.contribution)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .alignment import Alignment, TokenMatch, align, is_initial_of
from .bands import Bands, Decision, derive
from .matchers import REGISTRY, cascade, rarity_weighted
from .normalize import normalize, tokenize
from .phonetics import phonetic_key, same_sound, soundex, syllable_count
from .rarity import RarityTable

__version__ = "0.1.0"

__all__ = [
    "REGISTRY",
    "Alignment",
    "Bands",
    "Decision",
    "Explanation",
    "NameMatcher",
    "RarityTable",
    "TokenMatch",
    "__version__",
    "align",
    "derive",
    "is_initial_of",
    "normalize",
    "phonetic_key",
    "same_sound",
    "soundex",
    "syllable_count",
    "tokenize",
]


@dataclass(frozen=True)
class Explanation:
    """Why a pair scored what it did.

    Every scoring decision is reconstructible from this: which tokens paired with which,
    what kind of evidence justified each pairing, how much each was worth, and which tokens
    found no partner at all.
    """

    name_a: str
    name_b: str
    normalized_a: str
    normalized_b: str
    tokens_a: List[str]
    tokens_b: List[str]
    matches: List[TokenMatch]
    unmatched_a: List[str]
    unmatched_b: List[str]
    score: float
    decision: Decision

    def __str__(self) -> str:
        lines = [
            f"{self.name_a!r} vs {self.name_b!r}",
            f"  normalised : {self.normalized_a!r} | {self.normalized_b!r}",
        ]
        for m in self.matches:
            lines.append(
                f"  {m.token_a} ~ {m.token_b}: {m.similarity:.2f} ({m.kind})"
                f" x weight {m.weight:.2f} = {m.contribution:.3f}"
            )
        for t in self.unmatched_a:
            lines.append(f"  {t} ~ (nothing)")
        for t in self.unmatched_b:
            lines.append(f"  (nothing) ~ {t}")
        lines.append(f"  score {self.score:.3f} -> {self.decision.value.upper()}")
        return "\n".join(lines)


class NameMatcher:
    """Scores and decides on pairs of Indian names.

    :param rarity: how much each token's agreement is worth. Defaults to a hand-curated
        tier list; replace it with :meth:`RarityTable.from_counts` over your own records.
        Pass :meth:`RarityTable.uniform` to disable rarity weighting.
    :param bands: the auto-approve and auto-reject thresholds. The defaults come from the
        bundled benchmark and are a starting point, not a universal constant.

    >>> m = NameMatcher()
    >>> round(m.score("Kumar Suresh", "Suresh Kumar"), 3)
    1.0
    >>> m.decide("Rajesh Kumar Sharma", "Ramesh Kumar Sharma")
    <Decision.REVIEW: 'review'>
    """

    def __init__(
        self,
        rarity: Optional[RarityTable] = None,
        bands: Optional[Bands] = None,
    ) -> None:
        self.rarity = rarity if rarity is not None else RarityTable()
        self.bands = bands if bands is not None else Bands()

    def score(self, a: str, b: str) -> float:
        """Similarity in ``[0.0, 1.0]``. Symmetric: ``score(a, b) == score(b, a)``."""
        return rarity_weighted(a, b, self.rarity)

    def decide(self, a: str, b: str) -> Decision:
        """Score the pair and place it in a band."""
        return self.bands.decide(self.score(a, b))

    def explain(self, a: str, b: str) -> Explanation:
        """Score the pair and return the full evidence breakdown."""
        ta, tb = tokenize(a), tokenize(b)
        alignment = align(ta, tb, cascade, self.rarity.weight)
        score = self.score(a, b)
        return Explanation(
            name_a=a,
            name_b=b,
            normalized_a=normalize(a),
            normalized_b=normalize(b),
            tokens_a=ta,
            tokens_b=tb,
            matches=alignment.matches,
            unmatched_a=alignment.unmatched_a,
            unmatched_b=alignment.unmatched_b,
            score=score,
            decision=self.bands.decide(score),
        )

    def __repr__(self) -> str:
        return f"NameMatcher(rarity={self.rarity!r}, bands={self.bands!r})"
