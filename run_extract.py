"""The self-report extraction retrofit, exactly as RETROFIT-PREREG.md specifies it.

Resumes each original C1/C2 session and adds one turn asking the model which squares its
own answer singled out. Turn 1 is the original response; nothing is regenerated. Sessions
are forked, so the recorded transcripts are not mutated and every number in RESULTS.md
stays reproducible whatever this produces.

Two things this script will not let you get wrong:

  - Sessions are keyed by working directory. Resuming from anywhere other than the
    directory the original run used silently fails, so --cwd is required and checked
    against the session store before any call is made.
  - The extraction prompt is frozen in RETROFIT-PREREG.md §2 and is a constant here. It
    is not a parameter.

  python run_extract.py --cwd /path/to/original/run --probe   # 6 calls, then stop
  python run_extract.py --cwd /path/to/original/run           # the full retrofit, resumable
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
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

import run_gate

HERE = Path(__file__).parent
OUT = HERE / "data" / "extract_raw.jsonl"

SEED = 20260811
STABILITY_FRACTION = 0.10     # RETROFIT-PREREG.md §2
STABILITY_REPEATS = 3
CONCURRENCY = 8               # matches the original run

# RETROFIT-PREREG.md §2. Frozen. Not a parameter.
EXTRACT_PROMPT = (
    "Without re-examining the position and without any new analysis, list only the "
    "squares your answer above already singled out as needing attention: a threat, a "
    "weakness, a capture, or an opportunity. One square per line, algebraic. If your "
    "answer singled out none, write NONE. Output nothing else."
)

SQUARE = re.compile(r"^[a-h][1-8]$")


def parse_squares(text: str) -> tuple[list[str], bool]:
    """RETROFIT-PREREG.md §3. Returns (squares, parsed_ok)."""
    if text.strip().upper().startswith("NONE"):
        return [], True
    out, junk = [], 0
    for line in text.splitlines():
        tok = line.strip().strip("-*`.,;:").split()
        if not tok:
            continue
        cand = tok[0].strip("-*`.,;:").lower()
        if SQUARE.match(cand):
            out.append(cand)
        elif cand.upper() != "NONE":
            junk += 1
    return sorted(set(out)), junk == 0


def options(session_id: str, cwd: str) -> ClaudeAgentOptions:
    """Identical hygiene to run_gate.options(), plus a forked resume."""
    return ClaudeAgentOptions(
        system_prompt=run_gate.SYSTEM_PROMPT,
        setting_sources=[],
        settings=json.dumps({"hooks": {}, "enabledPlugins": {}, "disableAllHooks": True}),
        extra_args={"setting-sources": ""},
        tools=[], allowed_tools=[], mcp_servers={}, strict_mcp_config=True,
        thinking=ThinkingConfigDisabled(type="disabled"),
        model=run_gate.MODEL,
        max_turns=1,
        cwd=cwd,
        resume=session_id,
        fork_session=True,
    )


async def one_extraction(job: dict, cwd: str) -> dict:
    text, result = [], None
    async for msg in query(prompt=EXTRACT_PROMPT, options=options(job["session_id"], cwd)):
        if isinstance(msg, AssistantMessage):
            text += [b.text for b in msg.content if isinstance(b, TextBlock)]
        elif isinstance(msg, ResultMessage):
            result = msg
    raw = "\n".join(text).strip()
    squares, parsed = parse_squares(raw)
    said = {s.lower() for s in job["squares_mentioned"]}
    return {
        **{k: job[k] for k in ("position_id", "condition", "variant", "repeat",
                               "session_id", "critical_square", "extract_repeat")},
        "extraction": raw,
        "flagged_squares": squares,
        "n_flagged": len(squares),
        "parsed": parsed,
        # RETROFIT-PREREG.md §4: the check that the model reported rather than re-analysed
        "subset_of_turn1": all(s in said for s in squares),
        "detected_self": job["critical_square"].lower() in squares,
        "cost_usd": getattr(result, "total_cost_usd", None),
        "duration_ms": getattr(result, "duration_ms", None),
        "is_error": getattr(result, "is_error", None),
    }


def build_jobs(raw: Path, session_dir: Path | None) -> list[dict]:
    recs = [json.loads(l) for l in raw.read_text().splitlines() if l.strip()]
    base = [r for r in recs
            if r["condition"] in ("C1", "C2") and not r.get("is_error")]

    if session_dir is not None:
        on_disk = {p.stem for p in session_dir.glob("*.jsonl")}
        missing = [r["session_id"] for r in base if r["session_id"] not in on_disk]
        if missing:
            raise SystemExit(
                f"{len(missing)} of {len(base)} sessions are not in {session_dir}.\n"
                f"Sessions are keyed by working directory; --cwd is probably wrong.\n"
                f"first missing: {missing[0]}"
            )

    rng = random.Random(SEED)
    stability = set(rng.sample(sorted(r["session_id"] for r in base),
                               int(len(base) * STABILITY_FRACTION)))
    jobs = []
    for r in base:
        reps = STABILITY_REPEATS if r["session_id"] in stability else 1
        for k in range(reps):
            jobs.append({
                "position_id": r["position_id"], "condition": r["condition"],
                "variant": r["variant"], "repeat": r["repeat"],
                "session_id": r["session_id"], "extract_repeat": k,
                "critical_square": r["score"]["critical_square"],
                "squares_mentioned": r["score"].get("squares_mentioned", []),
            })
    return jobs


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cwd", required=True,
                    help="the ORIGINAL run's directory; sessions are keyed by it")
    ap.add_argument("--raw", default=str(HERE / "data" / "full_raw.jsonl"))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--probe", action="store_true", help="6 calls, then stop")
    args = ap.parse_args()

    cwd = str(Path(args.cwd).expanduser().resolve())
    slug = "-" + cwd.replace("/", "-").lstrip("-")
    session_dir = Path.home() / ".claude" / "projects" / slug
    jobs = build_jobs(Path(args.raw), session_dir if session_dir.is_dir() else None)

    out_path = Path(HERE / "data" / "extract_probe.jsonl") if args.probe else Path(args.out)
    if args.probe:
        jobs = jobs[:6]

    done = set()
    if out_path.exists() and not args.probe:
        for line in out_path.read_text().splitlines():
            if line.strip():
                d = json.loads(line)
                done.add((d["session_id"], d["extract_repeat"]))
    jobs = [j for j in jobs if (j["session_id"], j["extract_repeat"]) not in done]

    print(f"{len(jobs)} extractions to run ({len(done)} already done), "
          f"{CONCURRENCY} at a time, cwd={cwd}")
    if not jobs:
        return

    sem = asyncio.Semaphore(CONCURRENCY)
    t0, n, spend = time.time(), 0, 0.0
    lock = asyncio.Lock()

    with out_path.open("a") as fh:
        async def run(job):
            nonlocal n, spend
            async with sem:
                try:
                    rec = await one_extraction(job, cwd)
                except Exception as exc:                       # noqa: BLE001
                    rec = {**{k: job[k] for k in ("position_id", "condition", "variant",
                                                  "repeat", "session_id", "extract_repeat",
                                                  "critical_square")},
                           "is_error": True, "error": f"{type(exc).__name__}: {exc}"[:300]}
            async with lock:
                n += 1
                spend += rec.get("cost_usd") or 0
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                flag = "ERR" if rec.get("is_error") else (
                    "HIT" if rec.get("detected_self") else " . ")
                print(f"[{n}/{len(jobs)}] {flag} {rec['condition']}.{rec['variant']} "
                      f"{rec['position_id']} n_flagged={rec.get('n_flagged','-')} "
                      f"${spend:.2f} {time.time()-t0:.0f}s", flush=True)

        await asyncio.gather(*(run(j) for j in jobs))

    print(f"\ndone: {n} extractions, ${spend:.2f}, {time.time()-t0:.0f}s -> {out_path.name}")
    print("next: python score_extract.py")


if __name__ == "__main__":
    asyncio.run(main())
