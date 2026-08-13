"""Run the frozen Haiku cross-model judge in HAIKU-JUDGE-PROTOCOL.md.

One pass over all 180 blinded stage-1 tasks plus two additional passes over the 60 tasks
already flagged for reliability. Output is resumable JSONL and remains blinded.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
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


HERE = Path(__file__).parent
MODEL = "claude-haiku-4-5-20251001"
TASKS = HERE / "data" / "label_tasks_stage1.json"
OUT = HERE / "data" / "haiku_labels_stage1.jsonl"
SYSTEM = "Apply the supplied labelling rubric. Return exactly one digit: 0, 1, or 2."

PROMPT = """Label the model response for the engine's critical square.

2 DETECTED: The critical square, or a move to/from it, is named AND the response attributes
a threat, weakness, capture, tactic, target, or opportunity to it. Hedged detection counts.
The tactical reason may be wrong; significance attached to the right square still counts.

1 NAMED ONLY: The square appears only as board transcription, in an undifferentiated list
of ideas, or in a statement dismissing it as safe or irrelevant.

0 ABSENT: The square and any move involving it are absent. A tactic elsewhere does not count.

Return exactly one character: 0, 1, or 2. Do not explain.

Board:
{board}

Side to move: {side}
Critical square: {square}
Accepted engine move notation (recognition aid only): {moves}

Response:
---
{response}
---

Label:"""


def options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt=SYSTEM,
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


def render(task: dict) -> str:
    return PROMPT.format(
        board=task["board"],
        side=task["side_to_move"],
        square=task["critical_square"],
        moves=", ".join(task["accept_moves"]),
        response=task["response"] or "",
    )


def parse_label(text: str) -> str | None:
    value = (text or "").strip()
    return value if value in {"0", "1", "2"} else None


async def one(prompt: str) -> dict:
    text, result = [], None
    async for msg in query(prompt=prompt, options=options()):
        if isinstance(msg, AssistantMessage):
            text.extend(b.text for b in msg.content if isinstance(b, TextBlock))
        elif isinstance(msg, ResultMessage):
            result = msg
    raw = "\n".join(text)
    return {
        "raw": raw,
        "label": parse_label(raw),
        "parsed": parse_label(raw) is not None,
        "cost_usd": getattr(result, "total_cost_usd", None),
        "duration_ms": getattr(result, "duration_ms", None),
        "is_error": getattr(result, "is_error", None),
        "session_id": getattr(result, "session_id", None),
    }


def jobs(tasks: list[dict]) -> list[tuple[dict, int]]:
    out = [(task, 0) for task in tasks]
    for task in tasks:
        if task.get("double_rate"):
            out.extend([(task, 1), (task, 2)])
    return out


async def run(selected: list[tuple[dict, int]], out_path: Path, concurrency: int) -> None:
    semaphore = asyncio.Semaphore(concurrency)
    lock = asyncio.Lock()
    handle = out_path.open("a")
    complete = 0

    async def worker(task: dict, label_repeat: int) -> None:
        nonlocal complete
        prompt = render(task)
        started = time.time()
        async with semaphore:
            try:
                call = await one(prompt)
            except Exception as exc:  # recorded once; protocol forbids automatic retry
                call = {"raw": "", "label": None, "parsed": False, "cost_usd": None,
                        "duration_ms": None, "is_error": True, "session_id": None,
                        "error": f"{type(exc).__name__}: {exc}"[:500]}
        record = {
            "uid": task["uid"],
            "label_repeat": label_repeat,
            "model": MODEL,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "wall_s": round(time.time() - started, 3),
            **call,
        }
        async with lock:
            handle.write(json.dumps(record) + "\n")
            handle.flush()
            complete += 1
            print(f"[{complete}/{len(selected)}] {task['uid']} r{label_repeat} "
                  f"label={record['label']} error={bool(record.get('is_error'))}", flush=True)

    try:
        await asyncio.gather(*(worker(task, repeat) for task, repeat in selected))
    finally:
        handle.close()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true", help="run one call into a separate file")
    parser.add_argument("--concurrency", type=int, default=8)
    args = parser.parse_args()

    tasks = json.loads(TASKS.read_text())
    forbidden = {"condition", "variant", "repeat", "hit_square", "hit_move"}
    leaked = sorted(forbidden & set().union(*(set(task) for task in tasks)))
    if leaked:
        raise SystemExit(f"Blinding failure: task packet contains {leaked}")
    planned = jobs(tasks)

    if args.probe:
        planned = planned[:1]
        out_path = HERE / "data" / "haiku_labels_probe.jsonl"
    else:
        out_path = OUT
        done = set()
        if out_path.exists():
            done = {(r["uid"], r["label_repeat"]) for r in
                    (json.loads(line) for line in out_path.read_text().splitlines() if line.strip())}
        planned = [(task, repeat) for task, repeat in planned
                   if (task["uid"], repeat) not in done]

    print(f"{len(planned)} calls; model={MODEL}; output={out_path.name}", flush=True)
    if planned:
        await run(planned, out_path, args.concurrency)


if __name__ == "__main__":
    asyncio.run(main())
