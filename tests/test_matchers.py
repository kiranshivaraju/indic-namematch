"""What each matcher is supposed to catch, and where each one is known to fail.

The failure tests are as important as the success ones. They are the evidence for why the
composite matchers exist rather than any single family.
"""

from __future__ import annotations

import pytest

from indic_namematch.matchers import (
    cascade, exact, hybrid, jaro_winkler, levenshtein, phonetic, rarity_weighted, token_set,
)


class TestExact:
    def test_identical_after_normalisation(self):
        assert exact("PRIYA MENON", "  Priya   Menon ") == 1.0

    def test_anything_else_is_zero(self):
        assert exact("Mohammed Irfan", "Mohammad Irfan") == 0.0


class TestLevenshtein:
    def test_catches_ocr_substitution(self):
        assert levenshtein("Rajesh Kumar", "Rajcsh Kumar") > 0.9

    def test_blind_to_word_order(self):
        assert levenshtein("Kumar Suresh", "Suresh Kumar") < 0.2

    def test_rates_siblings_above_a_real_ocr_match(self):
        """The defect that makes character distance unusable alone on Indian names.

        One letter apart is a scanner error or a different sibling, and edit distance
        cannot tell which. Here it is more confident about the wrong answer.
        """
        siblings = levenshtein("Rajesh Kumar Sharma", "Ramesh Kumar Sharma")
        ocr_damage = levenshtein("Rajesh Kumar", "Rajcsh Kumar")
        assert siblings > ocr_damage


class TestJaroWinkler:
    def test_handles_typos(self):
        assert jaro_winkler("Lakshmi Narayanan", "Laxmi Narayanan") > 0.9

    def test_blind_to_word_order(self):
        assert jaro_winkler("Kumar Suresh", "Suresh Kumar") < 0.7


class TestTokenSet:
    def test_word_order_is_free(self):
        assert token_set("Kumar Suresh", "Suresh Kumar") == 1.0
        assert token_set("Sharma Rajesh Kumar", "Rajesh Kumar Sharma") == 1.0

    def test_initials_expand(self):
        assert token_set("S. Kumar", "Suresh Kumar") == pytest.approx(0.925)

    def test_dropped_middle_name_costs_something_but_not_everything(self):
        assert 0.7 < token_set("Priya Lakshmi Menon", "Priya Menon") < 1.0

    def test_blind_inside_a_word(self):
        """Mohammed and Mohammad are simply not equal to token algebra."""
        assert token_set("Lakshmi Narayanan", "Laxmi Narayanan") == 0.5

    def test_cannot_separate_an_initial_collision(self):
        """The pair that costs this matcher five false positives on the benchmark."""
        assert token_set("S. Kumar", "Suresh Kumar") == token_set("S Kumar", "Sunita Kumar")


class TestPhonetic:
    def test_catches_transliteration(self):
        assert phonetic("Lakshmi Narayanan", "Laxmi Narayanan") > 0.95
        assert phonetic("Mohammed Irfan", "Mohammad Irfan") > 0.95

    def test_separates_gender_variants(self):
        assert phonetic("Sunil Chauhan", "Sunila Chauhan") < 0.6

    def test_cannot_handle_ocr_damage(self):
        """Sound tells you nothing about a scanner reading l as the digit 1."""
        assert phonetic("Balaji Iyengar", "Ba1aji Iyengar") < 0.6


class TestHybrid:
    @pytest.mark.parametrize("a,b", [
        ("Kumar Suresh", "Suresh Kumar"),
        ("Lakshmi Narayanan", "Laxmi Narayanan"),
        ("Ram Kumar", "Ramkumar"),
        ("Smt. Sunita Devi", "Sunita Devi"),
        ("Manjunath S/o Ramaiah", "Manjunath Ramaiah"),
    ])
    def test_handles_every_family_of_variation(self, a, b):
        assert hybrid(a, b) > 0.9

    def test_joined_fallback_needs_differing_token_counts(self):
        """Without that guard, whole-string distance overrides every token judgement.

        'rajeshkumarsharma' against 'rameshkumarsharma' is one edit in seventeen characters,
        which clears the joined floor. If the fallback applied here, siblings would score by
        raw string distance and land in the auto-approve band.
        """
        assert hybrid("Rajesh Kumar Sharma", "Ramesh Kumar Sharma") < 0.92
        assert hybrid("Ram Kumar", "Ramkumar") == 1.0

    def test_over_credits_common_tokens(self):
        """Why rarity_weighted exists: Kumar and Sharma count as much as a rare name."""
        assert hybrid("Rajesh Kumar Sharma", "Ramesh Kumar Sharma") > 0.9


class TestRarityWeighted:
    def test_discounts_siblings_relative_to_hybrid(self):
        a, b = "Rajesh Kumar Sharma", "Ramesh Kumar Sharma"
        assert rarity_weighted(a, b) < hybrid(a, b)

    def test_initial_collisions_drop_out_of_the_approve_band(self):
        """It still cannot separate them. Nothing can. It prices them honestly instead."""
        expanded = rarity_weighted("S. Kumar", "Suresh Kumar")
        collision = rarity_weighted("S Kumar", "Sunita Kumar")
        assert expanded == collision
        assert expanded < 0.7, "an initial plus the commonest surname is not enough evidence"

    def test_common_surname_pairs_score_low(self):
        assert rarity_weighted("Amit Singh", "Rahul Singh") < 0.4

    def test_still_catches_real_variation(self):
        assert rarity_weighted("Kumar Suresh", "Suresh Kumar") == 1.0
        assert rarity_weighted("Lakshmi Narayanan", "Laxmi Narayanan") > 0.95

    def test_known_limitation_exact_common_name(self):
        """Documented limitation: coverage is a ratio, so an exact match still scores 1.0.

        'Amit Kumar' against 'Amit Kumar' is two different people in the benchmark and no
        string function can separate it. This test pins the limitation so it cannot be
        silently 'fixed' without someone noticing.
        """
        assert rarity_weighted("Amit Kumar", "Amit Kumar") == 1.0


