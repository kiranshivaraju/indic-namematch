# Contributing

Two kinds of contribution are especially useful: **benchmark rows** and **matchers**.

## Setup

```bash
git clone https://github.com/kiranshivaraju/indic-namematch
cd indic-namematch
pip install -e ".[dev]"
pytest -q
```

## Adding benchmark rows

The dataset is the most valuable part of this project, and the hardest to get right. A good
new row is one that some reasonable algorithm gets **wrong**.

Append to `benchmark/name_pairs.csv` with the next free `id`, and:

1. **Label by who the person actually is**, not by what a matcher could infer. Follow the
   five rules in `benchmark/DATASET.md`.
2. **Set `resolvable` honestly.** If your row has a structural twin already in the set with
   the opposite label, it is `no`. If you are unsure, say so in the `rationale` and mention
   it in the PR; it is better to discuss than to guess.
3. **Write a real `rationale`.** "Siblings sharing a father's name" is useful. "Different
   people" is not.
4. **Prefer hard negatives.** Easy ones inflate precision and teach nothing.
5. Regenerate the pins in the same commit:
   ```bash
   python benchmark/evaluate.py
   python -c "import json,csv;from indic_namematch.matchers import REGISTRY;\
   rows=list(csv.DictReader(open('benchmark/name_pairs.csv')));\
   json.dump({n:{r['id']:round(f(r['name_a'],r['name_b']),9) for r in rows} for n,f in REGISTRY.items()},\
   open('tests/expected_scores.json','w'),indent=1,sort_keys=True)"
   ```

The PR diff then shows exactly which scores moved, which is the review you want.

## Adding a matcher

A matcher is a function `(str, str) -> float` in `src/indic_namematch/matchers.py`, added to
`REGISTRY`. It must satisfy the contracts in `tests/test_contracts.py`, which run
automatically against every registered matcher:

- **symmetric**: `f(a, b) == f(b, a)`, including on empty and punctuation-only input
- **bounded**: always inside `[0.0, 1.0]`
- **reflexive**: a name with content scores 1.0 against itself
- **safe on contentless input**: a string that normalises to nothing never matches anything

Also add behaviour tests to `tests/test_matchers.py` covering both what it catches **and
where it fails**. The failure tests are what justify the composites.

## Changing scores

Any change to what a matcher outputs will fail `tests/test_regression.py`. That is
deliberate. If the change is intentional, regenerate `tests/expected_scores.json` and
`tests/expected_benchmark.json` in the same commit so the diff shows what moved.

Please also check the mutation sweep still bites. Every tuning constant in `matchers.py`
should break at least one test when nudged:

```bash
sed -i '' 's/^PHONETIC = 0.95$/PHONETIC = 0.93/' src/indic_namematch/matchers.py
pytest -q          # must fail
git checkout src/indic_namematch/matchers.py
```

## Before opening a PR

```bash
pytest -q
ruff check src tests benchmark
mypy src
python benchmark/evaluate.py
```

## Scope

In scope: normalisation, phonetics, token algebra, rarity weighting, threshold derivation,
benchmark data.

Out of scope for now: OCR and text extraction, native Indic script input (this library works
on Latin-script romanised names, which is what PAN and Aadhaar print), blocking and indexing
for search against large registries, and anything requiring a trained model or network access.
