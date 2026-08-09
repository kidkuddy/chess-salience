"""Exploratory analysis, exactly as EXPLORATORY.md §5 specifies it.

This is NOT the confirmatory analysis. `pilot_report.py` reads its thresholds off the
frozen `PREREGISTRATION.md`; this file reads its thresholds off `EXPLORATORY.md`, which
was written on 2026-08-09 after seeing the crashed pilot's partial data and committed
before the full-run positions existed. Every number this prints is exploratory and must be
labelled as such wherever it is reported.

  §5.1  p(C1), p(C2) by severity band, cluster-bootstrap CIs over positions within band
  §5.2  RD = p(C2) - p(C1) within each band, same bootstrap
  §5.3  interaction contrast RD_decisive - RD_minor, cluster bootstrap, CI must exclude 0
        (+ a position-clustered Wald test on the interaction as a parametric cross-check)
  §5.4  C1 flatness: slope over ordered bands, C1 only. The claim predicts a CI CONTAINING 0.
  §5.5  C2 sensitivity: the same slope on C2. The claim predicts a CI EXCLUDING 0, positive.

  §6    support requires ALL FOUR of: interaction CI excludes 0; band RDs ordered
        minor < major < decisive; decisive RD CI excludes 0; C1 slope CI contains 0 while
        C2 slope CI excludes 0.

  python exploratory_report.py [--raw data/full_raw.jsonl]
                               [--positions data/full_positions.jsonl]
                               [--json data/exploratory_report.json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from pilot_report import load, per_position_rates

HERE = Path(__file__).parent
BOOT = 10_000
SEED = 20260809
BANDS = ["minor", "major", "decisive"]
BAND_IDX = {b: i for i, b in enumerate(BANDS)}


def band_of(positions: dict) -> dict:
    return {pid: p["severity_band"] for pid, p in positions.items()}


def ci(samples: np.ndarray, level: float = 95.0) -> list[float]:
    lo = (100 - level) / 2
    return [float(np.percentile(samples, lo)), float(np.percentile(samples, 100 - lo))]


def boot_mean(values: np.ndarray, rng, n_boot=BOOT) -> np.ndarray:
    """Resample POSITIONS with replacement — the cluster is the position."""
    if len(values) == 0:
        return np.array([np.nan])
    idx = rng.integers(0, len(values), size=(n_boot, len(values)))
    return values[idx].mean(axis=1)


def slope_over_bands(by_band: dict[str, np.ndarray], rng, n_boot=BOOT) -> dict:
    """OLS slope of the position-level rate on the ordered band index (0,1,2).

    Bootstrapped by resampling positions within each band independently, so the CI
    inherits the same cluster structure as every other interval in this study.
    """
    present = [b for b in BANDS if len(by_band.get(b, [])) > 0]
    if len(present) < 2:
        return {"slope": float("nan"), "ci95": [float("nan")] * 2, "n_bands": len(present)}

    def fit(samples: dict[str, np.ndarray]) -> float:
        xs, ys = [], []
        for b in present:
            xs.append(BAND_IDX[b])
            ys.append(float(np.mean(samples[b])))
        x, y = np.array(xs, float), np.array(ys, float)
        return float(np.polyfit(x, y, 1)[0])

    point = fit({b: by_band[b] for b in present})
    draws = np.empty(n_boot)
    for k in range(n_boot):
        draws[k] = fit({b: by_band[b][rng.integers(0, len(by_band[b]), len(by_band[b]))]
                        for b in present})
    return {"slope": point, "ci95": ci(draws), "n_bands": len(present)}


def clustered_wald(recs, bands: dict) -> dict:
    """Binomial GLM, detected ~ condition * severity_band, position-clustered covariance.

    Parametric cross-check on §5.3 only. The bootstrap contrast is the headline.
    """
    try:
        import pandas as pd
        import statsmodels.formula.api as smf
    except Exception as exc:                                     # pragma: no cover
        return {"available": False, "reason": str(exc)}

    rows = [
        {"detected": int(bool(r["score"].get("hit_square"))),
         "condition": r["condition"],
         "band": bands.get(r["position_id"], "?"),
         "position": r["position_id"]}
        for r in recs
        if r["condition"] in ("C1", "C2") and not r.get("is_error")
        and r["position_id"] in bands
    ]
    df = pd.DataFrame(rows)
    if df.empty or df["band"].nunique() < 2:
        return {"available": False, "reason": "insufficient band coverage"}
    df["band"] = pd.Categorical(df["band"], categories=BANDS, ordered=True)
    try:
        import statsmodels.api as sm
        fit = smf.glm("detected ~ C(condition) * band", data=df,
                      family=sm.families.Binomial()).fit(
            cov_type="cluster", cov_kwds={"groups": df["position"]})
        terms = [t for t in fit.params.index if ":" in t]
        if not terms:
            return {"available": False, "reason": "interaction not estimable"}
        wald = fit.wald_test(terms, scalar=True)
        # Perfect separation (a condition x band cell at 0.0 or 1.0) blows the logit
        # coefficient up to ~20+ and makes the Wald statistic meaningless. It is a real
        # possibility here: the pilot's decisive/C2 cell sat at 1.000. Flag it rather
        # than let a p-value of 1e-205 be quoted as if it meant something.
        cells = df.groupby(["condition", "band"], observed=True)["detected"].mean()
        separated = [f"{c}/{b}={v:.3f}" for (c, b), v in cells.items() if v in (0.0, 1.0)]
        return {"available": True, "terms": terms,
                "statistic": float(wald.statistic), "p_value": float(wald.pvalue),
                "coefficients": {t: float(fit.params[t]) for t in terms},
                "separation_detected": bool(separated),
                "separated_cells": separated,
                "caveat": ("perfect separation in the cells listed; this Wald test is "
                           "not interpretable and the bootstrap contrast is the headline")
                if separated else None}
    except Exception as exc:
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(HERE / "data" / "full_raw.jsonl"))
    ap.add_argument("--positions", default=str(HERE / "data" / "full_positions.jsonl"))
    ap.add_argument("--json", default=str(HERE / "data" / "exploratory_report.json"))
    args = ap.parse_args()

    recs, positions = load(Path(args.raw), Path(args.positions))
    bands = band_of(positions)
    rng = np.random.default_rng(SEED)

    c1 = per_position_rates(recs, "C1")
    c2 = per_position_rates(recs, "C2")
    paired = sorted(set(c1) & set(c2))

    out: dict = {
        "warning": "EXPLORATORY. Not pre-registered in PREREGISTRATION.md. "
                   "Hypothesis formed on pilot data 2026-08-09; tested here on fresh positions.",
        "n_positions_paired": len(paired),
        "band_counts": {b: sum(1 for p in paired if bands.get(p) == b) for b in BANDS},
    }

    # §5.1 / §5.2 -----------------------------------------------------------
    per_band: dict = {}
    rd_draws: dict[str, np.ndarray] = {}
    for b in BANDS:
        ids = [p for p in paired if bands.get(p) == b]
        if not ids:
            per_band[b] = {"n_positions": 0}
            continue
        a1 = np.array([c1[p] for p in ids])
        a2 = np.array([c2[p] for p in ids])
        d = a2 - a1
        idx = rng.integers(0, len(ids), size=(BOOT, len(ids)))
        rd_draws[b] = d[idx].mean(axis=1)
        per_band[b] = {
            "n_positions": len(ids),
            "p_c1": float(a1.mean()), "p_c1_ci95": ci(boot_mean(a1, rng)),
            "p_c2": float(a2.mean()), "p_c2_ci95": ci(boot_mean(a2, rng)),
            "rd": float(d.mean()), "rd_ci95": ci(rd_draws[b]),
        }
    out["by_band"] = per_band

    # §5.3 interaction contrast --------------------------------------------
    if "decisive" in rd_draws and "minor" in rd_draws:
        contrast = rd_draws["decisive"] - rd_draws["minor"]
        out["interaction"] = {
            "contrast": "RD_decisive - RD_minor",
            "point": float(per_band["decisive"]["rd"] - per_band["minor"]["rd"]),
            "ci95": ci(contrast),
            "excludes_zero": bool(ci(contrast)[0] > 0 or ci(contrast)[1] < 0),
        }
    else:
        out["interaction"] = {"available": False}
    out["interaction_wald_crosscheck"] = clustered_wald(recs, bands)

    # §5.4 / §5.5 slopes ----------------------------------------------------
    out["c1_flatness"] = slope_over_bands(
        {b: np.array([c1[p] for p in paired if bands.get(p) == b]) for b in BANDS}, rng)
    out["c2_sensitivity"] = slope_over_bands(
        {b: np.array([c2[p] for p in paired if bands.get(p) == b]) for b in BANDS}, rng)

    # §6 support criterion --------------------------------------------------
    rds = [per_band[b].get("rd") for b in BANDS if per_band[b].get("n_positions")]
    ordered = len(rds) == 3 and rds[0] < rds[1] < rds[2]
    dec_ci = per_band.get("decisive", {}).get("rd_ci95")
    dec_excl = bool(dec_ci and (dec_ci[0] > 0 or dec_ci[1] < 0))
    c1_ci = out["c1_flatness"]["ci95"]
    c2_ci = out["c2_sensitivity"]["ci95"]
    c1_flat = bool(c1_ci[0] <= 0 <= c1_ci[1])
    c2_rises = bool(c2_ci[0] > 0)
    inter = bool(out["interaction"].get("excludes_zero"))
    checks = {
        "interaction_ci_excludes_zero": inter,
        "band_rds_ordered_minor_lt_major_lt_decisive": ordered,
        "decisive_rd_ci_excludes_zero": dec_excl,
        "c1_slope_ci_contains_zero_and_c2_slope_positive": bool(c1_flat and c2_rises),
    }
    out["support"] = {
        "checks": checks,
        "all_four_met": all(checks.values()),
        "verdict": "SUPPORTED" if all(checks.values()) else "NOT SUPPORTED",
    }

    Path(args.json).write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
