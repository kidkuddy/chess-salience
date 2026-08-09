"""Scorer reliability on the full run — blind hand-audit of 50 responses.

The number this produces is the "scorer agreement" figure RESULTS.md reports. It exists
because `scorer.py` is the only thing standing between a model's prose and a binary
`hit_square`, and a paper that reports detection rates without auditing its own extractor
is reporting the extractor, not the model.

The audit is BLIND by construction, in two steps:

  python audit_scorer.py --emit      writes data/audit_unlabelled.json — response text and
                                     the position's accept lists, and NOTHING from the
                                     scorer. Label these by hand into data/audit_labels.json
                                     as {"<uid>": {"hit_square": bool, "hit_move": bool}}.

  python audit_scorer.py --compare   joins the labels against scorer.py's verdicts and
                                     prints exact-match agreement per metric, plus every
                                     disagreement in full so it can be adjudicated.

Sampling is stratified over condition x scorer-verdict so the audit cannot be dominated by
the majority cell — with detection around 0.85, a uniform sample of 50 would carry only a
handful of scorer-misses, and misses are where an extractor bug would actually live.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
SEED = 20260809
N_AUDIT = 50


def uid(r: dict) -> str:
    return f"{r['condition']}.{r['variant']}|{r['position_id']}|r{r['repeat']}"


def load_raw(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def sample(recs: list[dict], n: int) -> list[dict]:
    """Stratify over (condition, scorer hit_square) so misses are over-represented."""
    pool = [r for r in recs if r["condition"] in ("C1", "C2") and not r.get("is_error")]
    cells: dict[tuple, list] = defaultdict(list)
    for r in pool:
        cells[(r["condition"], bool(r["score"].get("hit_square")))].append(r)
    rng = random.Random(SEED)
    for v in cells.values():
        rng.shuffle(v)
    out: list[dict] = []
    # round-robin across cells until n, so small cells (the misses) are fully drawn
    while len(out) < n and any(cells.values()):
        for k in sorted(cells, key=str):
            if cells[k] and len(out) < n:
                out.append(cells[k].pop())
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(HERE / "data" / "full_raw.jsonl"))
    ap.add_argument("--positions", default=str(HERE / "data" / "full_positions.jsonl"))
    ap.add_argument("--unlabelled", default=str(HERE / "data" / "audit_unlabelled.json"))
    ap.add_argument("--labels", default=str(HERE / "data" / "audit_labels.json"))
    ap.add_argument("--out", default=str(HERE / "data" / "audit_report.json"))
    ap.add_argument("--emit", action="store_true")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--n", type=int, default=N_AUDIT)
    args = ap.parse_args()

    recs = load_raw(Path(args.raw))
    positions = {p["id"]: p for p in
                 (json.loads(l) for l in Path(args.positions).read_text().splitlines() if l.strip())}
    picked = sample(recs, args.n)

    if args.emit:
        items = []
        for r in picked:
            p = positions[r["position_id"]]
            items.append({
                "uid": uid(r),
                "critical_square": p["critical_square"],
                "critical_move_san": p["critical_move_san"],
                "accept_squares": p["accept_squares"],
                "accept_moves": p["accept_moves"],
                "response": r["response"],
            })
        Path(args.unlabelled).write_text(json.dumps(items, indent=1))
        print(f"wrote {len(items)} unlabelled -> {args.unlabelled}")
        print("label into", args.labels, 'as {"<uid>": {"hit_square": bool, "hit_move": bool}}')
        return

    if args.compare:
        labels = json.loads(Path(args.labels).read_text())
        by_uid = {uid(r): r for r in picked}
        rows, disagreements = [], []
        for u, lab in labels.items():
            r = by_uid.get(u)
            if r is None:
                continue
            for metric in ("hit_square", "hit_move"):
                mine = bool(lab[metric])
                theirs = bool(r["score"].get(metric))
                rows.append((metric, mine == theirs))
                if mine != theirs:
                    disagreements.append({
                        "uid": u, "metric": metric,
                        "hand": mine, "scorer": theirs,
                        "critical_square": positions[r["position_id"]]["critical_square"],
                        "response": r["response"],
                    })
        agree = {}
        for metric in ("hit_square", "hit_move"):
            hits = [ok for m, ok in rows if m == metric]
            agree[metric] = {"n": len(hits), "agreed": sum(hits),
                             "agreement": (sum(hits) / len(hits)) if hits else None}
        report = {"n_audited": len(labels), "agreement": agree,
                  "disagreements": disagreements}
        Path(args.out).write_text(json.dumps(report, indent=2))
        print(json.dumps({"n_audited": report["n_audited"], "agreement": agree}, indent=2))
        for d in disagreements:
            print(f"\n--- DISAGREE {d['uid']} {d['metric']}: hand={d['hand']} "
                  f"scorer={d['scorer']} (critical {d['critical_square']})\n{d['response'][:500]}")
        return

    ap.error("pass --emit or --compare")


if __name__ == "__main__":
    main()
