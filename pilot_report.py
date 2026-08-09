"""Pilot analysis, exactly as PREREGISTRATION.md §2-§4 specify it.

Nothing here chooses a metric or a threshold; it reads them off the frozen document:

  §2  primary hit_square, secondary hit_move, unit = position, paired RD = p(C2) - p(C1),
      cluster bootstrap over positions (10,000 resamples, 95% percentile), McNemar exact
      on the position-level majority binarisation, headline = the CONSERVATIVE pairing
      (worst C1 paraphrase vs best C2 paraphrase).
  §3  the floor is empirical p(C0), not 1/64; collapse and equivalence branches with the
      thresholds stated there.
  §4  N for the full run, from the OBSERVED discordance, targeting RD = 0.25 at 80% power.

The floor deserves a word. C0 has no position, so a C0 response cannot be right or wrong
on its own. What it gives is the model's guess distribution over squares. Each of the 9
C0 responses is therefore scored against every position's critical square: p(C0) is the
rate at which a blind guess would have hit, averaged over the same positions the other
arms are measured on. That is the only construction under which p(C0) is on the same
scale as p(C1).

  python pilot_report.py [--raw data/pilot_raw.jsonl] [--json data/pilot_report.json]
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

HERE = Path(__file__).parent
BOOT = 10_000
SEED = 20260805

# --- frozen thresholds, quoted from the pre-registration -------------------
RD_HEADLINE = 0.25          # §2
RD_CI_FLOOR = 0.15          # §2
COLLAPSE_MARGIN = 0.10      # §3
TOST_MARGIN = 0.10          # §3
TARGET_POWER = 0.80         # §4
ALPHA = 0.05                # §4


def load(raw: Path, positions: Path):
    recs = [json.loads(l) for l in raw.read_text().splitlines() if l.strip()]
    pos = {p["id"]: p for p in
           (json.loads(l) for l in positions.read_text().splitlines() if l.strip())}
    return recs, pos


def per_position_rates(recs, condition, metric="hit_square", variant=None):
    """{position_id: rate over its calls} for one arm."""
    hits = defaultdict(list)
    for r in recs:
        if r["condition"] != condition or r.get("is_error"):
            continue
        if variant and r["variant"] != variant:
            continue
        hits[r["position_id"]].append(bool(r["score"].get(metric)))
    return {p: float(np.mean(v)) for p, v in hits.items() if v}


def floor_rates(recs, positions):
    """p(C0) per position: how often the blind-guess responses named THAT position's square."""
    guesses = [set(r["score"]["squares_mentioned"]) for r in recs
               if r["condition"] == "C0" and not r.get("is_error")]
    out = {}
    for pid, p in positions.items():
        accept = {s.lower() for s in p["accept_squares"]}
        hit = [bool(accept & {s.lower() for s in g}) for g in guesses]
        out[pid] = float(np.mean(hit)) if hit else 0.0
    return out, guesses


def cluster_bootstrap(diffs: dict, ids: list, rng, n_boot=BOOT):
    """Resample POSITIONS with replacement — the cluster is the position, per §2."""
    arr = np.array([diffs[i] for i in ids])
    idx = rng.integers(0, len(arr), size=(n_boot, len(arr)))
    return arr[idx].mean(axis=1)


def mcnemar_exact(a_rates: dict, b_rates: dict, ids: list):
    """Position-level majority binarisation, then the exact (binomial) McNemar test."""
    b = c = concordant = 0
    for i in ids:
        x, y = a_rates[i] > 0.5, b_rates[i] > 0.5
        if y and not x:
            b += 1
        elif x and not y:
            c += 1
        else:
            concordant += 1
    n = b + c + concordant
    p = stats.binomtest(b, b + c, 0.5).pvalue if (b + c) else 1.0
    odds = (b / c) if c else (float("inf") if b else 1.0)
    return {"b_c2_only": b, "c_c1_only": c, "concordant": concordant,
            "n": n, "discordant_rate": (b + c) / n if n else 0.0,
            "p_exact": p, "odds_ratio": odds}


