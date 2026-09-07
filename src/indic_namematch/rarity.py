"""How much a token agreeing actually proves.

Fellegi & Sunter (1969), the foundation of probabilistic record linkage, and its modern
implementation as term-frequency adjustment in Splink: agreeing on a **rare** value is
strong evidence of a match, while agreeing on a **common** one is nearly none, because
common agreements happen by chance.

Two brothers share "Kumar Sharma" and that tells you almost nothing. Two records sharing
"Padmanabhan" are almost certainly the same person. Counting both at full price is how a
matcher ends up auto-approving siblings.

The default table here is hand-curated from general knowledge of common Indian names. It is
a stand-in, and you should replace it: build a :class:`RarityTable` from token counts over
your own customer base with :meth:`RarityTable.from_counts` and the weights become measured
rather than assumed.
"""

from __future__ import annotations

import csv
import math
from typing import Dict, Mapping, Optional

#: Weight floor and ceiling. Nothing is ever worth zero, and nothing beats a rare token.
MIN_WEIGHT = 0.10
MAX_WEIGHT = 1.00

# Tokens so common in Indian names that agreement is close to no evidence at all.
_NEAR_ZERO = frozenset({
    "kumar", "singh", "devi", "bai", "lal", "das", "ben", "bhai", "kaur",
})

# Frequent surnames, community markers and given names.
_COMMON = frozenset({
    "sharma", "verma", "patel", "reddy", "rao", "naidu", "nair", "menon", "iyer", "pillai",
    "khan", "mohammed", "mohammad", "ali", "sheikh", "ansari", "begum", "syed",
    "shah", "gupta", "jain", "agarwal", "mehta", "joshi", "chauhan", "yadav", "mishra",
    "banerjee", "mukherjee", "chatterjee", "prasad", "chandra", "babu", "raj",
    "amit", "rajesh", "ramesh", "suresh", "anil", "sunil", "vijay", "ajay", "rahul",
    "priya", "pooja", "neha", "anita", "sunita", "ravi", "arun", "sanjay", "deepak",
})

_NEAR_ZERO_WEIGHT = 0.15
_COMMON_WEIGHT = 0.40


class RarityTable:
    """Maps a token to how much evidence its agreement carries, in ``[0.1, 1.0]``.

    The default is a coarse three-tier list:

    >>> t = RarityTable()
    >>> t.weight("kumar"), t.weight("sharma"), t.weight("padmanabhan")
    (0.15, 0.4, 1.0)

    A bare initial is treated as near-zero evidence regardless of the letter, which is what
    keeps ``S Kumar`` / ``Sunita Kumar`` out of the auto-approve band:

    >>> t.weight("s")
    0.15
    """

    __slots__ = ("_default", "_initial_weight", "_weights")

    def __init__(
        self,
        weights: Optional[Mapping[str, float]] = None,
        default: float = MAX_WEIGHT,
        initial_weight: float = _NEAR_ZERO_WEIGHT,
    ) -> None:
        if weights is None:
            weights = dict.fromkeys(_NEAR_ZERO, _NEAR_ZERO_WEIGHT)
            weights.update(dict.fromkeys(_COMMON, _COMMON_WEIGHT))
        self._weights: Dict[str, float] = dict(weights)
        self._default = default
        self._initial_weight = initial_weight

    def weight(self, token: str) -> float:
        """Evidence weight for *token*. Unknown tokens are assumed rare.

        A single-character token is an initial, and one letter agreeing is one letter of
        agreement rather than a name, so it is weighted by *initial_weight* regardless of
        what the table says. Raise that value if you want initials trusted more.
        """
        if len(token) == 1:
            return self._initial_weight
        return self._weights.get(token.lower(), self._default)

    @classmethod
    def from_counts(
        cls,
        counts: Mapping[str, int],
        min_weight: float = MIN_WEIGHT,
    ) -> RarityTable:
        """Build a measured table from token frequencies over your own records.

        Weights are inverse document frequency, rescaled so the rarest observed token sits
        at 1.0 and the commonest at *min_weight*. Tokens absent from *counts* are treated
        as rare, which is the safe default: an unseen token is more likely to be unusual
        than to be a Kumar you forgot.

        >>> t = RarityTable.from_counts({"kumar": 50000, "sharma": 9000, "padmanabhan": 12})
        >>> t.weight("kumar") < t.weight("sharma") < t.weight("padmanabhan")
        True
        """
        if not counts:
            return cls()
        total = sum(counts.values())
        idf = {t: math.log(total / (c + 1)) for t, c in counts.items()}
        lo, hi = min(idf.values()), max(idf.values())
        span = hi - lo
        if span <= 0:
            scaled = dict.fromkeys(idf, MAX_WEIGHT)
        else:
            scaled = {
                t: min_weight + (MAX_WEIGHT - min_weight) * (v - lo) / span
                for t, v in idf.items()
            }
        return cls(scaled, min_weight)

    @classmethod
    def from_csv(cls, path: str, token_field: str = "token",
                 count_field: str = "count") -> RarityTable:
        """Build a table from a two-column CSV of token counts."""
        with open(path, newline="", encoding="utf-8") as fh:
            counts = {
                row[token_field].strip().lower(): int(row[count_field])
                for row in csv.DictReader(fh)
            }
        return cls.from_counts(counts)

    @classmethod
    def uniform(cls) -> RarityTable:
        """Every token weighted equally, initials included: rarity weighting off.

        With this table, :func:`~indic_namematch.matchers.rarity_weighted` reduces exactly to
        :func:`~indic_namematch.matchers.hybrid`, which the test suite asserts.

        >>> t = RarityTable.uniform()
        >>> t.weight("kumar"), t.weight("padmanabhan"), t.weight("s")
        (1.0, 1.0, 1.0)
        """
        return cls({}, default=MAX_WEIGHT, initial_weight=MAX_WEIGHT)

    def __len__(self) -> int:
        return len(self._weights)

    def __repr__(self) -> str:
        return (f"RarityTable({len(self._weights)} tokens, default={self._default}, "
                f"initial_weight={self._initial_weight})")


#: Shared default instance, used when no table is supplied.
DEFAULT_RARITY = RarityTable()
