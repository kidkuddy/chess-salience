"""Robustness analyses that the pre-registration did not specify.

These are post-hoc by construction and are reported as such. Each one exists because a
reviewer can ask for it from artifacts the paper already prints, and it is better to
compute it than to leave it to be computed against us.

  1. Chance-hit floor. PREREGISTRATION.md treats p(C0) as the guess rate. The model
     refused C0 rather than guessing (mean n_squares_mentioned = 0), so p(C0) = 0 is a
     refusal rate and carries no information about accidental hits in C1/C2, whose
     answers name ~11 squares each. Two nulls are computed instead: a permutation null
     (each response re-scored against a different position's critical square) and the
     uniform-square null the scorer already records per response. Detection rates are
     then chance-corrected and the primary contrast is recomputed.

  2. Paraphrase pairing in both directions. PREREGISTRATION.md §2 fixes the adversarial
     pairing as the MINIMUM RD across C1 paraphrases against the best-detecting C2
     paraphrase. That is the conservative direction for a SUPERIORITY claim. The claim
     that fired is equivalence, under which the conservative direction inverts. Both are
     reported, with the selection bias stated.

  3. Power for the branch that was actually pre-registered. pilot_report.py computes the
     power of a bare exact McNemar test. PREREGISTRATION.md §2 fires the headline only on
     a CONJUNCTION (observed RD >= 0.25 AND 95% CI lower >= 0.15), and the equivalence
     branch has its own operating characteristic, which was never computed.

  4. Interval estimates for two rates the paper reports as points: the floor (0/9) and
     the scorer audit (49/50).

  python robustness.py [--raw data/full_raw.jsonl] [--json data/robustness.json]
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

import pilot_report as P

HERE = Path(__file__).parent
BOOT = 10_000
SEED = 20260811

PERM_REPS = 200          # permutation draws per response
POWER_SIMS = 2_000       # simulated studies per branch
POWER_BOOT = BOOT        # bootstrap resamples inside each simulated study
CURVE_SIMS = 4_000       # sims for the McNemar curve, per RESULTS.md's method note
CALLS = 9                # calls per position per arm


# --- 1. chance-hit floor ---------------------------------------------------

def mention_stats(recs):
    out = defaultdict(list)
    for r in recs:
        if r["condition"] in ("C0", "C1", "C2") and not r.get("is_error"):
            out[r["condition"]].append(r["score"].get("n_squares_mentioned", 0))
    return {k: {"mean_squares_mentioned": round(float(np.mean(v)), 3), "n": len(v)}
            for k, v in sorted(out.items())}


def uniform_null(recs, condition):
    """Mean of the scorer's own per-response uniform-square chance estimate."""
    v = [r["score"]["chance_rate_estimate"] for r in recs
         if r["condition"] == condition and not r.get("is_error")
         and r["score"].get("chance_rate_estimate") is not None]
    return float(np.mean(v))


def permuted_rates(recs, positions, condition, rng, reps=PERM_REPS):
    """Per-position chance-hit rate: re-score each response against OTHER positions.

    The response is held fixed and the critical square is swapped for one drawn from a
    different position in the same set. Averaging over draws gives the probability that
    this response would have hit a randomly chosen position's square -- the accidental
    hit rate the 150-word cap was supposed to equalise.
    """
    pids = sorted(positions)
    accept = {p: {s.lower() for s in positions[p]["accept_squares"]} for p in pids}
    by_pos = defaultdict(list)
    for r in recs:
        if r["condition"] != condition or r.get("is_error"):
            continue
        if r["position_id"] not in accept:
            continue
        said = {s.lower() for s in r["score"].get("squares_mentioned", [])}
        others = [p for p in pids if p != r["position_id"]]
        draws = rng.choice(len(others), size=reps)
        hits = [bool(accept[others[d]] & said) for d in draws]
        by_pos[r["position_id"]].append(float(np.mean(hits)))
    return {p: float(np.mean(v)) for p, v in by_pos.items() if v}


def corrected(obs: float, chance: float) -> float:
    """Chance-corrected detection rate: the share of the non-chance headroom recovered."""
    return (obs - chance) / (1.0 - chance) if chance < 1.0 else float("nan")


