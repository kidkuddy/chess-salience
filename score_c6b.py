"""C6b analysis, exactly as C6B-PREREG.md §3-§4 specifies it."""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path
import numpy as np
import pilot_report as P

HERE = Path(__file__).parent
BOOT, SEED = 10_000, 20260813
MIN_PARSE, MIN_SUBSET = 0.98, 0.90
R_ELICITATION, R_REASONING = 0.40, 0.15
C2_STANDALONE = 0.536

def rate_ci(pp, rng):
    ids = sorted(pp); arr = np.array([pp[i] for i in ids])
    b = arr[rng.integers(0, len(arr), size=(BOOT, len(arr)))].mean(axis=1)
    return {"n_positions": len(ids), "rate": float(arr.mean()),
            "ci95": [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]}

rows = [json.loads(l) for l in (HERE/"data"/"c6b_raw.jsonl").read_text().splitlines() if l.strip()]
ok = [r for r in rows if not r.get("is_error")]
rng = np.random.default_rng(SEED)
rep = {"n": len(rows)}

print("--- C6B-PREREG.md §3 validity ---")
parse = float(np.mean([r["parsed"] for r in ok]))
subset = float(np.mean([r["subset_of_turn2"] for r in ok]))
resume = len(ok)/len(rows)
gates = {"resume": (resume, 0.98), "parse": (parse, MIN_PARSE), "subset": (subset, MIN_SUBSET)}
bad = [k for k,(v,t) in gates.items() if v < t]
for k,(v,t) in gates.items():
    print(f"  {'PASS' if v>=t else 'FAIL'}  {k:<8} {v:.4f}  (threshold {t})")
rep["validity"] = {k: v for k,(v,_) in gates.items()}

turn1 = {}
for r in (json.loads(l) for l in (HERE/"data"/"extract_raw.jsonl").read_text().splitlines() if l.strip()):
    if r.get("condition")=="C1" and r.get("variant")=="a" and r.get("extract_repeat")==0:
        turn1[(r["position_id"], r["repeat"])] = bool(r["detected_self"])

if bad:
    print(f"\n§4: failed {bad}. Final attempt — attribution reported as UNRESOLVED.")
    rep["verdict"] = f"INVALID — {bad}"
else:
    miss, hit = defaultdict(list), defaultdict(list)
    for r in ok:
        k = (r["position_id"], r["repeat"])
        if k in turn1:
            (miss if not turn1[k] else hit)[r["position_id"]].append(bool(r["detected_self"]))
    R = rate_ci({p: float(np.mean(v)) for p,v in miss.items()}, rng)
    H = rate_ci({p: float(np.mean(v)) for p,v in hit.items()}, rng)
    rep["R"], rep["persist_given_hit"] = R, H
    ncalls = sum(len(v) for v in miss.values())
    print(f"\n--- §3 attribution ---")
    print(f"  R = P(turn2 detects | turn1 MISSED)   = {R['rate']:.3f}  "
          f"95% [{R['ci95'][0]:.3f}, {R['ci95'][1]:.3f}]   "
          f"({R['n_positions']} positions, {ncalls} calls)")
    print(f"  P(turn2 detects | turn1 DETECTED)     = {H['rate']:.3f}   (confound bound 1)")
    print(f"  C2 standalone reference               = {C2_STANDALONE:.3f}   (confound bound 2)")
    if R["rate"] >= R_ELICITATION:
        v = "ELICITATION-DOMINANT — the model largely had the threat and did not volunteer it."
    elif R["rate"] <= R_REASONING:
        v = "REASONING-DOMINANT — the model largely did not have the threat."
    else:
        v = "MIXED — both mechanisms contribute; attribute nothing further."
    rep["verdict"] = v
    print(f"\n  branch: {v}")
    if R["rate"] > C2_STANDALONE:
        print("  NOTE: R exceeds C2 standalone — turn-1 context helped beyond being asked,")
        print("        so the elicitation reading weakens accordingly.")
(HERE/"data"/"c6b_report.json").write_text(json.dumps(rep, indent=2, default=float)+"\n")
print("\nwritten to data/c6b_report.json")
