"""Sound-based comparison, for transliteration variance.

Indian names are written natively in Devanagari, Tamil, Bengali and other scripts. When one
is printed on a PAN card in Latin letters somebody chose a spelling, and there is no
official rule for how. मोहम्मद is correctly written Mohammed, Mohammad or Muhammad; लक्ष्मी
is correctly Lakshmi or Laxmi. The spelling varies, the pronunciation does not, so
comparing sound rather than letters removes the variance.

Soundex alone is not enough, hence :func:`same_sound`. See its docstring.
"""

from __future__ import annotations

from typing import FrozenSet, Tuple

# Vowel digraph folds, used only for the syllable count.
#
# An earlier version of this library shipped a hand-written Indic consonant folding table
# as well (ksh -> ks, aspirate collapse, w -> v). Benchmarked against plain Soundex on the
# same tokens it was no better, so it was deleted. The syllable guard below, not the
# bespoke folding, was doing the work.
_VOWEL_FOLDS: Tuple[Tuple[str, str], ...] = (
    ("ow", "o"), ("ou", "o"), ("au", "o"), ("aw", "o"), ("ee", "i"), ("oo", "u"),
    ("ai", "e"), ("ay", "e"), ("ei", "e"), ("ia", "a"), ("aa", "a"), ("ii", "i"),
    ("uu", "u"),
)
_VOWELS: FrozenSet[str] = frozenset("aeiou")

# Soundex consonant classes: letters that make a similar sound share a digit.
#   1  b f p v          made with the lips
#   2  c g j k q s x z  hissing / back of the mouth
#   3  d t              tongue on the teeth
#   4  l                the L sound
#   5  m n              through the nose
#   6  r                the R sound
# Vowels plus h, w and y are dropped: they are what varies most between spellings.
_SOUNDEX_CLASS = {
    **{c: "1" for c in "bfpv"},
    **{c: "2" for c in "cgjkqsxz"},
    **{c: "3" for c in "dt"},
    "l": "4",
    **{c: "5" for c in "mn"},
    "r": "6",
}


def _fold_vowels(token: str) -> str:
    s = token.lower()
    for src, dst in _VOWEL_FOLDS:
        s = s.replace(src, dst)
    return s


def syllable_count(token: str) -> int:
    """Vowels left after digraph folding: a cheap proxy for beats of pronunciation.

    >>> syllable_count("sunil"), syllable_count("sunila")
    (2, 3)
    >>> syllable_count("mohammed"), syllable_count("mohammad")
    (3, 3)
    """
    return sum(1 for c in _fold_vowels(token) if c in _VOWELS)


def soundex(token: str) -> str:
    """Classic Soundex (Russell & Odell, 1918): first letter plus three consonant codes.

    >>> soundex("lakshmi"), soundex("laxmi")
    ('L250', 'L250')
    >>> soundex("rajesh"), soundex("ramesh")
    ('R220', 'R520')
    """
    w = token.lower()
    if not w:
        return ""
    out, prev = w[0].upper(), _SOUNDEX_CLASS.get(w[0], "")
    for ch in w[1:]:
        code = _SOUNDEX_CLASS.get(ch, "")
        if code and code != prev:
            out += code
        if ch not in "hw":
            prev = code
    return (out + "000")[:4]


def same_sound(x: str, y: str) -> bool:
    """Same Soundex code **and** the same syllable count.

    The second condition is not decoration. Soundex drops vowels, which makes ``sunil`` and
    ``sunila`` identical (both ``S540``), so masculine and feminine forms of one root
    collide with genuine transliteration variants. In a KYC setting that produces false
    positives, the expensive kind of error. Requiring the syllable counts to agree
    separates them without costing anything on real variants:

    >>> same_sound("sunil", "sunila")      # a man and a woman
    False
    >>> same_sound("nandan", "nandini")
    False
    >>> same_sound("mohammed", "mohammad")  # one person, two spellings
    True
    >>> same_sound("lakshmi", "laxmi")
    True
    """
    return soundex(x) == soundex(y) and syllable_count(x) == syllable_count(y)


def phonetic_key(token: str) -> str:
    """The full sound key used for comparison: Soundex code plus syllable count.

    Useful as a blocking key when comparing one name against many.

    >>> phonetic_key("lakshmi")
    'L250:2'
    """
    return f"{soundex(token)}:{syllable_count(token)}"
