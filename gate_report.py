"""Gate verdict against PREREGISTRATION.md §1 — mean critical_square_correct, Wilson CI, parse rate.

Thresholds are the pre-registered ones, quoted here so the verdict is not hand-applied:
  PASS  mean >= 0.70 and Wilson lower >= 0.50 and parse rate >= 0.80
  FAIL  mean <  0.40  or Wilson upper <  0.50
  GREY  otherwise
"""

import json
from collections import defaultdict
from math import sqrt
from pathlib import Path

RAW = Path(__file__).parent / "data" / "gate_c3_raw.jsonl"
Z = 1.959964


def wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + Z * Z / n
    c = p + Z * Z / (2 * n)
    h = Z * sqrt(p * (1 - p) / n + Z * Z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def main() -> None:
    recs = [json.loads(l) for l in RAW.read_text().splitlines() if l.strip()]
    n = len(recs)
    crit = sum(1 for r in recs if r["score"]["critical_square_correct"])
    parsed = sum(1 for r in recs if r["score"]["parsed"])
    exact = sum(1 for r in recs if r["score"]["exact_board"])
    occ = sum(1 for r in recs if r["score"]["critical_square_occupied_correct"])
    f1 = sum(r["score"]["placement_f1"] for r in recs) / n
    sqacc = sum(r["score"]["square_accuracy"] for r in recs) / n
    cost = sum(r["cost_usd"] or 0 for r in recs)
    errs = sum(1 for r in recs if r["is_error"])

    lo, hi = wilson(crit, n)
    mean = crit / n
    parse_rate = parsed / n

    if mean < 0.40 or hi < 0.50:
        verdict = "FAIL"
    elif mean >= 0.70 and lo >= 0.50 and parse_rate >= 0.80:
        verdict = "PASS"
    else:
        verdict = "GREY"

    print(f"calls                     {n}  (errors {errs}, ${cost:.2f})")
    print(f"parse rate                {parse_rate:.3f}")
    print(f"critical_square_correct   {mean:.3f}   Wilson95 [{lo:.3f}, {hi:.3f}]")
    print(f"  occupancy only          {occ / n:.3f}")
    print(f"exact_board               {exact / n:.3f}")
    print(f"placement_f1 (mean)       {f1:.3f}")
    print(f"square_accuracy (mean)    {sqacc:.3f}")
    print(f"\nVERDICT: {verdict}")

    # Per-position consistency: 3/3 vs split vs 0/3 tells you whether misses are
    # position properties or sampling noise. A pile of splits means repeats matter.
    by_pos = defaultdict(list)
    for r in recs:
        by_pos[r["position_id"]].append(r["score"]["critical_square_correct"])
    dist = defaultdict(int)
    for hits in by_pos.values():
        dist[sum(hits)] += 1
    print("\nper-position hits out of 3:")
    for k in sorted(dist, reverse=True):
        print(f"  {k}/3  {dist[k]:2d} positions")

    # Where it fails, broken out by the factors the generator balanced.
    for field in ("severity_band", "motif", "phase"):
        by = defaultdict(lambda: [0, 0])
        for r in recs:
            pos = POS[r["position_id"]]
            b = by[pos[field]]
            b[0] += int(r["score"]["critical_square_correct"])
            b[1] += 1
        print(f"\nby {field}:")
        for k, (h, t) in sorted(by.items()):
            print(f"  {k:<12} {h / t:.3f}  ({h}/{t})")


POS = {
    json.loads(l)["id"]: json.loads(l)
    for l in (Path(__file__).parent / "data" / "gate_positions.jsonl")
    .read_text()
    .splitlines()
    if l.strip()
}

if __name__ == "__main__":
    main()
