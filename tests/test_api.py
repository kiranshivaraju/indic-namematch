"""The public surface: NameMatcher, explain, and the CLI."""

from __future__ import annotations

import pytest

from indic_namematch import Decision, NameMatcher, RarityTable, __version__
from indic_namematch.bands import Bands
from indic_namematch.cli import main


class TestNameMatcher:
    def test_score_and_decide_agree(self):
        m = NameMatcher()
        for a, b in [("Kumar Suresh", "Suresh Kumar"), ("Amit Verma", "Fatima Sheikh")]:
            assert m.decide(a, b) is m.bands.decide(m.score(a, b))

    def test_default_bands_route_the_headline_cases(self):
        m = NameMatcher()
        assert m.decide("Kumar Suresh", "Suresh Kumar") is Decision.APPROVE
        assert m.decide("Rajesh Kumar Sharma", "Ramesh Kumar Sharma") is Decision.REVIEW
        assert m.decide("Amit Verma", "Fatima Sheikh") is Decision.REJECT

    def test_custom_rarity_changes_the_answer(self):
        a, b = "Rajesh Kumar Sharma", "Ramesh Kumar Sharma"
        assert NameMatcher(rarity=RarityTable.uniform()).score(a, b) > NameMatcher().score(a, b)

    def test_custom_bands_are_respected(self):
        m = NameMatcher(bands=Bands(approve_at=0.5, reject_below=0.1))
        assert m.decide("Rajesh Kumar Sharma", "Ramesh Kumar Sharma") is Decision.APPROVE

    def test_is_stateless_across_calls(self):
        m = NameMatcher()
        first = m.score("S. Kumar", "Suresh Kumar")
        for _ in range(5):
            m.score("something", "else")
        assert m.score("S. Kumar", "Suresh Kumar") == first


class TestExplain:
    def test_reconstructs_the_score(self):
        e = NameMatcher().explain("Rajesh Kumar Sharma", "Ramesh Kumar Sharma")
        assert e.score == pytest.approx(NameMatcher().score(e.name_a, e.name_b))
        assert e.decision is Decision.REVIEW

    def test_reports_the_evidence_kind_per_token(self):
        e = NameMatcher().explain("Lakshmi Narayanan", "Laxmi Narayanan")
        kinds = {(m.token_a, m.token_b): m.kind for m in e.matches}
        assert kinds[("narayanan", "narayanan")] == "identical"
        assert kinds[("lakshmi", "laxmi")] == "phonetic"

    def test_shows_common_tokens_contributing_little(self):
        e = NameMatcher().explain("Rajesh Kumar Sharma", "Ramesh Kumar Sharma")
        by_token = {m.token_a: m for m in e.matches}
        assert by_token["kumar"].similarity == 1.0, "kumar matched perfectly"
        assert by_token["kumar"].contribution < 0.2, "and still contributed almost nothing"

    def test_reports_unmatched_tokens(self):
        e = NameMatcher().explain("Priya Lakshmi Menon", "Priya Menon")
        assert "lakshmi" in e.unmatched_a
        assert e.unmatched_b == []

    def test_is_printable(self):
        text = str(NameMatcher().explain("S. Kumar", "Suresh Kumar"))
        assert "REVIEW" in text and "kumar" in text


class TestCLI:
    def test_scores_a_pair(self, capsys):
        assert main(["S. Kumar", "Suresh Kumar"]) == 0
        assert "REVIEW" in capsys.readouterr().out

    def test_explain_flag(self, capsys):
        main(["Lakshmi Narayanan", "Laxmi Narayanan", "--explain"])
        assert "phonetic" in capsys.readouterr().out

    def test_all_flag_lists_every_matcher(self, capsys):
        main(["S. Kumar", "Suresh Kumar", "--all"])
        out = capsys.readouterr().out
        for name in ["exact", "levenshtein", "jaro_winkler", "token_set",
                     "phonetic", "hybrid", "rarity_weighted"]:
            assert name in out


def test_version_is_exported():
    assert __version__.count(".") == 2


class TestEdgeCases:
    """Boundary behaviour that is easy to get wrong and never exercised by real names."""

    def test_levenshtein_handles_empty_operands(self):
        from indic_namematch.metrics import jaro, levenshtein, levenshtein_ratio

        assert levenshtein("", "") == 0
        assert levenshtein("", "abc") == 3
        assert levenshtein("abc", "") == 3
        assert levenshtein_ratio("", "") == 1.0
        assert jaro("", "abc") == 0.0
        assert jaro("abc", "") == 0.0

    def test_explain_reports_tokens_unmatched_on_either_side(self):
        e = NameMatcher().explain("Priya Lakshmi Menon", "Priya Menon Nair")
        text = str(e)
        assert "(nothing)" in text, "unmatched tokens should be visible in the printout"
        assert e.unmatched_a and e.unmatched_b

    def test_repr_round_trips_configuration(self):
        m = NameMatcher(rarity=RarityTable.uniform())
        text = repr(m)
        assert "NameMatcher" in text and "RarityTable" in text and "Bands" in text

    def test_rarity_table_reports_its_size(self):
        assert len(RarityTable()) > 50
        assert len(RarityTable.uniform()) == 0
        assert "initial_weight" in repr(RarityTable())
