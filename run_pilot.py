"""Day-1 pilot — 40 positions, one model, arms C0 / C1 / C2 / C3.

PREREGISTRATION.md §4: the pilot exists to set N for the full run from the *observed*
discordant-pair rate, not an assumed one. That job needs the paired C1/C2 cells, the C0
floor they are measured against, and the C3 ceiling on these same positions.

C4 (conversational load) and C5 (pushback) are deliberately NOT in the pilot. Neither
enters the McNemar planning calculation, so running them here would cost ~360 calls that
cannot change N. They run in the full run, on the frozen prompts in prompts.py.

Format is FEN only — the default arm. PGN and move-list are emitted by the generator and
are a factor in the §2 GLMM; the pilot is not powered for a format contrast and does not
pretend to be.

Call hygiene is inherited from run_gate.options() rather than restated, so the pilot's
requests are byte-identical in configuration to the gate that has already been reported:
bare system prompt, no CLAUDE.md, no settings, no hooks, no plugins, no tools, no
thinking. That was verified attachment-by-attachment on the gate probe.

  python run_pilot.py --probe        one call per condition, then stop
  python run_pilot.py                the full pilot, resumable
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

import prompts
import scorer
from run_gate import MODEL, one_call

HERE = Path(__file__).parent
POSITIONS = HERE / "data" / "pilot_positions.jsonl"
OUT = HERE / "data" / "pilot_raw.jsonl"

REPEATS = 3
FORMAT = "fen"

# (condition, variants, per-position?) — C0 is position-independent by construction:
# 3 paraphrases x 3 repeats = 9 calls for the whole pilot, not 9 per position.
PLAN = [
    ("C0", ("a", "b", "c"), False),
    ("C1", ("a", "b", "c"), True),
    ("C2", ("a", "b", "c"), True),
    ("C3", ("a",), True),
]


def jobs_for(positions: list[dict]) -> list[dict]:
    out: list[dict] = []
    for condition, variants, per_position in PLAN:
        targets = positions if per_position else [None]
        for pos in targets:
            for variant in variants:
                for repeat in range(REPEATS):
                    out.append({
                        "position_id": pos["id"] if pos else "_none",
                        "condition": condition,
                        "variant": variant,
                        "repeat": repeat,
                        "_position": pos,
                    })
    return out


def key(rec: dict) -> tuple:
    return (rec["position_id"], rec["condition"], rec["variant"], rec["repeat"])


def score_of(job: dict, response: str) -> dict:
    pos = job["_position"]
    if job["condition"] == "C3":
        return scorer.score_reconstruction(pos, response).__dict__
    if pos is None:
        # The floor has no position to be right about. What it yields is the guess
        # distribution; it is scored against every position's target in the analysis,
        # which is what makes p(C0) comparable to p(C1) rather than a separate number.
        squares = scorer.squares_in(response or "")
        return {
            "position_id": "_none",
            "squares_mentioned": squares,
            "n_squares_mentioned": len(squares),
            "moves_mentioned": scorer.moves_in(response or ""),
            "empty_response": not (response or "").strip(),
        }
    return scorer.score_detection(pos, response).__dict__


async def run(jobs: list[dict], out_path: Path, concurrency: int) -> None:
    sem = asyncio.Semaphore(concurrency)
    lock = asyncio.Lock()
    fh = out_path.open("a")
    done_n = 0
    total = len(jobs)
    spent = 0.0

    async def worker(job: dict) -> None:
        nonlocal done_n, spent
        prompt = prompts.render(job["condition"], job["variant"], job["_position"], FORMAT)
        async with sem:
            t0 = time.time()
            call = await one_call(prompt)
        s = score_of(job, call["response"])
        rec = {k: v for k, v in job.items() if not k.startswith("_")}
        rec |= {
            "model": MODEL,
            "format": FORMAT,
            "system_prompt": prompts.SYSTEM_PROMPT,
            "prompt": prompt,
            "fen": (job["_position"] or {}).get("fen"),
            "critical_square": (job["_position"] or {}).get("critical_square"),
            "wall_s": round(time.time() - t0, 2),
            **call,
            "score": s,
        }
        async with lock:
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            done_n += 1
            spent += call.get("cost_usd") or 0.0
            hit = s.get("hit_square", s.get("critical_square_correct", "-"))
            print(
                f"[{done_n}/{total}] {rec['condition']}.{rec['variant']} "
                f"{rec['position_id']} r{rec['repeat']} hit={hit} "
                f"nsq={s.get('n_squares_mentioned')} ({rec['wall_s']}s) ${spent:.2f}",
                flush=True,
            )

    try:
        await asyncio.gather(*(worker(j) for j in jobs))
    finally:
        fh.close()


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true", help="one call per condition, then stop")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--positions", default=str(POSITIONS),
                    help="position set to run (default: the day-1 pilot's)")
    ap.add_argument("--out", default=str(OUT),
                    help="raw output; resumed from if it already exists")
    args = ap.parse_args()

    positions = [json.loads(l) for l in Path(args.positions).read_text().splitlines() if l.strip()]
    jobs = jobs_for(positions)

    if args.probe:
        seen: set[str] = set()
        probe: list[dict] = []
        for j in jobs:
            if j["condition"] not in seen:
                seen.add(j["condition"])
                probe.append(j)
        jobs = probe
        out_path = HERE / "data" / "pilot_probe.jsonl"
    else:
        out_path = Path(args.out)
        if out_path.exists():
            done = {key(json.loads(l)) for l in out_path.read_text().splitlines() if l.strip()}
            before = len(jobs)
            jobs = [j for j in jobs if key(j) not in done]
            print(f"resuming: {before - len(jobs)} already done, {len(jobs)} to go", flush=True)

    print(f"{len(jobs)} calls, {args.concurrency} at a time, model={MODEL}", flush=True)
    await run(jobs, out_path, args.concurrency)


if __name__ == "__main__":
    asyncio.run(main())
