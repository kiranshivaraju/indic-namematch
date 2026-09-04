"""Character-level string similarity, implemented from scratch.

Kept dependency-free on purpose: the library installs with no build step and the logic is
readable rather than hidden behind a C extension. If you need these at high throughput,
``rapidfuzz`` is faster and returns compatible values.
"""

from __future__ import annotations


def levenshtein(a: str, b: str) -> int:
    """Edit distance: insertions, deletions and substitutions to turn *a* into *b*.

    Iterative two-row dynamic programming, O(len(a) * len(b)) time, O(len(b)) space.

    >>> levenshtein("rajesh", "rajcsh")
    1
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def levenshtein_ratio(a: str, b: str) -> float:
    """Edit distance rescaled to ``[0.0, 1.0]`` against the longer string.

    >>> round(levenshtein_ratio("rajesh kumar", "rajcsh kumar"), 3)
    0.917
    """
    if not a and not b:
        return 1.0
    return 1.0 - levenshtein(a, b) / max(len(a), len(b))


def jaro(a: str, b: str) -> float:
    """Jaro similarity: matching characters within a sliding window, minus transpositions."""
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    window = max(max(len(a), len(b)) // 2 - 1, 0)
    a_hit = [False] * len(a)
    b_hit = [False] * len(b)
    matches = 0
    for i, ca in enumerate(a):
        for j in range(max(0, i - window), min(len(b), i + window + 1)):
            if not b_hit[j] and b[j] == ca:
                a_hit[i] = b_hit[j] = True
                matches += 1
                break
    if not matches:
        return 0.0
    k = transpositions = 0
    for i, ca in enumerate(a):
        if a_hit[i]:
            while not b_hit[k]:
                k += 1
            if ca != b[k]:
                transpositions += 1
            k += 1
    t = transpositions / 2
    return (matches / len(a) + matches / len(b) + (matches - t) / matches) / 3


def jaro_winkler(a: str, b: str, p: float = 0.1, max_prefix: int = 4) -> float:
    """Jaro with a bonus for a shared prefix.

    The record-linkage default since the US Census Bureau, on the observation that
    corruption clusters toward the end of a name, so agreement at the front is worth more.

    Be aware this cuts against you on Indian data: siblings share a surname and frequently
    the same opening letters, so the prefix bonus rewards exactly the pairs you most need
    to keep apart.

    >>> round(jaro_winkler("lakshmi", "laxmi"), 3)
    0.832
    """
    j = jaro(a, b)
    if j < 0.7:
        return j
    prefix = 0
    for ca, cb in zip(a[:max_prefix], b[:max_prefix]):
        if ca != cb:
            break
        prefix += 1
    return j + prefix * p * (1 - j)
