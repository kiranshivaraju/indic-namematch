# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-09-07

Packaging and documentation only. No behaviour change: every score, threshold and
benchmark number is identical to 0.1.0.

### Fixed

- License metadata used the deprecated file form, so PyPI displayed the entire MIT text
  where the sidebar expects an identifier. Now declared as the SPDX expression `MIT`
  (PEP 639), which also removes the now-redundant `License :: OSI Approved` classifier.
- `CONTRIBUTING.md` referred to `matchers.py` rather than its real path,
  `src/indic_namematch/matchers.py`.

### Added

- `Source`, `Changelog` and `Benchmark` project URLs, which become sidebar links on PyPI.
- An explicit **Installation** heading in the README, and a **Project layout** section.

## [0.1.0] - 2026-09-07

First release.

### Added

- `NameMatcher` with `score()`, `decide()` and `explain()`.
- Seven matchers across five families, all exposed through `REGISTRY`: `exact`,
  `levenshtein`, `jaro_winkler`, `token_set`, `phonetic`, `hybrid`, `rarity_weighted`.
- `RarityTable` for Fellegi-Sunter token rarity weighting, constructible from your own
  token frequencies via `from_counts()` or `from_csv()`, or disabled with `uniform()`.
- Three-band decisions (`Decision.APPROVE` / `REVIEW` / `REJECT`) with `Bands.derive()`
  to fit thresholds to labelled data such that no decidable pair is auto-decided wrongly.
- Indian-specific normalisation: honorifics, generational suffixes, relationship markers
  (`S/o`, `D/o`, `W/o`, `C/o`), unicode folding and punctuation handling.
- Soundex with a syllable-count guard, which keeps gender variants such as
  `sunil`/`sunila` apart while still matching transliteration variants such as
  `mohammed`/`mohammad`.
- `indic-namematch` command line entry point with `--all` and `--explain`.
- A 120-pair labelled benchmark across 21 categories, with a harness that reports both a
  three-band and a single-threshold comparison plus every individual error.
- Type hints throughout and a `py.typed` marker.

### Notes

- `sri` is deliberately **not** treated as an honorific. It is a genuine title in South
  India and also the first syllable of Sriram, Srinivas and Sridhar, and stripping it
  breaks more pairs than it fixes.
- Soundex places `m` and `n` in the same class, so `anita` and `amita` are treated as the
  same name. This is inherent to the 1918 algorithm and is pinned as a known limitation.
- Coverage is a ratio, so an exact agreement on a common full name still scores 1.0.
  `Amit Kumar` against `Amit Kumar` is undecidable from the strings and separating it
  requires absolute evidence mass against real frequencies.
