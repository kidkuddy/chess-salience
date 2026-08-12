"""C6 and C4, exactly as ATTRIBUTION-PREREG.md specifies them.

C6 resumes each recorded C1.a session and adds the direct tactical question as turn 2,
then a self-report extraction. Turn 1 is the original response; sessions are forked, so
nothing already recorded can change.

C4 plays the frozen conversational prefix ONCE, records the realised assistant turns, and
forks that single session for every call — so the prefix is byte-identical across all of
them and costs eight calls rather than eight per position.

  python run_arms.py --cwd /path/to/original/run --prefix   # build the C4 prefix, stop
  python run_arms.py --cwd /path/to/original/run --probe    # 4 calls, stop
  python run_arms.py --cwd /path/to/original/run            # both arms, resumable
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ThinkingConfigDisabled,
    query,
)

import prompts
import run_gate
import scorer
from run_extract import EXTRACT_PROMPT, parse_squares

HERE = Path(__file__).parent
OUT = HERE / "data" / "arms_raw.jsonl"
PREFIX_SRC = HERE / "prompts" / "c4_prefix.json"
PREFIX_OUT = HERE / "data" / "c4_prefix_realized.json"
CONCURRENCY = 8
REPEATS = 3


def options(cwd: str, session_id: str | None = None) -> ClaudeAgentOptions:
    """Identical hygiene to run_gate.options(); forked resume when a session is given."""
    kw = dict(
        system_prompt=run_gate.SYSTEM_PROMPT,
        setting_sources=[],
        settings=json.dumps({"hooks": {}, "enabledPlugins": {}, "disableAllHooks": True}),
        extra_args={"setting-sources": ""},
        tools=[], allowed_tools=[], mcp_servers={}, strict_mcp_config=True,
        thinking=ThinkingConfigDisabled(type="disabled"),
        model=run_gate.MODEL, max_turns=1, cwd=cwd,
    )
    if session_id:
        kw.update(resume=session_id, fork_session=True)
    return ClaudeAgentOptions(**kw)


async def one(prompt_text: str, cwd: str, session_id: str | None = None):
    text, result = [], None
    async for msg in query(prompt=prompt_text, options=options(cwd, session_id)):
        if isinstance(msg, AssistantMessage):
            text += [b.text for b in msg.content if isinstance(b, TextBlock)]
        elif isinstance(msg, ResultMessage):
            result = msg
    return "\n".join(text).strip(), result


# --- C4 prefix, built once -------------------------------------------------

async def build_prefix(cwd: str) -> dict:
    """Play the frozen user turns once; record what the model actually said."""
    src = json.loads(PREFIX_SRC.read_text())
    session, realised = None, []
    for i, user_turn in enumerate(src["user_turns"], 1):
        reply, res = await one(user_turn, cwd, session)
        session = getattr(res, "session_id", None)
        realised.append({"role": "user", "content": user_turn})
        realised.append({"role": "assistant", "content": reply})
        print(f"  prefix turn {i}/{len(src['user_turns'])}: {len(reply)} chars", flush=True)
    out = {"session_id": session, "turns": realised,
           "source": str(PREFIX_SRC.relative_to(HERE))}
    PREFIX_OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(f"  realised prefix -> {PREFIX_OUT.name}, session {session}")
    return out


# --- jobs ------------------------------------------------------------------

def build_jobs(raw: Path, prefix_session: str | None) -> list[dict]:
    recs = [json.loads(l) for l in raw.read_text().splitlines() if l.strip()]
    c1a = [r for r in recs
           if r["condition"] == "C1" and r["variant"] == "a" and not r.get("is_error")]
    pos = {p["id"]: p for p in (json.loads(l) for l in
           (HERE / "data" / "full_positions.jsonl").read_text().splitlines() if l.strip())}
    jobs = []
    for r in c1a:
        jobs.append({"arm": "C6", "position_id": r["position_id"], "repeat": r["repeat"],
                     "resume": r["session_id"],
                     "critical_square": r["score"]["critical_square"],
                     "fen": pos[r["position_id"]]["fen"]})
    if prefix_session:
        for r in c1a:
            jobs.append({"arm": "C4", "position_id": r["position_id"], "repeat": r["repeat"],
                         "resume": prefix_session,
                         "critical_square": r["score"]["critical_square"],
                         "fen": pos[r["position_id"]]["fen"]})
    return jobs


async def run_job(job: dict, cwd: str) -> dict:
    """Two calls: the arm's own turn, then the self-report extraction."""
    block = prompts.position_block({"fen": job["fen"]}, "fen")
    template = prompts.C2["a"] if job["arm"] == "C6" else prompts.C1["a"]
    answer, res1 = await one(template.format(position=block), cwd, job["resume"])

    sid = getattr(res1, "session_id", None)
    extraction, res2 = await one(EXTRACT_PROMPT, cwd, sid)
    squares, parsed = parse_squares(extraction)
    said = set(_squares_in(answer))
    cost = (getattr(res1, "total_cost_usd", 0) or 0) + (getattr(res2, "total_cost_usd", 0) or 0)
    return {
        "arm": job["arm"], "position_id": job["position_id"], "repeat": job["repeat"],
        "critical_square": job["critical_square"],
        "response": answer, "extraction": extraction,
        "flagged_squares": squares, "n_flagged": len(squares), "parsed": parsed,
        "subset_of_turn": all(s in said for s in squares),
        "detected_self": job["critical_square"].lower() in squares,
        "session_id": sid, "cost_usd": cost, "is_error": False,
    }


