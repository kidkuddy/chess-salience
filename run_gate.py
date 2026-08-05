"""C3 board-reconstruction gate — 30 positions x 3 repeats, sonnet.

Runs through claude-agent-sdk so the call inherits Claude Code credentials. The point of
using the SDK rather than the raw Messages API is credentials only; everything that would
otherwise make it an *agent* call is switched off here, because the experiment's system
prompt is the variable under test:

  system_prompt=None   -> no preset, no Claude Code agent prompt. §2 of PROMPTS.md instead.
  setting_sources=None -> no CLAUDE.md, no settings files, no project instructions.
  tools=[] / allowed_tools=[] -> no tool definitions in the request.
  thinking=disabled    -> PROMPTS.md §0 invariant; thinking-on would pre-run the search.

--probe writes one call and stops, so the exact request can be read before the other 89 go.
"""

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

import scorer

HERE = Path(__file__).parent
POSITIONS = HERE / "data" / "gate_positions.jsonl"
OUT = HERE / "data" / "gate_c3_raw.jsonl"

MODEL = "claude-sonnet-5"
REPEATS = 3

# PROMPTS.md §2 — verbatim, the whole system prompt.
SYSTEM_PROMPT = "You are a helpful assistant."

# PROMPTS.md §6 — C3, one variant, no length cap.
C3_TEMPLATE = """Position (FEN): {fen}

List every piece on the board and the square it stands on, one per line, in the form
"e4: white pawn". List nothing else."""


def options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        # setting_sources=None alone is NOT enough: plugin SessionStart hooks still fire and
        # their stdout is injected into the model's context as attachments (verified in the
        # first probe — code-review-graph and last30days both wrote into the transcript).
        # These three keys plus an explicit empty --setting-sources give a zero-attachment run.
        setting_sources=[],
        settings=json.dumps({"hooks": {}, "enabledPlugins": {}, "disableAllHooks": True}),
        extra_args={"setting-sources": ""},
        tools=[],
        allowed_tools=[],
        mcp_servers={},
        strict_mcp_config=True,
        thinking=ThinkingConfigDisabled(type="disabled"),
        model=MODEL,
        max_turns=1,
        cwd=str(HERE),
    )


async def one_call(prompt: str) -> dict:
    text, result = [], None
    async for msg in query(prompt=prompt, options=options()):
        if isinstance(msg, AssistantMessage):
            text += [b.text for b in msg.content if isinstance(b, TextBlock)]
        elif isinstance(msg, ResultMessage):
            result = msg
    return {
        "response": "\n".join(text),
        "cost_usd": getattr(result, "total_cost_usd", None),
        "duration_ms": getattr(result, "duration_ms", None),
        "is_error": getattr(result, "is_error", None),
        "session_id": getattr(result, "session_id", None),
    }


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true", help="one call, then stop")
    args = ap.parse_args()

    positions = [json.loads(l) for l in POSITIONS.read_text().splitlines() if l.strip()]
    jobs = [(p, r) for p in positions for r in range(REPEATS)]
    if args.probe:
        jobs = jobs[:1]
        out_path = HERE / "data" / "gate_c3_probe.jsonl"
    else:
        out_path = OUT

    done = set()
    if out_path.exists() and not args.probe:
        for line in out_path.read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                done.add((rec["position_id"], rec["repeat"]))

    with out_path.open("a") as fh:
        for i, (pos, rep) in enumerate(jobs, 1):
            if (pos["id"], rep) in done:
                continue
            prompt = C3_TEMPLATE.format(fen=pos["fen"])
            t0 = time.time()
            call = await one_call(prompt)
            s = scorer.score_reconstruction(pos, call["response"])
            rec = {
                "position_id": pos["id"],
                "repeat": rep,
                "condition": "C3",
                "model": MODEL,
                "system_prompt": SYSTEM_PROMPT,
                "prompt": prompt,
                "fen": pos["fen"],
                "critical_square": pos["critical_square"],
                "wall_s": round(time.time() - t0, 2),
                **call,
                "score": s.__dict__,
            }
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            print(
                f"[{i}/{len(jobs)}] {pos['id']} r{rep} "
                f"parsed={s.parsed} mode={s.parse_mode} "
                f"crit={s.critical_square_correct} f1={s.placement_f1} "
                f"({rec['wall_s']}s)",
                flush=True,
            )


if __name__ == "__main__":
    asyncio.run(main())
