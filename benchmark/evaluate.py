"""Run every matcher over the labelled benchmark and report a comparison.

    python3 benchmark/evaluate.py

Outputs to stdout and to ``benchmark/results/``. Exits non-zero if the dataset fails
validation or any matcher breaks the symmetry contract.

Two views are reported, because they answer different questions:

* **Three-band.** Each matcher gets two thresholds derived so that no *decidable* pair is
  ever auto-decided wrongly. Both error types are then pinned at zero, no arbitrary risk
  tolerance has to be invented, and the only thing left varying is how much human review
  each matcher costs. That answers "what would we deploy".

* **Single threshold.** Every matcher faces one identical rule instead: maximise recall
  subject to a false positive rate ceiling. That answers "which matcher is better", since
  the bands above are derived per-matcher and are otherwise not comparable.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict
from typing import Dict, List

from indic_namematch import REGISTRY
from indic_namematch.bands import derive

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "name_pairs.csv")
OUT = os.path.join(HERE, "results")

BETA = 0.5                      # < 1 weights precision above recall
FPR_BUDGETS = (0.01, 0.02, 0.05, 0.10)
PRIMARY_BUDGET = 0.05


def load_pairs(path: str = DATA) -> List[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["id"] = int(r["id"])
        r["is_match"] = r["label"] == "match"
        r["decidable"] = r["resolvable"] == "yes"
    return rows


def validate(pairs: List[dict]) -> List[str]:
    problems = []
    ids = [p["id"] for p in pairs]
    if len(set(ids)) != len(ids):
        problems.append("duplicate ids")
    for p in pairs:
        if p["label"] not in ("match", "non_match"):
            problems.append(f"row {p['id']}: bad label {p['label']!r}")
        if p["resolvable"] not in ("yes", "no"):
            problems.append(f"row {p['id']}: bad resolvable {p['resolvable']!r}")
        if not p["name_a"].strip() or not p["name_b"].strip():
            problems.append(f"row {p['id']}: empty name")
    return problems


def score_pairs(fn, pairs):
    """Score every pair in both directions and report any asymmetry or out-of-range score."""
    scores, violations = [], []
    for p in pairs:
        ab = fn(p["name_a"], p["name_b"])
        ba = fn(p["name_b"], p["name_a"])
        if abs(ab - ba) > 1e-9:
            violations.append((p["id"], p["name_a"], p["name_b"], ab, ba))
        elif not 0.0 <= ab <= 1.0:
            violations.append((p["id"], p["name_a"], p["name_b"], ab, "out of range"))
        scores.append(ab)
    return scores, violations


def metrics(tp: int, fp: int, fn_: int, tn: int) -> dict:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn_) if (tp + fn_) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    denom = (BETA ** 2 * precision) + recall
    fbeta = (1 + BETA ** 2) * precision * recall / denom if denom else 0.0
    return {
        "tp": tp, "fp": fp, "fn": fn_, "tn": tn,
        "precision": precision, "recall": recall, "fpr": fpr, "fbeta": fbeta,
        "accuracy": (tp + tn) / (tp + fp + fn_ + tn),
    }


def confusion(scores, pairs, threshold):
    tp = fp = fn_ = tn = 0
    for s, p in zip(scores, pairs):
        predicted = s >= threshold
        if p["is_match"]:
            tp += predicted
            fn_ += not predicted
        else:
            fp += predicted
            tn += not predicted
    return tp, fp, fn_, tn


def sweep(scores, pairs):
    uniq = sorted(set(scores))
    return [(t, metrics(*confusion(scores, pairs, t))) for t in uniq + [max(uniq) + 1e-9]]


def best_under_budget(curve, budget):
    feasible = [(t, m) for t, m in curve if m["fpr"] <= budget]
    if not feasible:
        return None
    return max(feasible, key=lambda tm: (tm[1]["recall"], tm[1]["precision"], tm[0]))


def band_stats(scores, pairs, bands):
    approve = [i for i, s in enumerate(scores) if s >= bands.approve_at]
    reject = [i for i, s in enumerate(scores) if s < bands.reject_below]
    review = [i for i in range(len(scores)) if i not in set(approve) | set(reject)]
    n_pos = sum(p["is_match"] for p in pairs)
    fp = [i for i in approve if not pairs[i]["is_match"]]
    fn_ = [i for i in reject if pairs[i]["is_match"]]
    return {
        "approve_rate": sum(1 for i in approve if pairs[i]["is_match"]) / n_pos,
        "review_rate": len(review) / len(pairs),
        "reject_rate": len(reject) / len(pairs),
        "unavoidable_fp": [i for i in fp if not pairs[i]["decidable"]],
        "unavoidable_fn": [i for i in fn_ if not pairs[i]["decidable"]],
        "avoidable_fp": [i for i in fp if pairs[i]["decidable"]],
        "avoidable_fn": [i for i in fn_ if pairs[i]["decidable"]],
    }


def main() -> int:
    pairs = load_pairs()
    problems = validate(pairs)
    if problems:
        print("DATASET INVALID:")
        for p in problems:
            print("  -", p)
        return 1

    lines: List[str] = []

    def emit(s: str = "") -> None:
        lines.append(s)
        print(s)

    n_match = sum(p["is_match"] for p in pairs)
    emit("=" * 96)
    emit("INDIC-NAMEMATCH BENCHMARK")
    emit("=" * 96)
    emit(f"pairs              : {len(pairs)} ({n_match} match / {len(pairs) - n_match} non_match)")
    emit(f"undecidable pairs  : {sum(1 for p in pairs if not p['decidable'])} "
         f"(no correct answer exists from the strings alone)")
    emit(f"metric             : F-beta with beta={BETA}, precision weighted above recall")
    emit()

    all_scores: Dict[str, List[float]] = {}
    results: Dict[str, dict] = {}
    failed = False

    for name, fn in REGISTRY.items():
        scores, violations = score_pairs(fn, pairs)
        all_scores[name] = scores
        if violations:
            failed = True
            emit(f"[FAIL] {name}: {len(violations)} symmetry or range violation(s)")
            for v in violations[:5]:
                emit(f"        id={v[0]} {v[1]!r} vs {v[2]!r} -> {v[3]} / {v[4]}")
            continue
        bands = derive(
            [(s, p["is_match"]) for s, p in zip(scores, pairs)],
            [p["decidable"] for p in pairs],
        )
        curve = sweep(scores, pairs)
        results[name] = {
            "bands": bands,
            "stats": band_stats(scores, pairs, bands),
            "chosen": best_under_budget(curve, PRIMARY_BUDGET),
            "budgets": {b: best_under_budget(curve, b) for b in FPR_BUDGETS},
        }

    if failed:
        emit("Symmetry is a hard contract. Fix the matcher before trusting any number below.")
        return 1

    emit("-" * 96)
    emit("THREE-BAND: thresholds pinned so no DECIDABLE pair is auto-decided wrongly")
    emit("-" * 96)
    emit(f"{'matcher':20}{'reject<':>9}{'approve>=':>11}{'approve%':>10}{'review%':>9}"
         f"{'reject%':>9}{'unavoid.FP':>12}{'unavoid.FN':>12}")
    emit("-" * 96)
    for name, r in results.items():
        b, s = r["bands"], r["stats"]
        emit(f"{name:20}{b.reject_below:>9.3f}{b.approve_at:>11.3f}"
             f"{s['approve_rate'] * 100:>9.1f}%{s['review_rate'] * 100:>8.1f}%"
             f"{s['reject_rate'] * 100:>8.1f}%"
             f"{len(s['unavoidable_fp']):>12}{len(s['unavoidable_fn']):>12}")
    emit()

    for name, r in results.items():
        s = r["stats"]
        assert not s["avoidable_fp"] and not s["avoidable_fn"], \
            f"{name}: bands failed their own zero-avoidable-error guarantee"
    emit("  All matchers verified: zero avoidable errors inside the automatic bands.")
    emit()

    for name, r in results.items():
        s = r["stats"]
        if s["unavoidable_fp"] or s["unavoidable_fn"]:
            emit(f"  {name} unavoidable auto-errors:")
            for kind, idx in (("FP", s["unavoidable_fp"]), ("FN", s["unavoidable_fn"])):
                for i in idx:
                    p = pairs[i]
                    emit(f"    {kind} id={p['id']:>3} {p['name_a']!r} vs {p['name_b']!r}"
                         f"  [{p['category']}]")
    emit()

    emit("-" * 96)
    emit(f"SINGLE THRESHOLD: max recall subject to FPR <= {PRIMARY_BUDGET:.0%}")
    emit("-" * 96)
    emit(f"{'matcher':20}{'thr':>8}{'prec':>8}{'recall':>8}{'F0.5':>8}"
         f"{'FPR':>8}{'FP':>5}{'FN':>5}{'acc':>8}")
    emit("-" * 96)
    for name, r in results.items():
        if r["chosen"] is None:
            emit(f"{name:20}{'n/a':>8}   cannot reach the budget at any threshold")
            continue
        t, m = r["chosen"]
        emit(f"{name:20}{t:>8.3f}{m['precision']:>8.3f}{m['recall']:>8.3f}{m['fbeta']:>8.3f}"
             f"{m['fpr']:>8.3f}{m['fp']:>5}{m['fn']:>5}{m['accuracy']:>8.3f}")
    emit()

    emit("-" * 96)
    emit("RECALL AT EACH FPR BUDGET: genuine traffic auto-approved per unit of risk")
    emit("-" * 96)
    emit(f"{'matcher':20}" + "".join(f"{'FPR<=' + format(b, '.0%'):>14}" for b in FPR_BUDGETS))
    emit("-" * 96)
    for name, r in results.items():
        row = f"{name:20}"
        for b in FPR_BUDGETS:
            hit = r["budgets"][b]
            row += f"{'--' if hit is None else format(hit[1]['recall'], '.3f'):>14}"
        emit(row)
    emit()

    cats = sorted({p["category"] for p in pairs})
    emit("-" * 96)
    emit("PER-CATEGORY ACCURACY at the single-threshold operating point")
    emit("-" * 96)
    emit(f"{'category':24}{'n':>4}" + "".join(f"{k[:13]:>15}" for k in results))
    emit("-" * 96)
    per_cat: Dict[str, Dict[str, float]] = defaultdict(dict)
    for cat in cats:
        idx = [i for i, p in enumerate(pairs) if p["category"] == cat]
        row = f"{cat:24}{len(idx):>4}"
        for name, r in results.items():
            t = r["chosen"][0]
            ok = sum(1 for i in idx
                     if (all_scores[name][i] >= t) == pairs[i]["is_match"])
            per_cat[cat][name] = ok / len(idx)
            row += f"{f'{ok}/{len(idx)}':>15}"
        emit(row)
    emit()

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "summary.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    with open(os.path.join(OUT, "scores.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "name_a", "name_b", "label", "category", "resolvable", *results])
        for i, p in enumerate(pairs):
            w.writerow([p["id"], p["name_a"], p["name_b"], p["label"], p["category"],
                        p["resolvable"], *[round(all_scores[n][i], 4) for n in results]])
    with open(os.path.join(OUT, "errors.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["matcher", "id", "error", "score", "threshold",
                                           "resolvable", "category", "name_a", "name_b"])
        w.writeheader()
        for name, r in results.items():
            t = r["chosen"][0]
            for i, p in enumerate(pairs):
                if (all_scores[name][i] >= t) != p["is_match"]:
                    w.writerow({"matcher": name, "id": p["id"],
                                "error": "FP" if not p["is_match"] else "FN",
                                "score": round(all_scores[name][i], 4),
                                "threshold": round(t, 4), "resolvable": p["resolvable"],
                                "category": p["category"],
                                "name_a": p["name_a"], "name_b": p["name_b"]})
    with open(os.path.join(OUT, "metrics.json"), "w", encoding="utf-8") as fh:
        json.dump({
            "beta": BETA,
            "primary_fpr_budget": PRIMARY_BUDGET,
            "matchers": {
                n: {
                    "bands": {"approve_at": r["bands"].approve_at,
                              "reject_below": r["bands"].reject_below},
                    "approve_rate": r["stats"]["approve_rate"],
                    "review_rate": r["stats"]["review_rate"],
                    "unavoidable_fp_ids": [pairs[i]["id"] for i in r["stats"]["unavoidable_fp"]],
                    "unavoidable_fn_ids": [pairs[i]["id"] for i in r["stats"]["unavoidable_fn"]],
                    "single_threshold": r["chosen"][1],
                    "threshold": r["chosen"][0],
                    "per_category_accuracy": {c: per_cat[c][n] for c in cats},
                } for n, r in results.items()
            },
        }, fh, indent=2)

    print(f"wrote {OUT}/summary.txt, scores.csv, errors.csv, metrics.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