def _squares_in(text: str) -> list[str]:
    """The frozen scorer's own square extractor — same function the study has always used."""
    return [s.lower() for s in scorer.squares_in(text)]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cwd", required=True)
    ap.add_argument("--raw", default=str(HERE / "data" / "full_raw.jsonl"))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--prefix", action="store_true", help="build the C4 prefix, then stop")
    ap.add_argument("--probe", action="store_true", help="4 calls, then stop")
    args = ap.parse_args()
    cwd = str(Path(args.cwd).expanduser().resolve())

    if args.prefix or not PREFIX_OUT.exists():
        print("building the C4 prefix (8 calls)...")
        await build_prefix(cwd)
        if args.prefix:
            return

    prefix_session = json.loads(PREFIX_OUT.read_text())["session_id"]
    jobs = build_jobs(Path(args.raw), prefix_session)

    out_path = Path(HERE / "data" / "arms_probe.jsonl") if args.probe else Path(args.out)
    if args.probe:
        jobs = [j for j in jobs if j["arm"] == "C6"][:2] + \
               [j for j in jobs if j["arm"] == "C4"][:2]

    done = set()
    if out_path.exists() and not args.probe:
        for line in out_path.read_text().splitlines():
            if line.strip():
                d = json.loads(line)
                done.add((d["arm"], d["position_id"], d["repeat"]))
    jobs = [j for j in jobs if (j["arm"], j["position_id"], j["repeat"]) not in done]

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
                except Exception as exc:                       # noqa: BLE001
                    rec = {k: job[k] for k in ("arm", "position_id", "repeat",
                                               "critical_square")}
                    rec.update(is_error=True, error=f"{type(exc).__name__}: {exc}"[:300])
            async with lock:
                n += 1
                spend += rec.get("cost_usd") or 0
                fh.write(json.dumps(rec) + "\n"); fh.flush()
                flag = "ERR" if rec.get("is_error") else ("HIT" if rec.get("detected_self") else " . ")
                print(f"[{n}/{len(jobs)}] {flag} {rec['arm']} {rec['position_id']} "
                      f"r{rec['repeat']} ${spend:.2f} {time.time()-t0:.0f}s", flush=True)
        await asyncio.gather(*(go(j) for j in jobs))

    print(f"\ndone: {n} jobs, ${spend:.2f}, {time.time()-t0:.0f}s -> {out_path.name}")


if __name__ == "__main__":
    asyncio.run(main())
