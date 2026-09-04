"""Soundex and the syllable guard."""

from __future__ import annotations

import pytest

from indic_namematch.phonetics import phonetic_key, same_sound, soundex, syllable_count


@pytest.mark.parametrize("a,b", [
    ("mohammed", "mohammad"), ("mohammad", "muhammad"),
    ("lakshmi", "laxmi"), ("chowdhury", "choudhury"),
    ("gauri", "gowri"), ("tiwari", "tewari"), ("aashish", "ashish"),
])
def test_transliteration_variants_sound_the_same(a, b):
    assert same_sound(a, b), f"{a} and {b} are the same name spelled two ways"


@pytest.mark.parametrize("a,b", [
    ("sunil", "sunila"), ("nandan", "nandini"), ("ravi", "ravina"),
    ("rajesh", "rajeshwari"), ("sunil", "sushil"), ("rajesh", "ramesh"),
    ("anita", "ankita"), ("farhan", "furqan"),
])
def test_different_people_do_not_sound_the_same(a, b):
    assert not same_sound(a, b), f"{a} and {b} are different people"


def test_the_syllable_guard_is_what_separates_gender_variants():
    """Soundex alone maps sunil and sunila to the same code, merging a man and a woman.

    This is the whole reason same_sound is not just a Soundex comparison.
    """
    assert soundex("sunil") == soundex("sunila")
    assert syllable_count("sunil") != syllable_count("sunila")
    assert not same_sound("sunil", "sunila")


@pytest.mark.parametrize("token,expected", [
    ("lakshmi", "L250"), ("laxmi", "L250"),
    ("rajesh", "R220"), ("ramesh", "R520"),
])
def test_known_soundex_codes(token, expected):
    assert soundex(token) == expected


def test_soundex_is_always_four_characters():
    for t in ["a", "kumar", "padmanabhan", "x", "aeiou"]:
        assert len(soundex(t)) == 4


def test_soundex_of_empty_is_empty():
    assert soundex("") == ""


@pytest.mark.parametrize("token,count", [
    ("sunil", 2), ("sunila", 3), ("mohammed", 3), ("nandini", 3), ("a", 1),
])
def test_syllable_counts(token, count):
    assert syllable_count(token) == count


def test_phonetic_key_combines_both_signals():
    assert phonetic_key("lakshmi") == "L250:2"
    assert phonetic_key("sunil") != phonetic_key("sunila")
