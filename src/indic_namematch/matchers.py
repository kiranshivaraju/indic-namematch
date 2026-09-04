"""The matching algorithms.

Every matcher takes two raw name strings and returns a score in ``[0.0, 1.0]``, where 1.0
means "certainly the same person". Two contracts hold for all of them, and the benchmark
suite enforces both:

* **symmetry** -- ``f(a, b) == f(b, a)``. Neither document in a KYC pair is authoritative.
* **bounded** -- the score never leaves ``[0.0, 1.0]``, so thresholds are comparable.

A matcher returns a score, never a decision. Turning a score into approve/review/reject is
:mod:`indic_namematch.bands`, because a threshold is a tuned business parameter.

Seven algorithms across five families, chosen so their failure modes do not overlap:

===================== ==================== ==========================================
matcher               family               what it adds
===================== ==================== ==========================================
``exact``             equality             floor, for reference only
``levenshtein``       character edits      OCR substitutions, dropped letters
``jaro_winkler``      character + prefix   typos, shared prefixes
``token_set``         token algebra        reordering, dropped middle names, initials
``phonetic``          sound                transliteration variants
``hybrid``            composite            best evidence per token
``rarity_weighted``   composite + rarity   the above, weighted by token rarity
===================== ==================== ==========================================
"""

from __future__ import annotations

from typing import Optional, Tuple

from .alignment import Similarity, align, is_initial_of
from .metrics import jaro_winkler as _jw
from .metrics import levenshtein_ratio as _lev_ratio
from .normalize import normalize, tokenize
from .phonetics import same_sound
from .rarity import DEFAULT_RARITY, RarityTable

#: How much each kind of evidence is worth. These are not blended: a token pair is scored by
#: the *strongest* test that fires, and the number says how much identity that kind of
#: evidence actually proves. Two identical tokens prove more than two similar-sounding ones,
#: which prove more than a single matching letter.
IDENTICAL = 1.00
PHONETIC = 0.95
INITIAL = 0.85
CHARACTER = 0.80

#: Jaro-Winkler must clear this before character similarity counts as evidence at all.
CHARACTER_FLOOR = 0.88

#: Whole-string similarity must clear this for the joined-token fallback to apply.
JOINED_FLOOR = 0.92


def _no_match() -> Similarity:
    return 0.0, ""


def _exact_or_initial(x: str, y: str) -> Similarity:
    if x == y:
        return IDENTICAL, "identical"
    if is_initial_of(x, y) or is_initial_of(y, x):
        return INITIAL, "initial"
    return _no_match()


def _with_sound(x: str, y: str) -> Similarity:
    if x == y:
        return IDENTICAL, "identical"
    if is_initial_of(x, y) or is_initial_of(y, x):
        return INITIAL, "initial"
    if same_sound(x, y):
        return PHONETIC, "phonetic"
    return _no_match()


def cascade(x: str, y: str) -> Similarity:
    """Score one token pair by the strongest evidence available for it.

    Read as a priority ladder, not a blend. The first test that fires wins:

    ==========  ====================================  ===========================
    1.00        the same token                        certainty
    0.95        same Soundex and syllable count       transliteration variant
    0.85        one is an initial of the other        one letter, weak on its own
    0.80 x jw   Jaro-Winkler at or above 0.88         OCR damage
    0.00        nothing fired                         no evidence
    ==========  ====================================  ===========================

    Only the character row multiplies, because Jaro-Winkler is the one test returning a
    continuous value rather than yes/no. The 0.80 discounts it as the weakest evidence on
    the ladder.

    >>> cascade("kumar", "kumar")
    (1.0, 'identical')
    >>> cascade("lakshmi", "laxmi")
    (0.95, 'phonetic')
    >>> cascade("s", "suresh")
    (0.85, 'initial')
    >>> round(cascade("rajesh", "ramesh")[0], 3)
    0.729
    """
    if x == y:
        return IDENTICAL, "identical"
    if same_sound(x, y):
        return PHONETIC, "phonetic"
    if is_initial_of(x, y) or is_initial_of(y, x):
        return INITIAL, "initial"
    jw = _jw(x, y)
    if jw >= CHARACTER_FLOOR:
        return CHARACTER * jw, "character"
    return _no_match()


def _normalized_pair(a: str, b: str) -> Optional[Tuple[str, str]]:
    """Normalise both names, returning ``None`` when either carries no name content.

    Extraction can hand you a field holding only an honorific, a relationship marker or
    punctuation, which normalises away to nothing. The character-level metrics treat two
    empty strings as identical and would score that pair 1.0, auto-approving two documents
    that contain no name at all. Every matcher routes through here so that cannot happen.
    """
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return None
    return na, nb


def _joined_ratio(a: str, b: str) -> float:
    """Whole-string similarity with the spaces removed."""
    r = _lev_ratio(normalize(a).replace(" ", ""), normalize(b).replace(" ", ""))
    return r if r >= JOINED_FLOOR else 0.0


# --------------------------------------------------------------------------- matchers

