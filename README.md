# indic-namematch

[![CI](https://github.com/kiranshivaraju/indic-namematch/actions/workflows/ci.yml/badge.svg)](https://github.com/kiranshivaraju/indic-namematch/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/indic-namematch.svg)](https://pypi.org/project/indic-namematch/)
[![Python](https://img.shields.io/pypi/pyversions/indic-namematch.svg)](https://pypi.org/project/indic-namematch/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Matching person names across Indian identity documents.

The same person's name is written differently on a PAN card, an Aadhaar, a passport and a
bank statement. It gets abbreviated to initials, reordered surname-first, transliterated with
a different spelling, stripped of a middle name, prefixed with an honorific, or mangled by
OCR. General-purpose fuzzy matching handles this badly, because it has no idea that half of
North India shares a surname.

```python
from indic_namematch import NameMatcher

m = NameMatcher()

m.score("Kumar Suresh", "Suresh Kumar")        # 1.000  surname-first ordering
m.score("Lakshmi Narayanan", "Laxmi Narayanan")# 0.975  transliteration
m.score("Smt. Sunita Devi", "Sunita Devi")     # 1.000  honorific
m.score("Ram Kumar", "Ramkumar")               # 1.000  token boundary

m.score("Rajesh Kumar Sharma", "Ramesh Kumar Sharma")  # 0.886  two brothers
m.score("S. Kumar", "Sunita Kumar")                    # 0.653  not the same person
```

## Installation

**Pure standard library. No dependencies, no build step.**

```bash
pip install indic-namematch
```

Python 3.8 or newer.

## Three bands, not two

Production KYC does not answer match or no-match. It answers auto-approve, send to a human,
or auto-reject, and the middle band is where a matcher should decline rather than guess.

```python
from indic_namematch import NameMatcher, Decision

m = NameMatcher()
m.decide("Kumar Suresh", "Suresh Kumar")               # Decision.APPROVE
m.decide("Rajesh Kumar Sharma", "Ramesh Kumar Sharma") # Decision.REVIEW
m.decide("Amit Verma", "Fatima Sheikh")                # Decision.REJECT
```

This is not a stylistic choice. Some pairs are genuinely undecidable from the strings: two
people are both named `Amit Kumar`, and no function of two identical strings can separate
them from a real match on two identical strings. Since nothing can score higher than an exact
match, refusing to ever produce a false positive means auto-approving nobody. The honest
design routes the uncertainty to a human instead of pretending it away.

## Rarity weighting

Agreeing on `Kumar` proves almost nothing. Agreeing on `Padmanabhan` nearly settles it. This
is Fellegi & Sunter (1969), and it is the difference between auto-approving two brothers and
not.

The bundled table is a coarse hand-curated tier list. **Replace it** with frequencies from
your own records and the weights become measured rather than assumed:

```python
from indic_namematch import NameMatcher, RarityTable

table = RarityTable.from_counts({"kumar": 50_000, "sharma": 9_000, "padmanabhan": 12})
m = NameMatcher(rarity=table)

RarityTable.from_csv("token_counts.csv")   # two columns: token, count
RarityTable.uniform()                      # disable rarity weighting entirely
```

## Explaining a score

The first question anyone asks is "why did it score that". So:

```python
print(m.explain("Rajesh Kumar Sharma", "Ramesh Kumar Sharma"))
```

```
'Rajesh Kumar Sharma' vs 'Ramesh Kumar Sharma'
  normalised : 'rajesh kumar sharma' | 'ramesh kumar sharma'
  kumar ~ kumar: 1.00 (identical) x weight 0.15 = 0.150
  sharma ~ sharma: 1.00 (identical) x weight 0.40 = 0.400
  rajesh ~ ramesh: 0.73 (character) x weight 0.40 = 0.292
  score 0.886 -> REVIEW
```

`kumar` matched perfectly and contributed 0.150. That is the whole idea.

## Command line

```bash
indic-namematch "S. Kumar" "Suresh Kumar"
indic-namematch "Lakshmi Narayanan" "Laxmi Narayanan" --explain
indic-namematch "Rajesh Kumar Sharma" "Ramesh Kumar Sharma" --all
```

## What it handles

| | example | score |
|---|---|---|
| initials expanded | `S. Kumar` / `Suresh Kumar` | 0.653 |
| surname-first ordering | `Kumar Suresh` / `Suresh Kumar` | 1.000 |
| transliteration | `Lakshmi Narayanan` / `Laxmi Narayanan` | 0.975 |
| dropped middle name | `Priya Lakshmi Menon` / `Priya Menon` | 0.615 |
| honorifics and suffixes | `Smt. Sunita Devi` / `Sunita Devi` | 1.000 |
| relationship markers | `Manjunath S/o Ramaiah` / `Manjunath Ramaiah` | 1.000 |
| patronymic initials | `Nithya B` / `Nithya Balakrishnan` | 0.716 |
| token boundaries | `Ram Kumar` / `Ramkumar` | 1.000 |
| OCR damage | `Balaji Iyengar` / `Ba1aji Iyengar` | 0.864 |

And, just as importantly, what it keeps **apart**:

| | example | score |
|---|---|---|
| siblings | `Rajesh Kumar Sharma` / `Ramesh Kumar Sharma` | 0.886 |
| gender variants | `Nandan Kumar` / `Nandini Kumar` | 0.763 |
| shared common surname | `Amit Singh` / `Rahul Singh` | 0.273 |
| initial collisions | `S Kumar` / `Sunita Kumar` | 0.653 |

## The algorithms

Seven, across five families, chosen so their failure modes do not overlap. `rarity_weighted`
is the one `NameMatcher` uses; the rest are exposed for comparison and research.

| matcher | family | what it adds |
|---|---|---|
| `exact` | equality | floor, for reference |
| `levenshtein` | character edits | OCR substitutions |
| `jaro_winkler` | character + prefix | typos, shared prefixes |
| `token_set` | token algebra | reordering, dropped names, initials |
| `phonetic` | sound | transliteration (Soundex + syllable guard) |
| `hybrid` | composite | best evidence per token |
| `rarity_weighted` | composite + rarity | the above, weighted by token rarity |

```python
from indic_namematch import REGISTRY
REGISTRY["phonetic"]("Lakshmi Narayanan", "Laxmi Narayanan")   # 0.975
```

## Benchmark

`benchmark/` holds 120 hand-labelled pairs across 21 categories, 60 matches and 60
non-matches, with a harness that runs every algorithm and reports a per-category breakdown
plus every individual error.

```bash
python3 benchmark/evaluate.py
```

Notably, 18 pairs are marked as **not resolvable from the strings alone**, and for 17 of them
that is provable: each has a structural twin elsewhere in the set with the same shape and the
opposite label, so any rule that gets one right must get the other wrong. They set an explicit
ceiling on what any string algorithm can achieve. See `benchmark/DATASET.md`.

## Design notes

* Matchers return a score, never a decision. A threshold is a business parameter.
* `score(a, b) == score(b, a)` is an enforced contract, tested on every pair. Neither
  document in a KYC pair is authoritative and you do not control which arrives first.
* Soundex alone maps `sunil` and `sunila` to the same code, which merges men and women. The
  syllable guard fixes that without costing anything on real transliteration variants.
* Name matching alone cannot close identity. It is one signal beside PAN, date of birth and
  face match, and it should be allowed to abstain.

## Project layout

```
src/indic_namematch/
  normalize.py    honorifics, S/o markers, unicode, tokenising
  metrics.py      Levenshtein and Jaro-Winkler, implemented from scratch
  phonetics.py    Soundex plus the syllable guard
  rarity.py       RarityTable, the Fellegi-Sunter weighting
  alignment.py    token pairing and coverage
  matchers.py     the seven algorithms
  bands.py        Decision, Bands, derive()
  cli.py          the indic-namematch command
benchmark/
  name_pairs.csv  120 labelled pairs across 21 categories
  DATASET.md      how it was built, the labelling policy, its known ceiling
  evaluate.py     the harness
  results/        regenerated on every run
tests/            253 tests, 100% coverage
```

## Contributing

New benchmark rows are the most valuable contribution, particularly ones that some
reasonable algorithm gets wrong. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
