"""Unblind the hand labels and run the analysis fixed in LABELLING.md §5 and §7.

  python score_labels.py --stages 1
  python score_labels.py --stages 1 2 --rater2 data/labels_stage1_rater2.json

Reads data/labels_stage<N>.json (exported from label_ui.html) and the sealed
data/label_key_stage<N>.json. Everything it prints is specified in advance in
LABELLING.md; this script chooses no metric and no threshold.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

import pilot_report as P

HERE = Path(__file__).parent
BOOT = 10_000
SEED = 20260811
MARGIN = P.TOST_MARGIN          # ±0.10, reused from the pre-registration for continuity

# The regex probe from LABELLING.md §6. Committed here only so that it can be validated
# against the human labels. It is not a metric and its estimate is not reported as one.
THREAT = re.compile(
    r"\b(hang|loose|undefended|unprotected|en prise|attack|threat|win|lose|losing|lost|"
    r"mate|captur|take|fork|pin|skewer|defend|defenc|defens|drop|danger|weak|target|"
    r"blunder|tactic|sacrifi|trap|discover)\w*", re.I)
FENISH = re.compile(r"[rnbqkpRNBQKP1-8]{2,}/[rnbqkpRNBQKP1-8/]+")


def probe_semantic(response: str, square: str) -> bool:
    """Critical square named within ±90 chars of threat language, outside a literal FEN."""
    spans = [(m.start(), m.end()) for m in FENISH.finditer(response)]
    for m in re.finditer(r"(?<![a-zA-Z0-9])" + square + r"(?![0-9a-zA-Z])", response, re.I):
        if any(a <= m.start() < b for a, b in spans):
            continue
        if THREAT.search(response[max(0, m.start() - 90): m.end() + 90]):
            return True
    return False


def kappa(a: list, b: list) -> float:
    """Cohen's kappa on paired categorical judgements."""
    cats = sorted(set(a) | set(b))
    n = len(a)
    obs = sum(x == y for x, y in zip(a, b)) / n
    exp = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return (obs - exp) / (1 - exp) if exp < 1 else 1.0


def paired_rd(rates_c1: dict, rates_c2: dict, rng):
    ids = sorted(set(rates_c1) & set(rates_c2))
    d = {i: rates_c2[i] - rates_c1[i] for i in ids}
    b = P.cluster_bootstrap(d, ids, rng, n_boot=BOOT)
    return {
        "n_positions": len(ids),
        "p_c1": float(np.mean([rates_c1[i] for i in ids])),
        "p_c2": float(np.mean([rates_c2[i] for i in ids])),
        "rd": float(np.mean(list(d.values()))),
        "ci90": [float(np.percentile(b, 5)), float(np.percentile(b, 95))],
        "ci95": [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))],
    }


def rates_by_position(items, pick):
    out = defaultdict(lambda: defaultdict(list))
    for it in items:
        out[it["condition"]][it["position_id"]].append(bool(pick(it)))
    return {c: {p: float(np.mean(v)) for p, v in d.items()} for c, d in out.items()}


def fmt(r, label):
    return (f"{label:<26} C1={r['p_c1']:.3f}  C2={r['p_c2']:.3f}  "
            f"RD={r['rd']:+.3f}  90% [{r['ci90'][0]:+.3f}, {r['ci90'][1]:+.3f}]  "
            f"95% [{r['ci95'][0]:+.3f}, {r['ci95'][1]:+.3f}]")