def exact(a: str, b: str) -> float:
    """1.0 only when the two names are identical after normalisation.

    The floor. Present for reference and to prove a harness is wired up; it rejects most
    genuine customers and should not be used on its own.

    >>> exact("PRIYA MENON", "Priya Menon")
    1.0
    >>> exact("Mohammed Irfan", "Mohammad Irfan")
    0.0
    """
    pair = _normalized_pair(a, b)
    return 1.0 if pair and pair[0] == pair[1] else 0.0


def levenshtein(a: str, b: str) -> float:
    """Character edit distance over the whole name.

    Handles OCR damage well and is blind to word order. It also cannot tell a scanner
    misreading one letter from a genuinely different person, which on Indian data means it
    scores siblings higher than real matches.

    >>> round(levenshtein("Rajesh Kumar", "Rajcsh Kumar"), 3)
    0.917
    >>> round(levenshtein("Kumar Suresh", "Suresh Kumar"), 3)
    0.167
    >>> levenshtein("s/o", "s/o")     # no name content on either side
    0.0
    """
    pair = _normalized_pair(a, b)
    return max(0.0, _lev_ratio(*pair)) if pair else 0.0


def jaro_winkler(a: str, b: str) -> float:
    """Prefix-weighted character similarity, the record-linkage default.

    >>> round(jaro_winkler("Lakshmi Narayanan", "Laxmi Narayanan"), 3)
    0.935
    >>> jaro_winkler("Smt.", "Smt.")   # honorific only, no name content
    0.0
    """
    pair = _normalized_pair(a, b)
    return max(0.0, min(1.0, _jw(*pair))) if pair else 0.0


def token_set(a: str, b: str) -> float:
    """Order-independent token matching with initial awareness.

    Reordering and dropped middle names become free. Variation *inside* a token does not:
    ``Mohammed`` and ``Mohammad`` are simply not equal here.

    >>> token_set("Kumar Suresh", "Suresh Kumar")
    1.0
    >>> round(token_set("S. Kumar", "Suresh Kumar"), 3)
    0.925
    >>> token_set("Lakshmi Narayanan", "Laxmi Narayanan")
    0.5
    """
    return align(tokenize(a), tokenize(b), _exact_or_initial).coverage


def phonetic(a: str, b: str) -> float:
    """Token matching on sound rather than spelling.

    >>> round(phonetic("Lakshmi Narayanan", "Laxmi Narayanan"), 3)
    0.975
    >>> phonetic("Sunil Chauhan", "Sunila Chauhan")
    0.5
    """
    return align(tokenize(a), tokenize(b), _with_sound).coverage


def hybrid(a: str, b: str) -> float:
    """Best evidence per token, across every family.

    Also falls back to whole-string similarity when the two names have **different token
    counts**, which is the token-boundary case (``Ram Kumar`` against ``Ramkumar``). The
    token-count guard matters: without it, ``rajeshkumarsharma`` against
    ``rameshkumarsharma`` is one edit in seventeen characters, clears the floor, and
    silently overrides every token-level judgement for siblings.

    >>> hybrid("Ram Kumar", "Ramkumar")
    1.0
    >>> round(hybrid("Rajesh Kumar Sharma", "Ramesh Kumar Sharma"), 3)
    0.91
    """
    ta, tb = tokenize(a), tokenize(b)
    base = align(ta, tb, cascade).coverage
    return max(base, _joined_ratio(a, b)) if len(ta) != len(tb) else base


def rarity_weighted(a: str, b: str, rarity: Optional[RarityTable] = None) -> float:
    """:func:`hybrid`, with each token weighted by how much its agreement proves.

    The recommended matcher. Coverage is measured in evidence mass rather than token count,
    so agreeing on ``Kumar`` barely moves the score while agreeing on a rare given name
    nearly settles it. Pass your own :class:`~indic_namematch.rarity.RarityTable` built from
    real frequencies; the default is a coarse hand-curated tier list.

    >>> round(rarity_weighted("Rajesh Kumar Sharma", "Ramesh Kumar Sharma"), 3)
    0.886
    >>> round(rarity_weighted("S. Kumar", "Suresh Kumar"), 3)
    0.653

    Known limitation: coverage is a ratio, so an exact agreement on a common full name still
    scores 1.0. ``Amit Kumar`` against ``Amit Kumar`` cannot be resolved from the strings at
    all, and separating it needs absolute evidence mass against real frequencies.
    """
    table = rarity if rarity is not None else DEFAULT_RARITY
    ta, tb = tokenize(a), tokenize(b)
    base = align(ta, tb, cascade, table.weight).coverage
    return max(base, _joined_ratio(a, b)) if len(ta) != len(tb) else base


#: Every matcher by name, in increasing order of capability.
REGISTRY = {
    "exact": exact,
    "levenshtein": levenshtein,
    "jaro_winkler": jaro_winkler,
    "token_set": token_set,
    "phonetic": phonetic,
    "hybrid": hybrid,
    "rarity_weighted": rarity_weighted,
}
