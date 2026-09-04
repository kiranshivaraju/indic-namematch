"""Normalisation: what gets stripped, and what must not be."""

from __future__ import annotations

import pytest

from indic_namematch.normalize import normalize, normalize_basic, tokenize


@pytest.mark.parametrize("raw,expected", [
    ("Smt. Sunita Devi", "sunita devi"),
    ("Shri Rajesh Kumar Sharma", "rajesh kumar sharma"),
    ("Kumari Ananya Iyer", "ananya iyer"),
    ("Dr. Meenakshi Sundaram", "meenakshi sundaram"),
    ("Ramesh Patel Jr.", "ramesh patel"),
])
def test_strips_honorifics_and_suffixes(raw, expected):
    assert normalize(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("Manjunath S/o Ramaiah", "manjunath ramaiah"),
    ("Anjali D/o Rakesh", "anjali rakesh"),
    ("Sunita W/o Rajesh", "sunita rajesh"),
])
def test_strips_relationship_markers(raw, expected):
    assert normalize(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("PRIYA MENON", "priya menon"),
    ("  Amit   Verma  ", "amit verma"),
    ("K.Balaji", "k balaji"),
    ("Maria D'Souza", "maria dsouza"),
    ("José Fernandes", "jose fernandes"),
])
def test_cosmetic_cleanup(raw, expected):
    assert normalize(raw) == expected


def test_sri_is_kept_because_it_is_also_a_name_component():
    """'Sri' is an honorific in South India and the first syllable of Sriram/Srinivas.

    Stripping it turns 'Sri Ram Chandran' into 'Ram Chandran', which then fails to match
    'Sriram Chandran'. Disambiguating needs context a string matcher does not have, so the
    safer default is to keep it.
    """
    assert normalize("Sri Ram Chandran") == "sri ram chandran"
    assert "sri" in tokenize("Srinivas Rao")[0]


def test_apostrophe_is_deleted_not_spaced():
    """D'Souza must become dsouza, not d souza, so it matches the DSouza spelling."""
    assert normalize("Maria D'Souza") == normalize("Maria DSouza")


def test_contentless_input_normalises_to_empty():
    for raw in ["", "   ", ".", "s/o", "Smt.", "Dr. Jr.", "-", "/"]:
        assert normalize(raw) == ""
        assert tokenize(raw) == []


def test_basic_keeps_honorifics():
    """normalize_basic is cleanup only; it makes no identity judgement."""
    assert normalize_basic("Smt. Sunita Devi") == "smt sunita devi"
