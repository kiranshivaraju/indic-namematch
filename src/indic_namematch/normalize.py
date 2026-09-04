"""Turning a raw extracted name string into comparable tokens.

Nothing in this module makes an identity judgement. It removes the parts of a name that
carry no identifying information (case, punctuation, honorifics, relationship markers) so
that the matchers are never given credit for fixing capitalisation.
"""

from __future__ import annotations

import re
import unicodedata
from typing import FrozenSet, List

#: Titles that appear on Indian identity documents and carry no identity weight.
#:
#: ``sri`` is deliberately absent. It is a genuine honorific in South India, but it is also
#: the opening syllable of ordinary given names (Sriram, Srinivas, Sridhar), and stripping
#: it turns "Sri Ram Chandran" into "Ram Chandran", which no longer matches
#: "Sriram Chandran". Disambiguating needs context a string matcher does not have, so the
#: safer default is to keep it and accept the occasional uncorrected honorific.
HONORIFICS: FrozenSet[str] = frozenset({
    "mr", "mrs", "ms", "miss", "smt", "shri", "shrimati", "kumari", "kum",
    "dr", "prof", "late", "md",
})

#: Generational suffixes.
SUFFIXES: FrozenSet[str] = frozenset({"jr", "sr", "ii", "iii"})

#: Relationship markers printed on Indian IDs: son of, daughter of, wife of, care of.
RELATION_MARKERS: FrozenSet[str] = frozenset({
    "s/o", "d/o", "w/o", "c/o", "so", "do", "wo", "co",
})

_PUNCT = re.compile(r"[^\w\s/]", re.UNICODE)
_WS = re.compile(r"\s+")


def normalize_basic(name: str) -> str:
    """Casefold, drop diacritics and punctuation, strip relationship markers.

    >>> normalize_basic("Manjunath S/o Ramaiah")
    'manjunath ramaiah'
    >>> normalize_basic("Maria D'Souza")
    'maria dsouza'
    """
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = name.casefold().replace("'", "").replace("’", "")
    name = _PUNCT.sub(" ", name)
    parts = [
        t for t in _WS.split(name.strip())
        if t and t != "/" and t not in RELATION_MARKERS
    ]
    return " ".join(parts)


def normalize(name: str) -> str:
    """:func:`normalize_basic` plus removal of honorifics and generational suffixes.

    >>> normalize("Smt. Sunita Devi")
    'sunita devi'
    >>> normalize("Ramesh Patel Jr.")
    'ramesh patel'
    """
    parts = [
        t for t in normalize_basic(name).split()
        if t not in HONORIFICS and t not in SUFFIXES
    ]
    return " ".join(parts)


def tokenize(name: str) -> List[str]:
    """Normalise and split into word tokens.

    >>> tokenize("K.Balaji")
    ['k', 'balaji']
    """
    return normalize(name).split()
