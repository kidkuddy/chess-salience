"""The remaining analyses the paper needs, none of which cost an API call.

Five things, all computable from data already on disk:

  1. The exploratory severity analysis, recomputed on `detected_self`. It currently runs on
     hit_square, which the retrofit shows has specificity 0.382, so one Results section is
     scored on a metric the paper's own validation discredits.
  2. The GLMM PREREGISTRATION.md §2 specified and nobody fitted. With one model and one
     format it reduces to detected ~ condition + (1|position) + (1|prompt_variant).
  3. A margin-sensitivity curve, so the equivalence verdict is reported across a range of
     margins instead of resting on a ±0.10 that was never derived from anything.
  4. The paraphrase pairing table, recomputed on `detected_self`.
  5. The configuration table, recovered from the raw run records.

  python final_analyses.py
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np

import pilot_report as P

HERE = Path(__file__).parent
BOOT = 10_000
SEED = 20260813


def load_detected_self() -> dict:
    """{(condition, variant, position_id, repeat): detected_self} from the retrofit."""
    out = {}
    for r in (json.loads(l) for l in
              (HERE / "data" / "extract_raw.jsonl").read_text().splitlines() if l.strip()):
        if r.get("is_error") or r.get("extract_repeat") != 0:
            continue
        out[(r["condition"], r["variant"], r["position_id"], r["repeat"])] = \
            bool(r["detected_self"])
    return out


def per_position(ds: dict, cond: str, variant: str | None = None) -> dict:
    g = defaultdict(list)
    for (c, v, pid, _), hit in ds.items():
        if c == cond and (variant is None or v == variant):
            g[pid].append(hit)
    return {p: float(np.mean(v)) for p, v in g.items()}


def rd_ci(a: dict, b: dict, rng, boot=BOOT):
    ids = sorted(set(a) & set(b))
    d = {i: b[i] - a[i] for i in ids}
    s = P.cluster_bootstrap(d, ids, rng, n_boot=boot)
    return (float(np.mean(list(d.values()))),
            [float(np.percentile(s, 2.5)), float(np.percentile(s, 97.5))],
            [float(np.percentile(s, 5)), float(np.percentile(s, 95))], s)


def main() -> None:
    rng = np.random.default_rng(SEED)
    ds = load_detected_self()
    pos = {p["id"]: p for p in (json.loads(l) for l in
           (HERE / "data" / "full_positions.jsonl").read_text().splitlines() if l.strip())}
    out = {}

    c1, c2 = per_position(ds, "C1"), per_position(ds, "C2")
    rd, ci95, ci90, boot = rd_ci(c1, c2, rng)

    # --- 1. exploratory severity, on detected_self -------------------------
    print("=== 1. Exploratory severity, recomputed on detected_self ===")
    print("    (EXPLORATORY.md predicted C1 flat across bands, C2 rising)")
    bands = defaultdict(lambda: {"C1": defaultdict(list), "C2": defaultdict(list)})
    for (c, _, pid, _), hit in ds.items():
        if c in ("C1", "C2"):
            bands[pos[pid]["severity_band"]][c][pid].append(hit)
    order = ["minor", "major", "decisive"]
    sev = {}
    for b in order:
        a = {p: float(np.mean(v)) for p, v in bands[b]["C1"].items()}
        z = {p: float(np.mean(v)) for p, v in bands[b]["C2"].items()}
        r, c95, _, _ = rd_ci(a, z, rng, boot=4000)
        sev[b] = {"p_c1": float(np.mean(list(a.values()))),
                  "p_c2": float(np.mean(list(z.values()))), "rd": r, "ci95": c95,
                  "n": len(a)}
        print(f"  {b:<9} C1 {sev[b]['p_c1']:.3f}  C2 {sev[b]['p_c2']:.3f}  "
              f"RD {r:+.3f}  95% [{c95[0]:+.3f}, {c95[1]:+.3f}]  (n={len(a)})")
    inter = sev["decisive"]["rd"] - sev["minor"]["rd"]
    ordered = sev["minor"]["rd"] < sev["major"]["rd"] < sev["decisive"]["rd"]
    print(f"  interaction RD(decisive) - RD(minor) = {inter:+.3f}")
    print(f"  band RDs ordered minor<major<decisive: {ordered}")
    c1_slope = sev["decisive"]["p_c1"] - sev["minor"]["p_c1"]
    c2_slope = sev["decisive"]["p_c2"] - sev["minor"]["p_c2"]
    print(f"  C1 slope {c1_slope:+.3f}   C2 slope {c2_slope:+.3f}")
    print("  VERDICT: still not supported" if not ordered or abs(inter) < 0.10
          else "  VERDICT: CHANGED — re-read EXPLORATORY.md criteria against these")
    out["severity_detected_self"] = {"bands": sev, "interaction": inter,
                                     "ordered": bool(ordered),
                                     "c1_slope": c1_slope, "c2_slope": c2_slope}

    # --- 2. the pre-registered GLMM ---------------------------------------
    print("\n=== 2. GLMM (PREREGISTRATION.md §2, never fitted) ===")
    try:
        import pandas as pd
        import statsmodels.formula.api as smf
        rows = [{"detected": int(h), "condition": c, "variant": v, "position": pid}
                for (c, v, pid, _), h in ds.items() if c in ("C1", "C2")]
        df = pd.DataFrame(rows)
        # model and format terms are unusable (one model, one format); position and
        # prompt_variant are estimable. Fitted as a binomial GEE clustered on position,
        # with prompt_variant as a fixed effect — statsmodels has no crossed-RE binomial.
        m = smf.gee("detected ~ C(condition) + C(variant)", "position", data=df,
                    family=__import__("statsmodels.api", fromlist=["families"]).families.Binomial(),
                    cov_struct=__import__("statsmodels.api", fromlist=["cov_struct"]).cov_struct.Exchangeable())
        fit = m.fit()
        print(fit.summary().tables[1])
        out["glmm"] = {"params": {k: float(v) for k, v in fit.params.items()},
                       "pvalues": {k: float(v) for k, v in fit.pvalues.items()},
                       "note": ("binomial GEE clustered on position; crossed random effects "
                                "are not available for binomial outcomes in statsmodels, so "
                                "prompt_variant enters as a fixed effect. Model and format "
                                "terms are unusable with one model and one format.")}
    except Exception as exc:                                     # noqa: BLE001
        print(f"  GLMM not fitted: {type(exc).__name__}: {exc}")
        out["glmm"] = {"error": str(exc)[:300]}

    # --- 3. margin sensitivity --------------------------------------------
    print("\n=== 3. Margin sensitivity (replaces defending a bare ±0.10) ===")
    print(f"    detected_self RD {rd:+.4f}, 90% CI [{ci90[0]:+.3f}, {ci90[1]:+.3f}]")
    curve = {}
    for m in (0.02, 0.03, 0.05, 0.075, 0.10, 0.15, 0.20):
        fires = bool(-m < ci90[0] and ci90[1] < m)
        curve[m] = fires
        print(f"  margin ±{m:<5} equivalence {'FIRES' if fires else 'does not fire'}")
    smallest = min((m for m, f in curve.items() if f), default=None)
    print(f"  smallest margin at which equivalence holds: ±{smallest}")
    out["margin_curve"] = {"rd": rd, "ci90": ci90, "curve": {str(k): v for k, v in curve.items()},
                           "smallest_margin": smallest}

    # --- 4. paraphrase pairings on detected_self ---------------------------
    print("\n=== 4. Paraphrase pairings on detected_self ===")
    m1 = {v: float(np.mean(list(per_position(ds, "C1", v).values()))) for v in "abc"}
    m2 = {v: float(np.mean(list(per_position(ds, "C2", v).values()))) for v in "abc"}
    best = max(m2, key=m2.get)
    print(f"  C1 {  {k: round(x,3) for k,x in m1.items()} }")
    print(f"  C2 {  {k: round(x,3) for k,x in m2.items()} }   best C2 = C2.{best} ({m2[best]:.3f})")
    pair = {}
    for v in "abc":
        r, c95, _, _ = rd_ci(per_position(ds, "C1", v), per_position(ds, "C2", best), rng, boot=4000)
        pair[f"C1.{v}"] = {"p": m1[v], "rd": r, "ci95": c95}
        print(f"  C1.{v} vs C2.{best}:  RD {r:+.3f}  95% [{c95[0]:+.3f}, {c95[1]:+.3f}]")
    spread = max(max(m1.values()) - min(m1.values()), max(m2.values()) - min(m2.values()))
    print(f"  within-arm spread {spread:.3f} vs between-arm |RD| {abs(rd):.3f}  "
          f"= {spread/abs(rd):.0f}x")
    out["pairings"] = {"c1": m1, "c2": m2, "best_c2": f"C2.{best}", "rows": pair,
                       "within_spread": spread, "ratio": spread / abs(rd)}

    # --- 5. configuration table -------------------------------------------
    print("\n=== 5. Configuration table (recovered from the run records) ===")
    recs = [json.loads(l) for l in
            (HERE / "data" / "full_raw.jsonl").read_text().splitlines() if l.strip()]
    cfg = {
        "model": sorted({r["model"] for r in recs}),
        "position_format": sorted({r["format"] for r in recs}),
        "system_prompt": recs[0]["system_prompt"],
        "temperature": "1.0 (API default; not set explicitly)",
        "extended_thinking": "disabled",
        "tools / hooks / MCP / project context": "none",
        "calls": len(recs),
        "errors": sum(1 for r in recs if r.get("is_error")),
        "cost_usd": round(sum(r.get("cost_usd") or 0 for r in recs), 2),
        "mean_wall_s_per_call": round(float(np.mean([r["wall_s"] for r in recs
                                                     if r.get("wall_s")])), 2),
        "retry_logic": "none; the runner records is_error and does not retry",
        "engine": sorted({p["engine"] for p in pos.values()}),
        "engine_depth": sorted({p["label_depth"] for p in pos.values()}),
        "generator_seed": sorted({p["seed"] for p in pos.values()}),
    }
    for k, v in cfg.items():
        print(f"  {k:<38} {v if not isinstance(v, str) or len(v) < 60 else v[:57] + '...'}")
    out["config"] = cfg

    (HERE / "data" / "final_analyses.json").write_text(
        json.dumps(out, indent=2, default=float) + "\n")
    print("\nwritten to data/final_analyses.json")


if __name__ == "__main__":
    main()