def verdict(r) -> str:
    lo, hi = r["ci95"]
    if lo > MARGIN:
        return ("STOP — advisory detects materially less often than direct. "
                "The 95% CI clears the +0.10 margin. LABELLING.md §8: the paper inverts.")
    if -MARGIN < lo and hi < MARGIN:
        return ("STOP — equivalence holds on the validated metric. "
                "LABELLING.md §8: the paper keeps its conclusion.")
    return ("CONTINUE to the next stage. If this was stage 3, stop and report the "
            "interval as inconclusive (LABELLING.md §8, third case).")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", type=int, nargs="+", required=True)
    ap.add_argument("--rater2", default=None, help="second rater's export, for kappa")
    ap.add_argument("--raw", default=str(HERE / "data" / "full_raw.jsonl"))
    ap.add_argument("--positions", default=str(HERE / "data" / "full_positions.jsonl"))
    ap.add_argument("--json", default=str(HERE / "data" / "label_report.json"))
    args = ap.parse_args()

    recs, pos = P.load(Path(args.raw), Path(args.positions))
    by_id = {(r["position_id"], r["condition"], r["variant"], r["repeat"]): r
             for r in recs if r["condition"] in ("C1", "C2")}

    items, unsure, missing = [], 0, 0
    for s in args.stages:
        labels = json.loads((HERE / "data" / f"labels_stage{s}.json").read_text())["labels"]
        key = json.loads((HERE / "data" / f"label_key_stage{s}.json").read_text())
        tasks = {t["uid"]: t for t in
                 json.loads((HERE / "data" / f"label_tasks_stage{s}.json").read_text())}
        for uid, lab in labels.items():
            if lab == "?":
                unsure += 1
                continue
            k = key[uid]
            rec = by_id.get((k["position_id"], k["condition"], k["variant"], k["repeat"]))
            if rec is None:
                missing += 1
                continue
            items.append({
                "uid": uid, "stage": s, "label": int(lab), **k,
                "probe": probe_semantic(rec["response"] or "",
                                        pos[k["position_id"]]["critical_square"]),
            })

    if not items:
        raise SystemExit("no usable labels found")
    print(f"{len(items)} labels over stage(s) {args.stages}"
          + (f"; {unsure} unresolved '?' dropped" if unsure else "")
          + (f"; {missing} unmatched" if missing else ""))
    if unsure:
        print("  NOTE: LABELLING.md §2 requires every '?' to be resolved by the second "
              "rater before analysis. These are dropped and counted, not guessed.")

    rng = np.random.default_rng(SEED)
    report = {"stages": args.stages, "n_labels": len(items), "n_unsure_dropped": unsure}

    # --- primary, LABELLING.md §7 -----------------------------------------
    r = rates_by_position(items, lambda it: it["label"] == 2)
    primary = paired_rd(r["C1"], r["C2"], rng)
    report["primary_detected"] = primary
    print("\n--- primary: label == 2 (detected) ---")
    print(fmt(primary, "human detected"))
    print("\n" + verdict(primary))
    report["verdict"] = verdict(primary)

    # --- secondary --------------------------------------------------------
    print("\n--- secondary ---")
    for label, pick in (
        ("named at all (1 or 2)", lambda it: it["label"] >= 1),
        ("named only (== 1)", lambda it: it["label"] == 1),
        ("scorer hit_square", lambda it: it["hit_square"]),
        ("scorer hit_move", lambda it: it["hit_move"]),
        ("regex probe", lambda it: it["probe"]),
    ):
        rr = rates_by_position(items, pick)
        res = paired_rd(rr["C1"], rr["C2"], rng)
        report.setdefault("secondary", {})[label] = res
        print(fmt(res, label))

    print("\n--- per paraphrase, human detected ---")
    for cond in ("C1", "C2"):
        for v in "abc":
            sub = [it for it in items if it["condition"] == cond and it["variant"] == v]
            if sub:
                p = float(np.mean([it["label"] == 2 for it in sub]))
                print(f"  {cond}.{v}  {p:.3f}   (n={len(sub)})")

    # --- metric validation, LABELLING.md §7 -------------------------------
    print("\n--- metric validation against the human label ---")
    truth = [it["label"] == 2 for it in items]
    for name, pred in (("hit_square", [it["hit_square"] for it in items]),
                       ("hit_move", [it["hit_move"] for it in items]),
                       ("regex probe", [it["probe"] for it in items])):
        tp = sum(p and t for p, t in zip(pred, truth))
        fp = sum(p and not t for p, t in zip(pred, truth))
        fn = sum((not p) and t for p, t in zip(pred, truth))
        tn = sum((not p) and (not t) for p, t in zip(pred, truth))
        sens = tp / (tp + fn) if tp + fn else float("nan")
        spec = tn / (tn + fp) if tn + fp else float("nan")
        k = kappa([str(x) for x in pred], [str(x) for x in truth])
        report.setdefault("validation", {})[name] = {
            "sensitivity": sens, "specificity": spec, "kappa": k,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn}
        print(f"  {name:<12} sens={sens:.3f}  spec={spec:.3f}  kappa={k:.3f}   "
              f"(tp {tp}, fp {fp}, fn {fn}, tn {tn})")

    # --- inter-rater, LABELLING.md §5 -------------------------------------
    if args.rater2:
        second = json.loads(Path(args.rater2).read_text())["labels"]
        first = {it["uid"]: str(it["label"]) for it in items}
        both = [(first[u], v) for u, v in second.items() if u in first]
        if both:
            k = kappa([a for a, _ in both], [b for _, b in both])
            agree = sum(a == b for a, b in both) / len(both)
            report["inter_rater"] = {"n": len(both), "agreement": agree, "kappa": k}
            print(f"\n--- inter-rater, n={len(both)} ---")
            print(f"  raw agreement {agree:.3f}   Cohen's kappa {k:.3f}")
            if k < 0.6:
                print("  kappa below 0.6. LABELLING.md §5: the bright lines are "
                      "insufficient and the protocol needs revision before these "
                      "labels are used. That is itself reportable.")
    else:
        print("\n(no --rater2 given; LABELLING.md §5 requires a kappa before the labels "
              "are used in the paper)")

    Path(args.json).write_text(json.dumps(report, indent=2, default=float) + "\n")
    print(f"\nwritten to {Path(args.json).name}")


if __name__ == "__main__":
    main()
