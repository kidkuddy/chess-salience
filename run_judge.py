"""Blinded judge validation of `detected_self`, exactly as JUDGE-PREREG.md specifies it.

Every C1/C2 response is judged once against the LABELLING.md §2 rubric by a fresh session
that has never seen the conversation which produced it. A 162-response subsample is judged
three times for stability, mirroring RETROFIT-PREREG.md.

The judge is blind to arm, paraphrase, prompt and every scorer field. `assert_blind()`
enforces that on the assembled prompt before any call is made, and the run aborts rather
than spending money on a leaked instrument.

  python run_judge.py --probe    # 6 calls, then stop
  python run_judge.py            # all 1,944, resumable
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import time
from pathlib import Path

import prompts
import run_gate
from build_labelset import ascii_board
from run_arms import one

HERE = Path(__file__).parent
OUT = HERE / "data" / "judge_raw.jsonl"
CONCURRENCY = 8
SEED = 20260813          # fixed; the stability subsample must be reproducible
N_STABILITY = 162        # same size as RETROFIT-PREREG.md's

# --- the rubric, LABELLING.md §2 verbatim ---------------------------------------------

JUDGE_PROMPT = """You are labelling chess responses for a research dataset, one at a time.

A chess engine has identified one CRITICAL SQUARE in this position — the location of the
decisive threat or opportunity. Below is a response somebody wrote about the position.
Your job is to decide how that response treated the critical square.

Assign exactly one label:

2 = DETECTED. The critical square (or a move to or from it) is named, AND the response
    attributes a threat, a weakness, a capture, a tactic or an opportunity to it.
1 = NAMED ONLY. The critical square appears, but only as board transcription, or as one
    item in an undifferentiated list of candidate ideas, or in a statement that dismisses
    it.
0 = ABSENT. The critical square is never named, in any notation.

Rules for the hard cases:

- Board transcription is not detection. Listing every piece and its square is a 1, however
  accurate, regardless of what the response says later about other squares.
- Dismissal is not detection. "Your bishop on c4 is fine" is a 1. The square was named and
  the assessment was wrong.
- An undifferentiated candidate list is not detection. "Ideas include Bf3, Qf3, or
  something on c4", with no assessment attached to c4, is a 1. If the response singles the
  square out for a reason, it is a 2.
- The threat may run either direction. The critical square can hold a hanging piece of the
  writer's own or a capture the writer can make. Both are a 2.
- Correct square, wrong reason still counts. "c4 is hanging" when the engine says c4 is a
  mate-in-one square is a 2. The question is whether the square was surfaced as
  significant, not whether the chess analysis was right.
- Hedged detection counts. "c4 might be loose, worth checking" is a 2.
- Vocabulary is not required. "You can just take on c4 and win a piece" is a 2 with no
  tactical terms in it.
- Wrong-colour or wrong-piece claims about the right square are still a 2.
- Only the critical square counts. A response that finds a real tactic somewhere else and
  misses the critical square is a 0 or a 1.

POSITION
{board}

FEN: {fen}
Side to move: {side}
CRITICAL SQUARE: {critical}
Engine's accepted moves: {accept}

RESPONSE TO LABEL
---
{response}
---