def chance_corrected_block(recs, positions, ids, rng):
    o1 = P.per_position_rates(recs, "C1")
    o2 = P.per_position_rates(recs, "C2")
    k1 = permuted_rates(recs, positions, "C1", rng)
    k2 = permuted_rates(recs, positions, "C2", rng)
    ids = [i for i in ids if i in k1 and i in k2]

    a_o1 = np.array([o1[i] for i in ids]); a_o2 = np.array([o2[i] for i in ids])
    a_k1 = np.array([k1[i] for i in ids]); a_k2 = np.array([k2[i] for i in ids])

    idx = rng.integers(0, len(ids), size=(BOOT, len(ids)))
    rd_boot = np.array([
        corrected(a_o2[row].mean(), a_k2[row].mean())
        - corrected(a_o1[row].mean(), a_k1[row].mean())
        for row in idx
    ])
    c1c = corrected(a_o1.mean(), a_k1.mean())
    c2c = corrected(a_o2.mean(), a_k2.mean())
    return {
        "n_positions": len(ids),
        "observed": {"c1": round(float(a_o1.mean()), 3), "c2": round(float(a_o2.mean()), 3),
                     "rd": round(float(a_o2.mean() - a_o1.mean()), 3)},
        "permutation_null": {"c1": round(float(a_k1.mean()), 3),
                             "c2": round(float(a_k2.mean()), 3)},
        "uniform_null": {"c1": round(uniform_null(recs, "C1"), 3),
                         "c2": round(uniform_null(recs, "C2"), 3)},
        "chance_corrected": {"c1": round(c1c, 3), "c2": round(c2c, 3),
                             "rd": round(c2c - c1c, 3)},
        "ci90": [round(float(np.percentile(rd_boot, 5)), 3),
                 round(float(np.percentile(rd_boot, 95)), 3)],
        "ci95": [round(float(np.percentile(rd_boot, 2.5)), 3),
                 round(float(np.percentile(rd_boot, 97.5)), 3)],
    }


# --- 2. paraphrase pairings in both directions -----------------------------

def pairing_block(recs, ids, rng):
    v1 = {v: P.per_position_rates(recs, "C1", variant=v) for v in "abc"}
    v2 = {v: P.per_position_rates(recs, "C2", variant=v) for v in "abc"}
    means1 = {v: float(np.mean([r[i] for i in ids])) for v, r in v1.items()}
    means2 = {v: float(np.mean([r[i] for i in ids])) for v, r in v2.items()}
    best_c2 = max(means2, key=means2.get)

    rows = {}
    for v, r1 in v1.items():
        diffs = {i: v2[best_c2][i] - r1[i] for i in ids}
        boot = P.cluster_bootstrap(diffs, ids, rng)
        mc = P.mcnemar_exact(r1, v2[best_c2], ids)
        rows[f"C1.{v}"] = {
            "p_c1": round(means1[v], 3),
            "rd": round(float(np.mean(list(diffs.values()))), 3),
            "ci95": [round(float(np.percentile(boot, 2.5)), 3),
                     round(float(np.percentile(boot, 97.5)), 3)],
            "mcnemar_p": round(mc["p_exact"], 3),
        }
    min_rd = min(rows, key=lambda k: rows[k]["rd"])
    max_rd = max(rows, key=lambda k: rows[k]["rd"])
    return {
        "p_c1_by_variant": {k: round(v, 3) for k, v in means1.items()},
        "p_c2_by_variant": {k: round(v, 3) for k, v in means2.items()},
        "best_c2_variant": f"C2.{best_c2}",
        "vs_best_c2": rows,
        "prereg_literal_min_rd": {"variant": min_rd, **rows[min_rd]},
        "equivalence_adversarial_max_rd": {"variant": max_rd, **rows[max_rd]},
    }


# --- 3. power for the branches as written ----------------------------------

