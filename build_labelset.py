"""Draw a blinded, position-paired sample for hand labelling, per LABELLING.md §4.

Every position contributes to both arms, so the labelled sample supports the same
paired position-level estimator as the pre-registered primary analysis. Stages are
nested: stage 1 draws one paraphrase per (position, arm), stage 2 a second, stage 3 the
third, so three stages cover a/b/c exactly once each and every stage is paraphrase
balanced on its own.

Writes three files per stage:

  data/label_tasks_stage<N>.json   what the labeller sees. No arm, no paraphrase, no
                                   prompt, no scorer output. Shuffled.
  data/label_key_stage<N>.json     the mapping back. DO NOT OPEN until labelling is done.
  label_ui.html                    self-contained offline labelling tool, tasks embedded.

  python build_labelset.py --stage 1
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

HERE = Path(__file__).parent
SEED = 20260811          # fixed; the draw must be reproducible from the repo alone
N_DOUBLE = 60            # items flagged for the second rater, LABELLING.md §5


def load(raw: Path, positions: Path):
    recs = [json.loads(l) for l in raw.read_text().splitlines() if l.strip()]
    pos = {p["id"]: p for p in
           (json.loads(l) for l in positions.read_text().splitlines() if l.strip())}
    return recs, pos


def ascii_board(fen: str) -> str:
    """8 rows of the board as text. Falls back to the raw FEN if python-chess is absent."""
    try:
        import chess
        b = chess.Board(fen)
    except Exception:
        return fen
    rows = []
    for rank in range(8, 0, -1):
        cells = []
        for file_ in "abcdefgh":
            import chess as _c
            piece = b.piece_at(_c.parse_square(f"{file_}{rank}"))
            cells.append(piece.symbol() if piece else ".")
        rows.append(f"{rank}  " + " ".join(cells))
    return "\n".join(rows) + "\n\n   " + " ".join("abcdefgh")


def variant_plan(position_ids):
    """{position_id: [stage1, stage2, stage3]} paraphrases, exactly balanced per stage.

    Positions are shuffled once under the fixed seed, then position i is assigned the
    base order rotated by i mod 3. With 90 positions each rotation class holds 30, so
    every stage draws exactly 30 of each paraphrase per arm rather than approximately.
    """
    order = sorted(position_ids)
    random.Random(f"{SEED}:plan").shuffle(order)
    base = ["a", "b", "c"]
    return {pid: base[i % 3:] + base[:i % 3] for i, pid in enumerate(order)}


def draw(recs, pos, stage: int, rng: random.Random):
    """One (position, arm, paraphrase, repeat) per cell, paraphrase fixed by stage."""
    by_cell = {}
    for r in recs:
        if r["condition"] not in ("C1", "C2") or r.get("is_error"):
            continue
        by_cell.setdefault((r["condition"], r["position_id"], r["variant"]), []).append(r)

    plan = variant_plan(pos)
    items = []
    for pid in sorted(pos):
        variant = plan[pid][stage - 1]
        for cond in ("C1", "C2"):
            cell = by_cell.get((cond, pid, variant))
            if not cell:
                continue
            rec = rng.choice(sorted(cell, key=lambda x: x["repeat"]))
            items.append((rec, pos[pid]))
    return items


def write_ui(tasks, stage: int) -> None:
    """Assemble label_ui.html for one stage. Always writes the stage it was given, so a
    stale page from another stage cannot survive."""
    ui = (HERE / "label_ui.template.html").read_text()
    ui = ui.replace("/*__TASKS__*/null", json.dumps(tasks))
    ui = ui.replace("__STAGE__", str(stage))
    (HERE / "label_ui.html").write_text(ui)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", type=int, required=True, choices=(1, 2, 3))
    ap.add_argument("--raw", default=str(HERE / "data" / "full_raw.jsonl"))
    ap.add_argument("--positions", default=str(HERE / "data" / "full_positions.jsonl"))
    ap.add_argument("--ui-only", action="store_true",
                    help="rebuild label_ui.html from the stage's existing tasks file "
                         "without redrawing it")
    args = ap.parse_args()

    tasks_path = HERE / "data" / f"label_tasks_stage{args.stage}.json"
    if args.ui_only:
        if not tasks_path.exists():
            raise SystemExit(f"{tasks_path.name} does not exist; draw the stage first.")
        write_ui(json.loads(tasks_path.read_text()), args.stage)
        print(f"label_ui.html rebuilt for stage {args.stage} from {tasks_path.name}")
        return

    key_path = HERE / "data" / f"label_key_stage{args.stage}.json"
    if key_path.exists():
        raise SystemExit(
            f"{key_path.name} already exists. A stage is drawn once and never redrawn, "
            f"or the blinding is worthless. Delete it deliberately if you mean to."
        )

    rng = random.Random(f"{SEED}:stage{args.stage}")
    recs, pos = load(Path(args.raw), Path(args.positions))
    drawn = draw(recs, pos, args.stage, rng)

    tasks, key = [], {}
    for i, (rec, p) in enumerate(drawn):
        uid = f"s{args.stage}-{i:03d}"
        tasks.append({
            "uid": uid,
            "fen": p["fen"],
            "board": ascii_board(p["fen"]),
            "side_to_move": p["side_to_move"],
            "critical_square": p["critical_square"],
            "accept_squares": p["accept_squares"],
            "accept_moves": p["accept_moves"],
            "response": rec["response"] or "",
        })
        key[uid] = {
            "position_id": rec["position_id"], "condition": rec["condition"],
            "variant": rec["variant"], "repeat": rec["repeat"],
            "hit_square": bool(rec["score"].get("hit_square")),
            "hit_move": bool(rec["score"].get("hit_move")),
            "n_squares_mentioned": rec["score"].get("n_squares_mentioned"),
        }

    rng.shuffle(tasks)
    for t in tasks[:N_DOUBLE]:
        t["double_rate"] = True          # flagged for the second rater, LABELLING.md §5
    rng.shuffle(tasks)

    tasks_path.write_text(json.dumps(tasks, indent=1) + "\n")
    key_path.write_text(json.dumps(key, indent=1) + "\n")
    write_ui(tasks, args.stage)

    c1 = sum(1 for k in key.values() if k["condition"] == "C1")
    print(f"stage {args.stage}: {len(tasks)} items ({c1} advisory, {len(tasks)-c1} direct), "
          f"{N_DOUBLE} flagged for the second rater")
    print(f"  {tasks_path.relative_to(HERE)}")
    print(f"  {key_path.relative_to(HERE)}   <- do not open until labelling is finished")
    print(f"  label_ui.html   <- open this in a browser")


if __name__ == "__main__":
    main()