class TestCascade:
    @pytest.mark.parametrize("a,b,kind,score", [
        ("kumar", "kumar", "identical", 1.00),
        ("lakshmi", "laxmi", "phonetic", 0.95),
        ("s", "suresh", "initial", 0.85),
        ("padma", "zzzzz", "", 0.0),
    ])
    def test_ladder_picks_the_right_rung(self, a, b, kind, score):
        got_score, got_kind = cascade(a, b)
        assert got_kind == kind
        assert got_score == pytest.approx(score)

    def test_character_rung_is_scaled_not_flat(self):
        score, kind = cascade("rajesh", "ramesh")
        assert kind == "character"
        assert 0.7 < score < 0.8

    def test_identical_wins_over_every_other_rung(self):
        assert cascade("kumar", "kumar") == (1.0, "identical")


class TestCharacterFloor:
    """The 0.88 cutoff below which character similarity counts as no evidence at all.

    No benchmark pair happens to straddle this boundary, so without these tests the constant
    could be changed freely and every other test would still pass. These pin it directly.
    """

    def test_well_below_the_floor_yields_no_evidence(self):
        """sunil/sushil sits at Jaro-Winkler 0.858: two different people, correctly ignored."""
        from indic_namematch.metrics import jaro_winkler as jw

        assert jw("sunil", "sushil") < 0.88
        assert cascade("sunil", "sushil") == (0.0, "")

    def test_just_below_the_floor_yields_no_evidence(self):
        """kishan/krishnan sits at 0.875, inside the dead zone between 0.87 and 0.88.

        Chosen deliberately: without a pair in that narrow band, lowering the floor to 0.87
        would change real behaviour and no test in the suite would notice.
        """
        from indic_namematch.metrics import jaro_winkler as jw

        assert 0.87 <= jw("kishan", "krishnan") < 0.88
        assert cascade("kishan", "krishnan") == (0.0, ""), \
            "a pair below the floor must contribute nothing, not weak evidence"

    @pytest.mark.parametrize("a,b", [("ajay", "sanjay"), ("arpita", "sarita")])
    def test_above_the_floor_yields_scaled_character_evidence(self, a, b):
        from indic_namematch.metrics import jaro_winkler as jw

        assert jw(a, b) >= 0.88
        score, kind = cascade(a, b)
        assert kind == "character"
        assert score == pytest.approx(0.80 * jw(a, b))

    def test_a_stronger_rung_wins_even_when_the_floor_is_cleared(self):
        """The cascade is a priority ladder, not a maximum over independent tests.

        anita/amita clears the character floor at exactly 0.88, but it also shares a Soundex
        code and a syllable count, so the phonetic rung fires first and the character rung
        is never reached.
        """
        from indic_namematch.metrics import jaro_winkler as jw

        assert jw("anita", "amita") >= 0.88
        assert cascade("anita", "amita") == (0.95, "phonetic")

    def test_soundex_merges_m_and_n_which_is_a_known_limitation(self):
        """Soundex puts m and n in the same class, so amita and anita sound identical to it.

        Inherent to the 1918 algorithm, not something the syllable guard can fix. Pinned here
        so the behaviour is documented rather than discovered in production.
        """
        from indic_namematch.phonetics import same_sound

        assert same_sound("anita", "amita")
        assert same_sound("komal", "kamal")


class TestJoinedFloor:
    """The 0.92 whole-string cutoff for the token-boundary fallback.

    Like the character floor, no benchmark pair straddles this boundary, so it needs pinning
    from both sides or the constant is free to drift.
    """

    def test_above_the_floor_the_fallback_applies(self):
        """Naga Arjuna Rao / Nagarjuna Rao joins to 0.923, so the boundary case is rescued."""
        assert hybrid("Naga Arjuna Rao", "Nagarjuna Rao") > 0.92

    def test_just_below_the_floor_the_fallback_does_not_apply(self):
        """Hari Krishna / Harikrishnan joins to 0.917, which must not trigger the fallback.

        Lowering the floor to 0.90 would rescue this pair and change published scores, so
        this test is what stops that happening silently.
        """
        from indic_namematch.metrics import levenshtein_ratio
        from indic_namematch.normalize import normalize

        joined = levenshtein_ratio(normalize("Hari Krishna").replace(" ", ""),
                                   normalize("Harikrishnan").replace(" ", ""))
        assert 0.90 <= joined < 0.92
        assert hybrid("Hari Krishna", "Harikrishnan") < joined, \
            "the joined fallback fired below its floor"

    def test_the_fallback_needs_differing_token_counts(self):
        """Equal token counts must never reach the fallback, whatever the joined ratio."""
        from indic_namematch.metrics import levenshtein_ratio
        from indic_namematch.normalize import normalize

        a, b = "Rajesh Kumar Sharma", "Ramesh Kumar Sharma"
        joined = levenshtein_ratio(normalize(a).replace(" ", ""), normalize(b).replace(" ", ""))
        assert joined > 0.92, "this pair would clear the floor if the guard were removed"
        assert hybrid(a, b) < joined