def _simulate(r1t, r2, n, rng, sims, boot):
    """Yield (observed RD, 90% CI, 95% CI) for `sims` simulated studies of size n."""
    for _ in range(sims):
        pick = rng.integers(0, len(r1t), size=n)
        h1 = rng.binomial(CALLS, r1t[pick]) / CALLS
        h2 = rng.binomial(CALLS, r2[pick]) / CALLS
        d = h2 - h1
        idx = rng.integers(0, n, size=(boot, n))
        means = d[idx].mean(axis=1)
        yield (float(d.mean()),
               (float(np.percentile(means, 5)), float(np.percentile(means, 95))),
               (float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))))


def mcnemar_curve(r1, r2, rng, grid=(60, 80, 90, 100), sims=CURVE_SIMS):
    """The curve pilot_report.py computes, on the grid the paper actually quotes.

    data/full_report.json carries this curve at the script default of 2,000 sims and
    without an n = 90 point, while RESULTS.md quotes it at 4,000 sims including n = 90.
    Recomputing it here makes the artifact and the prose agree.
    """
    r1t = P.shift_to_target(r1, r2, P.RD_HEADLINE)
    return {str(n): round(P.power_for_n(r1t, r2, n, rng, sims=sims), 4) for n in grid}


def branch_power(r1, r2, n, rng, true_rd, sims=POWER_SIMS, boot=POWER_BOOT):
    r1t = P.shift_to_target(r1, r2, true_rd)
    head = equiv = excl0 = 0
    for rd, ci90, ci95 in _simulate(r1t, r2, n, rng, sims, boot):
        if rd >= P.RD_HEADLINE and ci95[0] >= P.RD_CI_FLOOR:
            head += 1
        if -P.TOST_MARGIN < ci90[0] and ci90[1] < P.TOST_MARGIN:
            equiv += 1
        if ci95[0] > 0 or ci95[1] < 0:
            excl0 += 1
    return {"true_rd": true_rd, "n": n, "sims": sims,
            "p_headline_branch_fires": head / sims,
            "p_equivalence_branch_fires": equiv / sims,
            "p_ci95_excludes_zero": excl0 / sims}


# --- 4. interval estimates for reported point rates ------------------------

def wilson(k: int, n: int, conf=0.95):
    lo, hi = stats.binomtest(k, n).proportion_ci(confidence_level=conf, method="wilson")
    return [round(float(lo), 3), round(float(hi), 3)]


# --- main ------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(HERE / "data" / "full_raw.jsonl"))
    ap.add_argument("--positions", default=str(HERE / "data" / "full_positions.jsonl"))
    ap.add_argument("--json", default=str(HERE / "data" / "robustness.json"))
    ap.add_argument("--sims", type=int, default=POWER_SIMS)
    args = ap.parse_args()

    rng = np.random.default_rng(SEED)
    recs, positions = P.load(Path(args.raw), Path(args.positions))
    o1 = P.per_position_rates(recs, "C1")
    o2 = P.per_position_rates(recs, "C2")
    ids = sorted(set(o1) & set(o2))
    r1 = np.array([o1[i] for i in ids])
    r2 = np.array([o2[i] for i in ids])
    n = len(ids)

    report = {
        "seed": SEED, "n_positions": n, "boot": BOOT,
        "mention_density": mention_stats(recs),
        "chance_hit": chance_corrected_block(recs, positions, ids, rng),
        "pairings": pairing_block(recs, ids, rng),
        "mcnemar_power_curve_at_rd_0.25": {
            "sims": CURVE_SIMS,
            "curve": mcnemar_curve(r1, r2, np.random.default_rng(P.SEED)),
        },
        "branch_power": {
            "headline_at_rd_0.25": branch_power(r1, r2, n, rng, 0.25, sims=args.sims),
            "equivalence_at_rd_0.00": branch_power(r1, r2, n, rng, 0.00, sims=args.sims),
            "equivalence_at_rd_0.05": branch_power(r1, r2, n, rng, 0.05, sims=args.sims),
        },
        "intervals": {
            "floor_p_c0_0_of_9": wilson(0, 9),
            "scorer_error_1_of_50": wilson(1, 50),
            "scorer_agreement_49_of_50": wilson(49, 50),
        },
    }

    Path(args.json).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
