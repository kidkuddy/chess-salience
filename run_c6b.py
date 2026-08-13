"""C6b — the corrected attribution arm, exactly as C6B-PREREG.md specifies it.

Identical to C6 except for the two changes in C6B-PREREG.md §2: the extraction prompt
names the most recent answer, and the subset check is computed against turn 2 only.

  python run_c6b.py --cwd /path/to/original/run [--probe]
"""

from __future__ import annotations

import argparse, asyncio, json, time
from pathlib import Path

import run_arms
from run_extract import parse_squares

HERE = Path(__file__).parent
OUT = HERE / "data" / "c6b_raw.jsonl"

# C6B-PREREG.md §2(a). Frozen. Not a parameter.
EXTRACT_PROMPT = (
    "Considering ONLY your most recent answer and ignoring everything said earlier in "
    "this conversation, list only the squares that answer singled out as needing "
    "attention: a threat, a weakness, a capture, or an opportunity. One square per line, "
    "algebraic. If that answer singled out none, write NONE. Output nothing else."
)


async def run_job(job: dict, cwd: str) -> dict:
    import prompts
    block = prompts.position_block({"fen": job["fen"]}, "fen")
    answer, res1 = await run_arms.one(prompts.C2["a"].format(position=block), cwd, job["resume"])
    sid = getattr(res1, "session_id", None)
    extraction, res2 = await run_arms.one(EXTRACT_PROMPT, cwd, sid)
    squares, parsed = parse_squares(extraction)
    # §2(b): subset is judged against turn 2 only
    said = set(run_arms._squares_in(answer))
    cost = (getattr(res1, "total_cost_usd", 0) or 0) + (getattr(res2, "total_cost_usd", 0) or 0)
    return {"arm": "C6b", "position_id": job["position_id"], "repeat": job["repeat"],
            "critical_square": job["critical_square"], "response": answer,
            "extraction": extraction, "flagged_squares": squares, "n_flagged": len(squares),
            "parsed": parsed, "subset_of_turn2": all(s in said for s in squares),
            "detected_self": job["critical_square"].lower() in squares,
            "session_id": sid, "cost_usd": cost, "is_error": False}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cwd", required=True)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--probe", action="store_true")
    args = ap.parse_args()
    cwd = str(Path(args.cwd).expanduser().resolve())

    jobs = [j for j in run_arms.build_jobs(HERE / "data" / "full_raw.jsonl", None)
            if j["arm"] == "C6"]
    out_path = Path(HERE / "data" / "c6b_probe.jsonl") if args.probe else Path(args.out)
    if args.probe:
        jobs = jobs[:3]

    done = set()
    if out_path.exists() and not args.probe:
        for line in out_path.read_text().splitlines():
            if line.strip():
                d = json.loads(line)
                done.add((d["position_id"], d["repeat"]))
    jobs = [j for j in jobs if (j["position_id"], j["repeat"]) not in done]
    print(f"{len(jobs)} jobs ({len(done)} done), {run_arms.CONCURRENCY} at a time")
    if not jobs:
        return

    sem = asyncio.Semaphore(run_arms.CONCURRENCY)
    lock = asyncio.Lock()
    t0, n, spend = time.time(), 0, 0.0
    with out_path.open("a") as fh:
        async def go(job):
            nonlocal n, spend
            async with sem:
                try:
                    rec = await run_job(job, cwd)
                except Exception as exc:                        # noqa: BLE001
                    rec = {k: job[k] for k in ("position_id", "repeat", "critical_square")}
                    rec.update(arm="C6b", is_error=True,
                               error=f"{type(exc).__name__}: {exc}"[:300])
            async with lock:
                n += 1
                spend += rec.get("cost_usd") or 0
                fh.write(json.dumps(rec) + "\n"); fh.flush()
                flag = "ERR" if rec.get("is_error") else ("HIT" if rec.get("detected_self") else " . ")
                print(f"[{n}/{len(jobs)}] {flag} {rec['position_id']} r{rec['repeat']} "
                      f"${spend:.2f} {time.time()-t0:.0f}s", flush=True)
        await asyncio.gather(*(go(j) for j in jobs))
    print(f"\ndone: {n} jobs, ${spend:.2f}, {time.time()-t0:.0f}s -> {out_path.name}")


if __name__ == "__main__":
    asyncio.run(main())
