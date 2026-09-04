# The benchmark: 120 labelled name pairs

`name_pairs.csv`, 120 rows, hand-authored. There is no generation script: the CSV is the
source of truth so it can be opened in a spreadsheet and audited row by row, which is
encouraged.

As far as we could find, there is no other public labelled benchmark for Indian name
matching. This one is small, but it is explicit about its own ceiling and it is extensible.
Contributions of new rows are welcome; see `CONTRIBUTING.md`.

## Columns

| column | meaning |
|---|---|
| `id` | 1..120, stable |
| `name_a`, `name_b` | the two extracted name strings |
| `label` | `match` = same human being, `non_match` = two different humans |
| `category` | the failure mode being probed, and the unit of the per-category breakdown |
| `resolvable` | `yes` if the answer is derivable from the two strings alone, `no` if it is not |
| `rationale` | why the pair carries the label it does |

## Composition

- 60 `match` / 60 `non_match`
- 10 control positives and 10 control negatives, trivial, present only to catch a broken
  implementation
- 100 hard pairs, split 50/50, across 19 further categories

The balance is deliberate. The headline metric is precision-weighted and precision is
estimated entirely from the negatives, so a positive-skewed set would leave too few
negatives to separate one algorithm from another.

Production traffic is nothing like 50/50; it is overwhelmingly genuine customers. **Absolute
precision measured here will read better than it would in production.** The ranking
transfers, the absolute number does not.

## Categories

Positive categories cover the ways one person's name legitimately drifts between two Indian
identity documents: initials versus expansions, surname-first ordering, transliteration with
no canonical spelling, middle names and father's names appearing and disappearing,
honorifics, token boundaries, OCR substitutions, and surname changes after marriage.

Negative categories cover the ways two *different* people end up looking alike in those same
records: siblings sharing a father's name and surname, spouses sharing a surname, gender
variants of one root, very common surnames, single-token records, and pairs that look like a
reorder but are not.

Every hard negative is deliberately close. Easy negatives earn nothing: they inflate
precision and hide the differences the benchmark exists to measure.

## Labelling policy

The label records **who the person actually is**, not what a matcher could reasonably work
out. Applied uniformly:

1. Honorifics and generational suffixes (`Smt.`, `Shri`, `Kumari`, `Dr.`, `Jr.`) carry no
   identity weight and never decide a label on their own.
2. A dropped middle name or father's name does not break identity when the remaining tokens
   line up.
3. An initial is consistent with any expansion starting with that letter. Consistent is not
   the same as sufficient, which is why `initial_collision` exists as a negative category.
4. A surname change after marriage is the same person, labelled `match`.
5. Token order carries no identity weight by itself.

## The `resolvable` column, and the ceiling it defines

18 of the 120 pairs are marked `resolvable = no`: the two strings genuinely do not contain
enough information, so any decision is a guess. It cuts both ways.

- `S Kumar` vs `Sunita Kumar`, labelled `non_match` because the S is Suresh. Identical in
  shape to row 21, which is a `match`.
- `Amit Kumar` vs `Amit Kumar`, labelled `non_match`. Two different individuals, identical
  strings.
- `Priya Menon` vs `Priya Kumar Sharma`, labelled `match`. One woman, after marriage.

This column is a judgement call, and in principle any failure could be hidden behind it. Two
things argue against that. Every value was assigned while the dataset was being written,
before any algorithm existed, so it cannot be retrofitted to excuse a result. And for 17 of
the 18 it is not really opinion: each has a **structural twin** elsewhere in the dataset
carrying the opposite label, so any rule that gets one right must get the other wrong.

| shape | one row | its twin |
|---|---|---|
| a string against an identical copy | #1 `Rajesh Kumar Sharma` (match) | #92 `Amit Kumar` (non-match) |
| initial + surname vs full name + same surname | #21 `S. Kumar` / `Suresh Kumar` (match) | #87 `S Kumar` / `Sunita Kumar` (non-match) |
| one name is the other minus a token | #44 `Priya Lakshmi Menon` / `Priya Menon` (match) | #110 `Kumar` / `Suresh Kumar` (non-match) |
| surname differing by one spelling variant | #40 `Anirban Chowdhury` / `Choudhury` (match) | #83 `Manoj Tiwari` / `Tiwary` (non-match) |
| the same tokens in the opposite order | #28 `Kumar Suresh` / `Suresh Kumar` (match) | #114 `Ram Mohan` / `Mohan Ram` (non-match) |

The one genuine judgement call is row 85, `Meena Sundaram` / `Meenakshi Sundaram`, which has
no exact twin. It is defensible and a reviewer could reasonably disagree.

These rows are in the set on purpose. They put a hard ceiling on achievable accuracy and they
are the argument for the three-band design: a name matcher should emit a score with an
abstain band and route these to review or to a second factor such as PAN or date of birth,
rather than deciding them at all.

**If any algorithm reports near-perfect accuracy on this dataset, something is wrong with it
or with these labels.**

## Known limitations

- 120 pairs is small. Rankings are meaningful; absolute percentages carry a few points of
  noise either way.
- The data is synthetic and hand-authored by one person, so it reflects the failure modes
  that person thought of. Real traffic will contain modes it does not.
- It is deliberately adversarial, roughly 86% hard pairs. Do not read the absolute review
  volumes as production forecasts.
- With 60 negatives, one false positive is 1.67% FPR, so the harness cannot resolve risk
  budgets finer than that.
