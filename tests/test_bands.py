"""Threshold derivation and the three-band decision."""

from __future__ import annotations

import pytest

from indic_namematch.bands import Bands, Decision, derive


class TestBands:
    def test_places_scores(self):
        b = Bands(approve_at=0.9, reject_below=0.4)
        assert b.decide(0.95) is Decision.APPROVE
        assert b.decide(0.90) is Decision.APPROVE
        assert b.decide(0.65) is Decision.REVIEW
        assert b.decide(0.40) is Decision.REVIEW
        assert b.decide(0.39) is Decision.REJECT

    def test_rejects_inverted_thresholds(self):
        with pytest.raises(ValueError):
            Bands(approve_at=0.3, reject_below=0.8)

    def test_rejects_out_of_range(self):
        with pytest.raises(ValueError):
            Bands(approve_at=1.5, reject_below=0.1)


class TestDerive:
    def test_makes_zero_avoidable_errors(self):
        scored = [(0.95, True), (0.90, True), (0.70, False), (0.20, False)]
        b = derive(scored)
        for score, is_match in scored:
            d = b.decide(score)
            assert not (d is Decision.APPROVE and not is_match), "auto-approved a non-match"
            assert not (d is Decision.REJECT and is_match), "auto-rejected a match"

    def test_undecidable_pairs_do_not_collapse_the_approve_band(self):
        """An identical-strings non-match would otherwise push approve_at above everything."""
        scored = [(1.00, True), (1.00, False), (0.90, True), (0.20, False)]
        collapsed = derive(scored)
        sensible = derive(scored, decidable=[True, False, True, True])
        assert collapsed.approve_at > 1.0, "including it should push the band out of range"
        assert sensible.approve_at < 1.0

    def test_clean_separation_gives_an_empty_review_band(self):
        scored = [(0.9, True), (0.8, True), (0.3, False), (0.1, False)]
        b = derive(scored)
        assert b.approve_at == pytest.approx(b.reject_below)

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError):
            derive([(0.5, True)], decidable=[True, True])

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            derive([])

    def test_derived_bands_hold_on_the_real_benchmark(self, pairs):
        """The guarantee the whole design rests on, checked against real data."""
        from indic_namematch.matchers import rarity_weighted

        scores = [rarity_weighted(p["name_a"], p["name_b"]) for p in pairs]
        b = derive([(s, p["is_match"]) for s, p in zip(scores, pairs)],
                   [p["decidable"] for p in pairs])
        for s, p in zip(scores, pairs):
            if not p["decidable"]:
                continue
            d = b.decide(s)
            assert not (d is Decision.APPROVE and not p["is_match"]), \
                f"row {p['id']} auto-approved but is a non-match"
            assert not (d is Decision.REJECT and p["is_match"]), \
                f"row {p['id']} auto-rejected but is a match"
