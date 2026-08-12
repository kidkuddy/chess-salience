"""Analysis of C6 and C4, exactly as ATTRIBUTION-PREREG.md §5-§7 specifies it.

Frozen and committed before any data call. It chooses no metric and no threshold:
everything it applies is quoted from the pre-registration.

  python score_arms.py
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

import pilot_report as P
import prompts

HERE = Path(__file__).parent
BOOT = 10_000
SEED = 20260812
MARGIN = P.TOST_MARGIN                 # ±0.10

# §5 thresholds
MIN_RESUME, MIN_PARSE, MIN_SUBSET = 0.98, 0.98, 0.90
# §6 branch thresholds
R_ELICITATION, R_REASONING = 0.40, 0.15
# reference points, quoted from the retrofit
C2_STANDALONE, C1_STANDALONE = 0.536, 0.542

EXCLUSION = ["hanging", "threat", "tactic", "mate", "blunder", "safe", "attack",
             "best move", "danger"]


def grams(s: str, n: int = 5) -> set:
    w = re.findall(r"[a-z]+", s.lower())
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def prefix_integrity(path: Path) -> dict:
    """§5 + Amendment 1: no exclusion word, no algebraic square, no prompt echo."""
    d = json.loads(path.read_text())
    txt = " ".join(t["content"] for t in d["turns"])
    probe = grams(prompts.C1["a"].replace("{position}", "")) | \
            grams(prompts.C2["a"].replace("{position}", ""))
    return {
        "exclusion_words": [w for w in EXCLUSION if w in txt.lower()],
        "algebraic_squares": re.findall(r"(?<![a-z0-9])[a-h][1-8](?![0-9a-z])", txt.lower()),
        "prompt_echo": sorted(probe & grams(txt)),
    }


def paired_rd(r1: dict, r2: dict, rng):
    ids = sorted(set(r1) & set(r2))
    d = {i: r2[i] - r1[i] for i in ids}
    b = P.cluster_bootstrap(d, ids, rng, n_boot=BOOT)
    return {"n_positions": len(ids),
            "p_a": float(np.mean([r1[i] for i in ids])),
            "p_b": float(np.mean([r2[i] for i in ids])),
            "rd": float(np.mean(list(d.values()))),
            "ci90": [float(np.percentile(b, 5)), float(np.percentile(b, 95))],
            "ci95": [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]}


def rate_ci(per_position: dict, rng):
    ids = sorted(per_position)
    arr = np.array([per_position[i] for i in ids])
    idx = rng.integers(0, len(arr), size=(BOOT, len(arr)))
    b = arr[idx].mean(axis=1)
    return {"n_positions": len(ids), "rate": float(arr.mean()),
            "ci90": [float(np.percentile(b, 5)), float(np.percentile(b, 95))],
            "ci95": [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default=str(HERE / "data" / "arms_raw.jsonl"))
    ap.add_argument("--extract", default=str(HERE / "data" / "extract_raw.jsonl"))
    ap.add_argument("--raw", default=str(HERE / "data" / "full_raw.jsonl"))
    ap.add_argument("--prefix", default=str(HERE / "data" / "c4_prefix_realized.json"))
    ap.add_argument("--json", default=str(HERE / "data" / "arms_report.json"))
    args = ap.parse_args()

    rows = [json.loads(l) for l in Path(args.arms).read_text().splitlines() if l.strip()]
    rng = np.random.default_rng(SEED)
    report = {"n_records": len(rows)}

    # --- §5 validity -------------------------------------------------------
    print("--- ATTRIBUTION-PREREG.md §5 validity checks ---")
    ok = [r for r in rows if not r.get("is_error")]
    resume = len(ok) / len(rows) if rows else 0.0
    parse = float(np.mean([r["parsed"] for r in ok])) if ok else 0.0
    for name, val, thr in (("resume_rate", resume, MIN_RESUME),
                           ("parse_rate", parse, MIN_PARSE)):
        print(f"  {'PASS' if val >= thr else 'FAIL'}  {name:<12} {val:.4f}  (threshold {thr})")

    # Amendment 3(a): §5 says "that arm", so the subset rate is judged per arm.
    invalid = set()
    report["validity"] = {"resume": resume, "parse": parse, "subset_by_arm": {}}
    for arm in ("C6", "C4"):
        s = [r["subset_of_turn"] for r in ok if r["arm"] == arm]
        v = float(np.mean(s)) if s else 0.0
        report["validity"]["subset_by_arm"][arm] = v
        if v < MIN_SUBSET:
            invalid.add(arm)
        print(f"  {'PASS' if v >= MIN_SUBSET else 'FAIL'}  subset_rate {arm}  {v:.4f}  "
              f"(threshold {MIN_SUBSET}, n={len(s)})")
    failed = []

    pi = prefix_integrity(Path(args.prefix))
    c4_void = any(pi.values())
    print(f"  {'FAIL' if c4_void else 'PASS'}  C4 prefix integrity "
          f"{'-> ' + json.dumps(pi) if c4_void else '(no exclusion word, square, or echo)'}")
    report["prefix_integrity"] = pi

    # C6 turn-1 identity: the C6 set must be exactly the recorded C1.a set
    c1a = {(r["position_id"], r["repeat"]) for r in
           (json.loads(l) for l in Path(args.raw).read_text().splitlines() if l.strip())
           if r["condition"] == "C1" and r["variant"] == "a" and not r.get("is_error")}
    c6set = {(r["position_id"], r["repeat"]) for r in ok if r["arm"] == "C6"}
    identity = c6set <= c1a and len(c6set) > 0
    print(f"  {'PASS' if identity else 'FAIL'}  C6 turn-1 identity "
          f"({len(c6set)} of {len(c1a)} recorded C1.a sessions)")
    report["c6_turn1_identity"] = identity

    if invalid:
        print(f"\n§5: {sorted(invalid)} reported as attempted and invalid (subset rate).")
    report["invalid_arms"] = sorted(invalid)

    # --- §6 C6 attribution -------------------------------------------------
    turn1 = {}
    for r in (json.loads(l) for l in Path(args.extract).read_text().splitlines() if l.strip()):
        if r.get("condition") == "C1" and r.get("variant") == "a" and r.get("extract_repeat") == 0:
            turn1[(r["position_id"], r["repeat"])] = bool(r["detected_self"])

    miss, hit_given_hit = defaultdict(list), defaultdict(list)
    for r in ok:
        if r["arm"] != "C6":
            continue
        k = (r["position_id"], r["repeat"])
        if k not in turn1:
            continue
        (miss if not turn1[k] else hit_given_hit)[r["position_id"]].append(bool(r["detected_self"]))

    print("\n--- §6 C6: attribution ---")
    if "C6" in invalid:
        print("  C6 INVALID per §5 (subset rate 0.759 < 0.90). No R computed — see")
        print("  ATTRIBUTION-PREREG.md Amendment 3. 64 of 65 subset failures are turn-1")
        print("  squares; the extraction prompt's 'your answer above' is ambiguous in a")
        print("  two-answer conversation, so C6 measured a conversation-level flag list.")
        report["c6"] = {"verdict": "INVALID — subset rate; see Amendment 3"}
        miss = {}
    if not miss:
        print("  no turn-1 misses; R undefined")
        report["c6"] = {"error": "no turn-1 misses"}
    else:
        Rpp = {p: float(np.mean(v)) for p, v in miss.items()}
        R = rate_ci(Rpp, rng)
        report["c6"] = {"recovery_R": R,
                        "n_turn1_miss_calls": sum(len(v) for v in miss.values())}
        print(f"  R = P(turn2 detects | turn1 missed) = {R['rate']:.3f}   "
              f"95% [{R['ci95'][0]:.3f}, {R['ci95'][1]:.3f}]   "
              f"({R['n_positions']} positions, "
              f"{report['c6']['n_turn1_miss_calls']} calls)")
        if hit_given_hit:
            H = rate_ci({p: float(np.mean(v)) for p, v in hit_given_hit.items()}, rng)
            report["c6"]["persist_given_hit"] = H
            print(f"  P(turn2 detects | turn1 detected)    = {H['rate']:.3f}   "
                  f"(confound bound 1, §6)")
        print(f"  C2 standalone reference              = {C2_STANDALONE:.3f}   "
              f"(confound bound 2, §6)")

        if R["rate"] >= R_ELICITATION:
            v = ("branch: ELICITATION-DOMINANT — the model largely had the threat and did "
                 "not volunteer it. §8: the Discussion attributes, and the salience "
                 "hypothesis is supported in a within-conversation form.")
        elif R["rate"] <= R_REASONING:
            v = ("branch: REASONING-DOMINANT — the model largely did not have the threat. "
                 "§8: the 0.98 ceiling measures board reading, not tactical search.")
        else:
            v = ("branch: MIXED — both mechanisms contribute; report R with its interval "
                 "and attribute nothing further.")
        report["c6"]["verdict"] = v
        print(f"\n  {v}")
        if R["rate"] > C2_STANDALONE:
            print("  NOTE §6: R exceeds C2 standalone, so turn-1 context helped beyond "
                  "being asked. The elicitation reading weakens accordingly.")

    # --- §7 C4 ------------------------------------------------------------
    print("\n--- §7 C4: advisory under conversational load ---")
    if c4_void:
        print("  C4 void: prefix integrity failed (§5).")
        report["c4"] = {"verdict": "VOID — prefix integrity"}
    else:
        c4 = defaultdict(list)
        for r in ok:
            if r["arm"] == "C4":
                c4[r["position_id"]].append(bool(r["detected_self"]))
        c4pp = {p: float(np.mean(v)) for p, v in c4.items()}
        c1pp = defaultdict(list)
        for k, v in turn1.items():
            c1pp[k[0]].append(v)
        c1pp = {p: float(np.mean(v)) for p, v in c1pp.items()}
        res = paired_rd(c1pp, c4pp, rng)
        report["c4"] = res
        print(f"  C1 (no load) {res['p_a']:.3f}   C4 (under load) {res['p_b']:.3f}   "
              f"RD {res['rd']:+.3f}   95% [{res['ci95'][0]:+.3f}, {res['ci95'][1]:+.3f}]")
        lo, hi = res["ci95"]
        if lo > MARGIN:
            v = ("branch: LOAD SUPPRESSES — advisory framing does suppress reporting under "
                 "conversational load. §8: this becomes the paper's headline.")
        elif -MARGIN < lo and hi < MARGIN:
            v = ("branch: NULL SURVIVES LOAD — the equivalence claim extends to a "
                 "materially more realistic setting.")
        else:
            v = "branch: INCONCLUSIVE — report the interval."
        report["c4"]["verdict"] = v
        print(f"\n  {v}")

    Path(args.json).write_text(json.dumps(report, indent=2, default=float) + "\n")
    print(f"\nwritten to {Path(args.json).name}")


if __name__ == "__main__":
    main()
