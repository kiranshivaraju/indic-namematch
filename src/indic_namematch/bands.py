"""Turning a score into an action.

A production KYC pipeline does not answer match/no-match. It answers auto-approve, send to
a human, or auto-reject. Forcing a binary is what makes "zero false positives" sound
achievable when it is arithmetically not: if any pair in your data is undecidable from the
strings alone, and some always are, then demanding no false positives is the same as
auto-approving nobody.

So there are two thresholds, and the band between them is where the matcher declines to
answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence, Tuple

#: Smallest gap used when placing a threshold just above an observed score.
EPSILON = 1e-9


class Decision(str, Enum):
    """What to do with a scored pair."""

    APPROVE = "approve"
    """Auto-approve. Above this the matcher has not been wrong on decidable data."""

    REVIEW = "review"
    """Send to a human. The matcher declines to answer."""

    REJECT = "reject"
    """Auto-reject. Below this no genuine match has been seen on decidable data."""


@dataclass(frozen=True)
class Bands:
    """The two thresholds that split scores into three actions.

    The defaults were derived from the bundled benchmark for the
    :func:`~indic_namematch.matchers.rarity_weighted` matcher. They are a starting point,
    not a universal constant: derive your own with :func:`derive` once you have labelled
    pairs from your own traffic.
    """

    approve_at: float = 0.8858479542163742
    reject_below: float = 0.36363636363636365

    def __post_init__(self) -> None:
        if not 0.0 <= self.reject_below <= self.approve_at <= 1.0 + EPSILON:
            raise ValueError(
                f"need 0 <= reject_below <= approve_at <= 1, "
                f"got reject_below={self.reject_below}, approve_at={self.approve_at}"
            )

    def decide(self, score: float) -> Decision:
        """Place a score into one of the three bands.

        >>> b = Bands(approve_at=0.886, reject_below=0.364)
        >>> b.decide(0.95), b.decide(0.65), b.decide(0.20)
        (<Decision.APPROVE: 'approve'>, <Decision.REVIEW: 'review'>, <Decision.REJECT: 'reject'>)
        """
        if score >= self.approve_at:
            return Decision.APPROVE
        if score < self.reject_below:
            return Decision.REJECT
        return Decision.REVIEW


def derive(
    scored: Sequence[Tuple[float, bool]],
    decidable: Optional[Sequence[bool]] = None,
) -> Bands:
    """Derive thresholds that make zero avoidable errors on labelled data.

    *scored* is a sequence of ``(score, is_match)``. *decidable* marks which pairs could in
    principle be resolved from the two strings; pairs where they could not are excluded from
    the constraints, because no threshold can satisfy them and including them collapses the
    approve band to nothing.

    ``approve_at`` lands just above the highest-scoring decidable non-match, so nothing
    decidably wrong is auto-approved. ``reject_below`` lands at the lowest-scoring decidable
    match, so nothing decidably right is auto-rejected. Everything between goes to a human.

    When the two classes separate cleanly, the lowest match outscores the highest non-match
    and the review band collapses to nothing. That is the correct outcome, not a bug: there
    is no uncertainty left to route to a person. ``reject_below`` is clamped to
    ``approve_at`` in that case so the bands stay well-ordered.

    >>> pairs = [(0.95, True), (0.90, True), (0.70, False), (0.20, False)]
    >>> b = derive(pairs)
    >>> round(b.approve_at, 3), round(b.reject_below, 3)
    (0.7, 0.7)

    An undecidable pair is excluded from the constraints, so it cannot drag the approve
    threshold above every real match:

    >>> pairs = [(1.00, True), (1.00, False), (0.90, True), (0.20, False)]
    >>> b = derive(pairs, decidable=[True, False, True, True])
    >>> round(b.approve_at, 3), round(b.reject_below, 3)
    (0.2, 0.2)
    """
    if decidable is None:
        decidable = [True] * len(scored)
    if len(decidable) != len(scored):
        raise ValueError("decidable must be the same length as scored")

    negatives = [s for (s, m), d in zip(scored, decidable) if d and not m]
    positives = [s for (s, m), d in zip(scored, decidable) if d and m]
    if not scored:
        raise ValueError("need at least one scored pair")

    approve_at = max(negatives) + EPSILON if negatives else min(s for s, _ in scored)
    reject_below = min(positives) if positives else max(s for s, _ in scored) + EPSILON
    return Bands(approve_at=approve_at, reject_below=min(reject_below, approve_at))