def shift_to_target(r1: np.ndarray, r2: np.ndarray, target: float) -> np.ndarray:
    """Move the C1 rates so the mean RD is exactly `target`, keeping their spread.

    Power at the pre-registered effect is what §4 asks for, not power at whatever the
    pilot happened to show. Shifting C1 (rather than scaling the whole thing) preserves
    the observed per-position heterogeneity and the observed C2 ceiling, which is what
    drives discordance and therefore N.
    """
    lo, hi = -1.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if float(np.mean(r2 - np.clip(r1 + mid, 0, 1))) > target:
            lo = mid
        else:
            hi = mid
    return np.clip(r1 + (lo + hi) / 2, 0, 1)


def power_for_n(r1: np.ndarray, r2: np.ndarray, n: int, rng, calls=9, sims=2000) -> float:
    """Monte-Carlo power of the exact McNemar test at sample size n.

    Positions are resampled from the pilot with replacement, so the simulation inherits
    the observed between-position heterogeneity rather than assuming a common rate —
    that heterogeneity is exactly why §4 warns against sizing on a plain logistic.
    """
    rejects = 0
    for _ in range(sims):
        pick = rng.integers(0, len(r1), size=n)
        h1 = rng.binomial(calls, r1[pick]) / calls > 0.5
        h2 = rng.binomial(calls, r2[pick]) / calls > 0.5
        b = int(np.sum(h2 & ~h1))
        c = int(np.sum(h1 & ~h2))
        if b + c and stats.binomtest(b, b + c, 0.5).pvalue < ALPHA:
            rejects += 1
    return rejects / sims


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(HERE / "data" / "pilot_raw.jsonl"))
    ap.add_argument("--positions", default=str(HERE / "data" / "pilot_positions.jsonl"))
    ap.add_argument("--json", default=str(HERE / "data" / "pilot_report.json"))
    ap.add_argument("--sims", type=int, default=2000)
    args = ap.parse_args()

    rng = np.random.default_rng(SEED)
    recs, positions = load(Path(args.raw), Path(args.positions))
    report: dict = {}

    errors = [r for r in recs if r.get("is_error")]
    report["calls"] = {"total": len(recs), "errors": len(errors),
                       "cost_usd": round(sum(r.get("cost_usd") or 0 for r in recs), 4)}
    by_cond = Counter(r["condition"] for r in recs)
    report["calls"]["by_condition"] = dict(by_cond)

    c1 = per_position_rates(recs, "C1")
    c2 = per_position_rates(recs, "C2")
    ids = sorted(set(c1) & set(c2))
    report["n_positions"] = len(ids)

    c0, guesses = floor_rates(recs, positions)
    p0 = float(np.mean([c0[i] for i in ids]))
    p1 = float(np.mean([c1[i] for i in ids]))
    p2 = float(np.mean([c2[i] for i in ids]))

    # --- §2 primary: paired RD, cluster bootstrap ---------------------------
    diffs = {i: c2[i] - c1[i] for i in ids}
    boots = cluster_bootstrap(diffs, ids, rng)
    rd = float(np.mean([diffs[i] for i in ids]))
    ci95 = [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]
    ci90 = [float(np.percentile(boots, 5)), float(np.percentile(boots, 95))]

    report["floor"] = {"p_c0": p0, "guess_squares": Counter(
        s for g in guesses for s in g).most_common(10), "n_c0_calls": len(guesses)}
    report["primary"] = {
        "metric": "hit_square", "p_c1": p1, "p_c2": p2, "rd": rd,
        "ci95_cluster_bootstrap": ci95, "ci90_cluster_bootstrap": ci90,
        "mcnemar": mcnemar_exact(c1, c2, ids),
    }

    # --- §2 strict secondary -------------------------------------------------
    m1 = per_position_rates(recs, "C1", "hit_move")
    m2 = per_position_rates(recs, "C2", "hit_move")
    mids = sorted(set(m1) & set(m2))
    mdiff = {i: m2[i] - m1[i] for i in mids}
    mboot = cluster_bootstrap(mdiff, mids, rng)
    report["secondary_hit_move"] = {
        "p_c1": float(np.mean([m1[i] for i in mids])),
        "p_c2": float(np.mean([m2[i] for i in mids])),
        "rd": float(np.mean([mdiff[i] for i in mids])),
        "ci95": [float(np.percentile(mboot, 2.5)), float(np.percentile(mboot, 97.5))],
    }

    # --- §2 conservative pairing = the pre-registered headline number -------
    per_variant = {}
    for cond in ("C1", "C2"):
        for v in ("a", "b", "c"):
            r = per_position_rates(recs, cond, "hit_square", v)
            if r:
                per_variant[f"{cond}.{v}"] = r
    c2_best = max((k for k in per_variant if k.startswith("C2")),
                  key=lambda k: np.mean(list(per_variant[k].values())))
    cons = {}
    for k in [k for k in per_variant if k.startswith("C1")]:
        common = sorted(set(per_variant[k]) & set(per_variant[c2_best]))
        d = {i: per_variant[c2_best][i] - per_variant[k][i] for i in common}
        bb = cluster_bootstrap(d, common, rng)
        cons[k] = {"rd": float(np.mean(list(d.values()))),
                   "ci95": [float(np.percentile(bb, 2.5)), float(np.percentile(bb, 97.5))],
                   "mcnemar": mcnemar_exact(per_variant[k], per_variant[c2_best], common)}
    worst = min(cons, key=lambda k: cons[k]["rd"])
    report["conservative_pairing"] = {
        "best_c2": c2_best, "worst_c1": worst,
        "per_variant_mean": {k: float(np.mean(list(v.values()))) for k, v in per_variant.items()},
        "per_c1_variant_vs_best_c2": cons,
        "headline": cons[worst],
    }

    # --- §3 branches ---------------------------------------------------------
    d20 = {i: c2[i] - c0[i] for i in ids}
    b20 = cluster_bootstrap(d20, ids, rng)
    ci_20 = [float(np.percentile(b20, 2.5)), float(np.percentile(b20, 97.5))]
    head = cons[worst]
    fires_headline = head["rd"] >= RD_HEADLINE and head["ci95"][0] >= RD_CI_FLOOR
    collapse = (p1 - p0 <= COLLAPSE_MARGIN and p2 - p0 <= COLLAPSE_MARGIN
                and ci_20[0] <= 0 <= ci_20[1])
    equivalence = ci90[0] > -TOST_MARGIN and ci90[1] < TOST_MARGIN
    report["branches"] = {
        "headline_fires": bool(fires_headline),
        "collapse_fires": bool(collapse),
        "equivalence_fires": bool(equivalence),
        "p_c2_minus_p_c0": float(np.mean(list(d20.values()))), "ci95_c2_minus_c0": ci_20,
    }

    # --- §4 N for the full run ----------------------------------------------
    r1 = np.array([c1[i] for i in ids])
    r2 = np.array([c2[i] for i in ids])
    r1t = shift_to_target(r1, r2, RD_HEADLINE)
    obs_disc = report["primary"]["mcnemar"]["discordant_rate"]
    curve = {}
    n_needed = None
    for n in (20, 30, 40, 60, 80, 100, 120, 160, 200, 240):
        pw = power_for_n(r1t, r2, n, rng, sims=args.sims)
        curve[n] = pw
        if n_needed is None and pw >= TARGET_POWER:
            n_needed = n
    report["power"] = {
        "observed_discordant_rate": obs_disc,
        "target_rd": RD_HEADLINE, "target_power": TARGET_POWER, "alpha": ALPHA,
        "curve_at_rd_0.25": curve, "n_positions_needed": n_needed,
        "power_at_pilot_effect_n40": power_for_n(r1, r2, 40, rng, sims=args.sims),
        "pilot_n_was_enough": bool(n_needed is not None and n_needed <= len(ids)),
    }

    # --- controls and the C3 ceiling on these positions ---------------------
    nsq = defaultdict(list)
    for r in recs:
        if r["condition"] in ("C0", "C1", "C2") and not r.get("is_error"):
            nsq[r["condition"]].append(r["score"].get("n_squares_mentioned", 0))
    report["length_cap_control"] = {k: round(float(np.mean(v)), 2) for k, v in nsq.items()}

    c3 = per_position_rates(recs, "C3", "critical_square_correct")
    if c3:
        report["ceiling_c3"] = {"mean_critical_square_correct": float(np.mean(list(c3.values()))),
                                "n_positions": len(c3)}
        ok = [i for i in ids if c3.get(i, 0) > 0.5]
        if ok:
            dr = {i: c2[i] - c1[i] for i in ok}
            bb = cluster_bootstrap(dr, ok, rng)
            report["ceiling_c3"]["rd_on_reconstructed_subset"] = {
                "n": len(ok), "rd": float(np.mean(list(dr.values()))),
                "ci95": [float(np.percentile(bb, 2.5)), float(np.percentile(bb, 97.5))]}

    Path(args.json).write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
