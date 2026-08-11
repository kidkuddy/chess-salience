"""Analysis of the extraction retrofit, exactly as RETROFIT-PREREG.md §4-§6 specifies it.

Frozen and committed before any extraction call was made. It chooses no metric and no
threshold: everything it applies is quoted from the pre-registration.

  python score_extract.py
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

import pilot_report as P
from score_labels import kappa, probe_semantic

HERE = Path(__file__).parent
BOOT = 10_000
SEED = 20260811
MARGIN = P.TOST_MARGIN                  # ±0.10

# RETROFIT-PREREG.md §4
MIN_SUBSET_RATE = 0.90
MIN_PARSE_RATE = 0.98
MIN_RESUME_RATE = 0.98


def paired_rd(r1: dict, r2: dict, rng):
    ids = sorted(set(r1) & set(r2))
    d = {i: r2[i] - r1[i] for i in ids}
    b = P.cluster_bootstrap(d, ids, rng, n_boot=BOOT)
    return {"n_positions": len(ids),
            "p_c1": float(np.mean([r1[i] for i in ids])),
            "p_c2": float(np.mean([r2[i] for i in ids])),
            "rd": float(np.mean(list(d.values()))),
            "ci90": [float(np.percentile(b, 5)), float(np.percentile(b, 95))],
            "ci95": [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]}


def by_position(rows, pick):
    out = defaultdict(lambda: defaultdict(list))
    for r in rows:
        out[r["condition"]][r["position_id"]].append(bool(pick(r)))
    return {c: {p: float(np.mean(v)) for p, v in d.items()} for c, d in out.items()}


def fmt(r, label):
    return (f"{label:<30} C1={r['p_c1']:.3f}  C2={r['p_c2']:.3f}  RD={r['rd']:+.3f}  "
            f"90% [{r['ci90'][0]:+.3f}, {r['ci90'][1]:+.3f}]  "
            f"95% [{r['ci95'][0]:+.3f}, {r['ci95'][1]:+.3f}]")


def permutation_null(rows, positions, rng, reps=200):
    """RETROFIT-PREREG.md §5, chance correction computed on the FLAGGED sets."""
    pids = sorted(positions)
    accept = {p: {s.lower() for s in positions[p]["accept_squares"]} for p in pids}
    out = defaultdict(lambda: defaultdict(list))
    for r in rows:
        said = set(r["flagged_squares"])
        others = [p for p in pids if p != r["position_id"]]
        draws = rng.choice(len(others), size=reps)
        out[r["condition"]][r["position_id"]].append(
            float(np.mean([bool(accept[others[d]] & said) for d in draws])))
    return {c: {p: float(np.mean(v)) for p, v in d.items()} for c, d in out.items()}


def corrected(obs, chance):
    return (obs - chance) / (1 - chance) if chance < 1 else float("nan")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extract", default=str(HERE / "data" / "extract_raw.jsonl"))
    ap.add_argument("--raw", default=str(HERE / "data" / "full_raw.jsonl"))
    ap.add_argument("--positions", default=str(HERE / "data" / "full_positions.jsonl"))
    ap.add_argument("--json", default=str(HERE / "data" / "extract_report.json"))
    ap.add_argument("--labels", default=None, help="human labels, if LABELLING.md was run")
    args = ap.parse_args()

    recs, positions = P.load(Path(args.raw), Path(args.positions))
    orig = {(r["position_id"], r["condition"], r["variant"], r["repeat"]): r for r in recs}
    rows = [json.loads(l) for l in Path(args.extract).read_text().splitlines() if l.strip()]

    rng = np.random.default_rng(SEED)
    report = {}

    # --- §4 validity checks, before looking at the primary -----------------
    attempted = len(rows)
    errored = [r for r in rows if r.get("is_error")]
    ok = [r for r in rows if not r.get("is_error")]
    first = [r for r in ok if r["extract_repeat"] == 0]

    resume_rate = 1 - len(errored) / attempted if attempted else 0.0
    parse_rate = float(np.mean([r["parsed"] for r in ok])) if ok else 0.0
    subset_rate = float(np.mean([r["subset_of_turn1"] for r in ok])) if ok else 0.0

    checks = {
        "resume_rate": (resume_rate, MIN_RESUME_RATE),
        "parse_rate": (parse_rate, MIN_PARSE_RATE),
        "subset_rate": (subset_rate, MIN_SUBSET_RATE),
    }
    print("--- RETROFIT-PREREG.md §4 validity checks ---")
    failed = []
    for name, (val, thr) in checks.items():
        flag = "PASS" if val >= thr else "FAIL"
        if val < thr:
            failed.append(name)
        print(f"  {flag}  {name:<14} {val:.4f}  (threshold {thr})")
    report["validity"] = {k: {"value": v, "threshold": t} for k, (v, t) in checks.items()}

    # stability on the 3x subsample
    grp = defaultdict(list)
    for r in ok:
        grp[r["session_id"]].append(r["detected_self"])
    multi = [v for v in grp.values() if len(v) > 1]
    if multi:
        stable = float(np.mean([len(set(v)) == 1 for v in multi]))
        report["extraction_stability"] = {"n_sessions": len(multi), "all_agree": stable}
        print(f"  ----  stability      {stable:.4f}  ({len(multi)} sessions × 3)")

    nflag = {c: float(np.mean([r["n_flagged"] for r in first if r["condition"] == c]))
             for c in ("C1", "C2")}
    report["flagged_count"] = nflag
    print(f"  ----  squares flagged per answer: C1 {nflag['C1']:.2f}  C2 {nflag['C2']:.2f}")

    if failed:
        print(f"\nRETROFIT-PREREG.md §6 branch 1: {', '.join(failed)} below threshold. "
              f"The retrofit is reported as attempted and invalid; the metric question "
              f"returns to LABELLING.md. Not reporting a primary estimate.")
        report["verdict"] = f"INVALID — failed {failed}"
        Path(args.json).write_text(json.dumps(report, indent=2, default=float) + "\n")
        return

    # --- §5 primary --------------------------------------------------------
    r = by_position(first, lambda x: x["detected_self"])
    primary = paired_rd(r["C1"], r["C2"], rng)
    report["primary_detected_self"] = primary
    print("\n--- primary: detected_self ---")
    print(fmt(primary, "self-reported detection"))

    lo, hi = primary["ci95"]
    if lo > MARGIN:
        v = ("branch 2 — the advisory arm detects materially less often on a metric that "
             "excludes transcription. The pre-registered null was a metric artifact.")
    elif -MARGIN < lo and hi < MARGIN:
        v = ("branch 3 — equivalence survives on the clean metric. The paper's conclusion "
             "is stronger than it is today.")
    else:
        v = "branch 4 — inconclusive. Report the interval and the metric-sensitivity range."
    report["verdict"] = v
    print(f"\nRETROFIT-PREREG.md §6 {v}")

    # --- chance correction on the flagged sets -----------------------------
    null = permutation_null(first, positions, rng)
    ids = sorted(set(r["C1"]) & set(r["C2"]))
    c1c = corrected(np.mean([r["C1"][i] for i in ids]), np.mean([null["C1"][i] for i in ids]))
    c2c = corrected(np.mean([r["C2"][i] for i in ids]), np.mean([null["C2"][i] for i in ids]))
    report["chance"] = {"null_c1": float(np.mean([null["C1"][i] for i in ids])),
                        "null_c2": float(np.mean([null["C2"][i] for i in ids])),
                        "corrected_c1": float(c1c), "corrected_c2": float(c2c),
                        "corrected_rd": float(c2c - c1c)}
    print(f"\n--- chance correction on flagged sets ---")
    print(f"  permutation null   C1 {report['chance']['null_c1']:.3f}   "
          f"C2 {report['chance']['null_c2']:.3f}")
    print(f"  corrected          C1 {c1c:.3f}   C2 {c2c:.3f}   RD {c2c - c1c:+.3f}")

    # --- secondary ---------------------------------------------------------
    print("\n--- secondary ---")
    def old(x, field):
        o = orig.get((x["position_id"], x["condition"], x["variant"], x["repeat"]))
        return bool(o["score"].get(field)) if o else False

    for label, pick in (
        ("hit_square (same responses)", lambda x: old(x, "hit_square")),
        ("hit_move (same responses)", lambda x: old(x, "hit_move")),
        ("hit_square but not self", lambda x: old(x, "hit_square") and not x["detected_self"]),
    ):
        rr = by_position(first, pick)
        res = paired_rd(rr["C1"], rr["C2"], rng)
        report.setdefault("secondary", {})[label] = res
        print(fmt(res, label))

    print("\n--- per paraphrase, detected_self ---")
    for cond in ("C1", "C2"):
        for v in "abc":
            sub = [x for x in first if x["condition"] == cond and x["variant"] == v]
            if sub:
                print(f"  {cond}.{v}  {np.mean([x['detected_self'] for x in sub]):.3f}"
                      f"   (n={len(sub)})")

    # --- agreement ---------------------------------------------------------
    print("\n--- agreement against detected_self ---")
    truth = [x["detected_self"] for x in first]
    preds = {"hit_square": [old(x, "hit_square") for x in first],
             "hit_move": [old(x, "hit_move") for x in first],
             "regex probe": [probe_semantic(
                 (orig[(x["position_id"], x["condition"], x["variant"], x["repeat"])]
                  ["response"] or ""), x["critical_square"]) for x in first]}
    for name, pred in preds.items():
        tp = sum(p and t for p, t in zip(pred, truth))
        fp = sum(p and not t for p, t in zip(pred, truth))
        fn = sum((not p) and t for p, t in zip(pred, truth))
        tn = sum((not p) and (not t) for p, t in zip(pred, truth))
        report.setdefault("agreement", {})[name] = {
            "sensitivity": tp / (tp + fn) if tp + fn else None,
            "specificity": tn / (tn + fp) if tn + fp else None,
            "kappa": kappa([str(x) for x in pred], [str(x) for x in truth])}
        a = report["agreement"][name]
        print(f"  {name:<14} sens={a['sensitivity']:.3f}  spec={a['specificity']:.3f}  "
              f"kappa={a['kappa']:.3f}")

    if args.labels:
        human = json.loads(Path(args.labels).read_text())["labels"]
        keyed = {}
        for s in (1, 2, 3):
            kp = HERE / "data" / f"label_key_stage{s}.json"
            if kp.exists():
                keyed.update(json.loads(kp.read_text()))
        idx = {(x["position_id"], x["condition"], x["variant"], x["repeat"]): x
               for x in first}
        pairs = []
        for uid, lab in human.items():
            if lab == "?" or uid not in keyed:
                continue
            k = keyed[uid]
            x = idx.get((k["position_id"], k["condition"], k["variant"], k["repeat"]))
            if x:
                pairs.append((x["detected_self"], int(lab) == 2))
        if pairs:
            kp = kappa([str(a) for a, _ in pairs], [str(b) for _, b in pairs])
            report["vs_human"] = {"n": len(pairs), "kappa": kp,
                                  "agreement": float(np.mean([a == b for a, b in pairs]))}
            print(f"\n--- detected_self vs human labels, n={len(pairs)} ---")
            print(f"  agreement {report['vs_human']['agreement']:.3f}   kappa {kp:.3f}")
            print("  This is what licenses using the automatic metric in place of hand "
                  "labelling (RETROFIT-PREREG.md §5).")

    Path(args.json).write_text(json.dumps(report, indent=2, default=float) + "\n")
    print(f"\nwritten to {Path(args.json).name}")


if __name__ == "__main__":
    main()