Output exactly one character: 2, 1 or 0. Nothing else."""


def assert_blind(text: str, job: dict) -> None:
    """JUDGE-PREREG.md §4: refuse to spend money on a prompt that leaks the arm.

    Checked against the scaffolding only. The response itself is the thing being judged and
    legitimately contains chess tokens ("Rc1.") and, occasionally, an echo of the prompt
    that produced it. That exposure is a property of the data, not of this instrument, and
    a human labeller under LABELLING.md §3 would face exactly the same one.
    """
    lowered = text.replace(job["response"], "«RESPONSE»").lower()
    for template in (prompts.C1, prompts.C2):
        for variant in template.values():
            stem = variant.split("{position}")[0].strip().lower()[:60]
            if stem and stem in lowered:
                raise SystemExit(f"BLINDING FAILURE: prompt template text in judge prompt "
                                 f"({job['position_id']})")
    for token in ("condition", "c1.", "c2.", "advisory", "detected_self", "hit_square",
                  "hit_move", "paraphrase", "variant"):
        if token in lowered:
            raise SystemExit(f"BLINDING FAILURE: '{token}' in judge prompt "
                             f"({job['position_id']})")


def build_jobs() -> list[dict]:
    pos = {p["id"]: p for p in (json.loads(l) for l in
           (HERE / "data" / "full_positions.jsonl").read_text().splitlines() if l.strip())}

    # which responses have a first extraction, i.e. carry a detected_self to validate
    have = set()
    for r in (json.loads(l) for l in
              (HERE / "data" / "extract_raw.jsonl").read_text().splitlines() if l.strip()):
        if not r.get("is_error") and r.get("extract_repeat") == 0:
            have.add((r["position_id"], r["condition"], r["variant"], r["repeat"]))

    jobs = []
    for r in (json.loads(l) for l in
              (HERE / "data" / "full_raw.jsonl").read_text().splitlines() if l.strip()):
        if r.get("is_error") or r["condition"] not in ("C1", "C2"):
            continue
        key = (r["position_id"], r["condition"], r["variant"], r["repeat"])
        if key not in have:
            continue
        p = pos[r["position_id"]]
        jobs.append({"position_id": r["position_id"], "condition": r["condition"],
                     "variant": r["variant"], "repeat": r["repeat"], "judge_repeat": 0,
                     "critical_square": r["critical_square"], "fen": r["fen"],
                     "side": p["side_to_move"], "accept": ", ".join(p["accept_moves"]),
                     "response": r["response"]})

    jobs.sort(key=lambda j: (j["position_id"], j["condition"], j["variant"], j["repeat"]))
    rng = random.Random(SEED)
    for j in rng.sample(jobs, N_STABILITY):          # §3 stability subsample
        for k in (1, 2):
            jobs.append({**j, "judge_repeat": k})
    return jobs


def render(job: dict) -> str:
    return JUDGE_PROMPT.format(
        board=ascii_board(job["fen"]), fen=job["fen"], side=job["side"],
        critical=job["critical_square"], accept=job["accept"], response=job["response"])


async def run_job(job: dict, cwd: str) -> dict:
    text = render(job)
    assert_blind(text, job)
    answer, res = await one(text, cwd, None)          # fresh session; never resume
    stripped = answer.strip()
    label = stripped if stripped in ("0", "1", "2") else None
    return {k: job[k] for k in ("position_id", "condition", "variant", "repeat",
                                "judge_repeat", "critical_square")} | {
        "judge_label": label, "parsed": label is not None, "raw": stripped[:200],
        "cost_usd": getattr(res, "total_cost_usd", None),
        "session_id": getattr(res, "session_id", None), "is_error": False}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cwd", default=str(HERE))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--probe", action="store_true", help="6 calls, then stop")
    args = ap.parse_args()
    cwd = str(Path(args.cwd).expanduser().resolve())

    jobs = build_jobs()
    out_path = Path(HERE / "data" / "judge_probe.jsonl") if args.probe else Path(args.out)
    if args.probe:
        jobs = jobs[:6]

    done = set()
    if out_path.exists() and not args.probe:
        for line in out_path.read_text().splitlines():
            if line.strip():
                d = json.loads(line)
                done.add((d["position_id"], d["condition"], d["variant"], d["repeat"],
                          d["judge_repeat"]))
    jobs = [j for j in jobs if (j["position_id"], j["condition"], j["variant"],
                                j["repeat"], j["judge_repeat"]) not in done]

    print(f"{len(jobs)} jobs ({len(done)} done), {CONCURRENCY} at a time, cwd={cwd}")
    if not jobs:
        return

    sem = asyncio.Semaphore(CONCURRENCY)
    lock = asyncio.Lock()
    t0, n, spend = time.time(), 0, 0.0
    with out_path.open("a") as fh:
        async def go(job):
            nonlocal n, spend
            async with sem:
                try:
                    rec = await run_job(job, cwd)
                except SystemExit:
                    raise
                except Exception as exc:                       # noqa: BLE001
                    rec = {k: job[k] for k in ("position_id", "condition", "variant",
                                               "repeat", "judge_repeat")}
                    rec.update(is_error=True, judge_label=None, parsed=False,
                               error=f"{type(exc).__name__}: {exc}"[:300])
            async with lock:
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                n += 1
                spend += rec.get("cost_usd") or 0.0
                if n % 100 == 0 or n == len(jobs):
                    el = time.time() - t0
                    print(f"  {n}/{len(jobs)}  ${spend:.2f}  {n/el:.2f}/s  "
                          f"eta {(len(jobs)-n)/max(n/el, 1e-9)/60:.1f}m", flush=True)

        await asyncio.gather(*(go(j) for j in jobs))
    print(f"done: {n} records, ${spend:.2f}, {(time.time()-t0)/60:.1f}m")


if __name__ == "__main__":
    asyncio.run(main())
