"""JUDGE-PREREG.md §4-§9, frozen before the run.

Validity gates first; if any fails, no agreement estimate is printed and the script says
so. Then the primary kappa and its §6 branch, then the secondaries.

  python score_judge.py
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np

import pilot_report as P
from score_labels import kappa

HERE = Path(__file__).parent
BOOT, SEED = 10_000, 20260813
MIN_PARSE, MIN_STABILITY = 0.98, 0.80
K_LICENSED, K_MODERATE = 0.60, 0.40


def load_judge() -> tuple[dict, dict]:
    """({key: label} for judge_repeat 0, {key: [labels]} for the stability subsample)."""
    first, allreps = {}, defaultdict(dict)
    for r in (json.loads(l) for l in
              (HERE / "data" / "judge_raw.jsonl").read_text().splitlines() if l.strip()):
        if r.get("is_error") or not r.get("parsed"):
            continue
        k = (r["position_id"], r["condition"], r["variant"], r["repeat"])
        allreps[k][r["judge_repeat"]] = r["judge_label"]
        if r["judge_repeat"] == 0:
            first[k] = r["judge_label"]
    return first, {k: v for k, v in allreps.items() if len(v) == 3}


def load_v1() -> dict:
    """{key: (hit_square, hit_move, response)} from the original run."""
    out = {}
    for r in (json.loads(l) for l in
              (HERE / "data" / "full_raw.jsonl").read_text().splitlines() if l.strip()):
        if r.get("is_error") or r["condition"] not in ("C1", "C2"):
            continue
        s = r["score"]
        out[(r["position_id"], r["condition"], r["variant"], r["repeat"])] = (
            bool(s["hit_square"]), bool(s["hit_move"]), r["response"])
    return out


def load_self() -> dict:
    out = {}
    for r in (json.loads(l) for l in
              (HERE / "data" / "extract_raw.jsonl").read_text().splitlines() if l.strip()):
        if r.get("is_error") or r.get("extract_repeat") != 0:
            continue
        out[(r["position_id"], r["condition"], r["variant"], r["repeat"])] = \
            bool(r["detected_self"])
    return out


def agree(pred: list, truth: list) -> dict:
    tp = sum(1 for p, t in zip(pred, truth) if p and t)
    fp = sum(1 for p, t in zip(pred, truth) if p and not t)
    fn = sum(1 for p, t in zip(pred, truth) if not p and t)
    tn = sum(1 for p, t in zip(pred, truth) if not p and not t)
    return {"n": len(pred),
            "sensitivity": tp / (tp + fn) if tp + fn else None,
            "specificity": tn / (tn + fp) if tn + fp else None,
            "kappa": kappa([str(x) for x in pred], [str(x) for x in truth]),
            "agreement": (tp + tn) / len(pred) if pred else None}


def main() -> None:
    rng = np.random.default_rng(SEED)
    first, reps = load_judge()
    v1, slf = load_v1(), load_self()
    raw = [json.loads(l) for l in
           (HERE / "data" / "judge_raw.jsonl").read_text().splitlines() if l.strip()]
    rep = {"n_records": len(raw), "n_judged": len(first)}

    # --- §4 validity ------------------------------------------------------
    print("=== JUDGE-PREREG.md §4 validity ===")
    parse = float(np.mean([bool(r.get("parsed")) for r in raw]))
    stability = (float(np.mean([len(set(v.values())) == 1 for v in reps.values()]))
                 if reps else 0.0)
    gates = {"parse": (parse, MIN_PARSE), "stability": (stability, MIN_STABILITY)}
    for k, (v, t) in gates.items():
        print(f"  {'PASS' if v >= t else 'FAIL'}  {k:<10} {v:.4f}  (threshold {t})")
    print(f"  (stability computed on {len(reps)} thrice-judged responses)")
    rep["validity"] = {k: v for k, (v, _) in gates.items()}
    bad = [k for k, (v, t) in gates.items() if v < t]
    if bad:
        print(f"\n§4: failed {bad}. No agreement estimate. detected_self stands on its "
              f"internal checks alone and JUDGE-PREREG.md §7 is stated more strongly.")
        rep["verdict"] = f"INVALID — {bad}"
        (HERE / "data" / "judge_report.json").write_text(json.dumps(rep, indent=2,
                                                                    default=float) + "\n")
        return

    keys = sorted(set(first) & set(slf) & set(v1))
    judged2 = [first[k] == "2" for k in keys]

    # --- §5 primary -------------------------------------------------------
    print(f"\n=== §5 primary: detected_self vs judge, n={len(keys)} ===")
    a = agree([slf[k] for k in keys], judged2)
    rep["primary"] = a
    print(f"  kappa {a['kappa']:.3f}   agreement {a['agreement']:.3f}   "
          f"sens {a['sensitivity']:.3f}  spec {a['specificity']:.3f}")
    if a["kappa"] >= K_LICENSED:
        v = "LICENSED — the level claims stand as stated, with §7 as their caveat."
    elif a["kappa"] >= K_MODERATE:
        v = ("MODERATE — level claims reported with the judge rate beside them; the two "
             "instruments disagree on which responses count.")
    else:
        v = ("NOT LICENSED — level claims come out, human labelling returns as the only "
             "route, per §6.")
    rep["verdict"] = v
    print(f"  branch: {v}")

    # --- §9 secondary: every metric against the judge ---------------------
    print("\n=== §9 metrics against the judge as reference ===")
    rep["metrics"] = {}
    for name, pred in (("detected_self", [slf[k] for k in keys]),
                       ("hit_square", [v1[k][0] for k in keys]),
                       ("hit_move", [v1[k][1] for k in keys])):
        m = agree(pred, judged2)
        rep["metrics"][name] = m
        print(f"  {name:<14} sens={m['sensitivity']:.3f}  spec={m['specificity']:.3f}  "
              f"kappa={m['kappa']:.3f}")

    # --- §9 secondary: the primary RD recomputed on the judge label -------
    print("\n=== §9 primary risk difference, third operationalisation ===")
    g = {"C1": defaultdict(list), "C2": defaultdict(list)}
    for k in keys:
        g[k[1]][k[0]].append(first[k] == "2")
    c1 = {p: float(np.mean(v)) for p, v in g["C1"].items()}
    c2 = {p: float(np.mean(v)) for p, v in g["C2"].items()}
    ids = sorted(set(c1) & set(c2))
    d = {i: c2[i] - c1[i] for i in ids}
    boot = P.cluster_bootstrap(d, ids, rng, n_boot=BOOT)
    rd = float(np.mean(list(d.values())))
    ci95 = [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]
    ci90 = [float(np.percentile(boot, 5)), float(np.percentile(boot, 95))]
    print(f"  C1 {np.mean(list(c1.values())):.3f}   C2 {np.mean(list(c2.values())):.3f}")
    print(f"  RD {rd:+.4f}   95% [{ci95[0]:+.3f}, {ci95[1]:+.3f}]   "
          f"90% [{ci90[0]:+.3f}, {ci90[1]:+.3f}]")
    print(f"  equivalence at ±0.10: {'FIRES' if -0.10 < ci90[0] and ci90[1] < 0.10 else 'does not fire'}")
    rep["rd_judge"] = {"c1": float(np.mean(list(c1.values()))),
                       "c2": float(np.mean(list(c2.values()))),
                       "rd": rd, "ci95": ci95, "ci90": ci90, "n_positions": len(ids)}

    # --- §9 secondary: label 1 rate per arm, LABELLING.md §7 --------------
    print("\n=== §9 'named only' rate per arm (is hit_square's inflation symmetric?) ===")
    ones = {}
    for arm in ("C1", "C2"):
        sel = [k for k in keys if k[1] == arm]
        ones[arm] = {"label1": float(np.mean([first[k] == "1" for k in sel])),
                     "label2": float(np.mean([first[k] == "2" for k in sel])),
                     "label0": float(np.mean([first[k] == "0" for k in sel]))}
        print(f"  {arm}  detected {ones[arm]['label2']:.3f}   "
              f"named-only {ones[arm]['label1']:.3f}   absent {ones[arm]['label0']:.3f}")
    delta = ones["C2"]["label1"] - ones["C1"]["label1"]
    print(f"  named-only difference C2-C1: {delta:+.3f}  "
          f"({'asymmetric — §8 weakens' if abs(delta) > 0.10 else 'close to symmetric'})")
    rep["named_only"] = {"by_arm": ones, "delta": delta}

    (HERE / "data" / "judge_report.json").write_text(
        json.dumps(rep, indent=2, default=float) + "\n")
    print("\nwritten to data/judge_report.json")


if __name__ == "__main__":
    main()
