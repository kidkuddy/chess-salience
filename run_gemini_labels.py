"""Run the frozen independent-vendor judge in GEMINI-JUDGE-PROTOCOL.md."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import shutil
import time
from pathlib import Path


HERE = Path(__file__).parent
MODEL = "gemini-2.5-pro"
CLI_VERSION = "0.47.0"
TASKS = HERE / "data" / "label_tasks_stage1.json"
OUT = HERE / "data" / "gemini_labels_stage1.jsonl"

PROMPT = """Apply this rubric to the model response for the engine's critical square.

2 DETECTED: The critical square, or a move to/from it, is named AND the response attributes
a threat, weakness, capture, tactic, target, or opportunity to it. Hedged detection counts.
The tactical reason may be wrong; significance attached to the right square still counts.

1 NAMED ONLY: The square appears only as board transcription, in an undifferentiated list
of ideas, or in a statement dismissing it as safe or irrelevant.

0 ABSENT: The square and any move involving it are absent. A tactic elsewhere does not count.

Return exactly one character: 0, 1, or 2. Do not explain and do not use tools.

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


def render(task: dict) -> str:
    return PROMPT.format(
        board=task["board"], side=task["side_to_move"],
        square=task["critical_square"], moves=", ".join(task["accept_moves"]),
        response=task["response"] or "",
    )


def parse_label(text: str) -> str | None:
    value = (text or "").strip()
    return value if value in {"0", "1", "2"} else None


def jobs(tasks: list[dict]) -> list[tuple[dict, int]]:
    out = [(task, 0) for task in tasks]
    for task in tasks:
        if task.get("double_rate"):
            out.extend([(task, 1), (task, 2)])
    return out


async def one(prompt: str) -> dict:
    binary = shutil.which("gemini")
    if not binary:
        raise RuntimeError("gemini CLI not found")
    proc = await asyncio.create_subprocess_exec(
        binary, "--model", MODEL, "--prompt", prompt, "--output-format", "json",
        "--approval-mode", "plan", "--skip-trust",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        cwd=str(HERE),
    )
    stdout, stderr = await proc.communicate()
    raw_json = stdout.decode(errors="replace")
    err = stderr.decode(errors="replace")
    payload = json.loads(raw_json) if raw_json.strip() else {}
    response = payload.get("response", "")
    return {
        "raw": response, "label": parse_label(response),
        "parsed": parse_label(response) is not None,
        "is_error": proc.returncode != 0 or bool(payload.get("error")),
        "returncode": proc.returncode, "stats": payload.get("stats"),
        "cli_error": payload.get("error"), "stderr": err[:1000],
        "cli_json": payload,
    }


async def run(selected: list[tuple[dict, int]], out_path: Path, concurrency: int) -> None:
    semaphore, lock = asyncio.Semaphore(concurrency), asyncio.Lock()
    handle, complete = out_path.open("a"), 0

    async def worker(task: dict, label_repeat: int) -> None:
        nonlocal complete
        prompt, started = render(task), time.time()
        async with semaphore:
            try:
                call = await one(prompt)
            except Exception as exc:
                call = {"raw": "", "label": None, "parsed": False, "is_error": True,
                        "returncode": None, "stats": None, "cli_error": None,
                        "stderr": "", "cli_json": {},
                        "error": f"{type(exc).__name__}: {exc}"[:500]}
        record = {
            "uid": task["uid"], "label_repeat": label_repeat, "model": MODEL,
            "cli_version": CLI_VERSION,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "wall_s": round(time.time() - started, 3), **call,
        }
        async with lock:
            handle.write(json.dumps(record) + "\n"); handle.flush(); complete += 1
            print(f"[{complete}/{len(selected)}] {task['uid']} r{label_repeat} "
                  f"label={record['label']} error={record['is_error']}", flush=True)

    try:
        await asyncio.gather(*(worker(task, repeat) for task, repeat in selected))
    finally:
        handle.close()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()
    tasks = json.loads(TASKS.read_text())
    forbidden = {"condition", "variant", "repeat", "hit_square", "hit_move"}
    leaked = sorted(forbidden & set().union(*(set(task) for task in tasks)))
    if leaked:
        raise SystemExit(f"Blinding failure: task packet contains {leaked}")
    planned, out_path = jobs(tasks), OUT
    if args.probe:
        planned, out_path = planned[:1], HERE / "data" / "gemini_labels_probe.jsonl"
    else:
        done = set()
        if out_path.exists():
            done = {(r["uid"], r["label_repeat"]) for r in
                    (json.loads(line) for line in out_path.read_text().splitlines()
                     if line.strip())}
        planned = [(task, repeat) for task, repeat in planned
                   if (task["uid"], repeat) not in done]
    print(f"{len(planned)} calls; model={MODEL}; output={out_path.name}", flush=True)
    if planned:
        await run(planned, out_path, args.concurrency)


if __name__ == "__main__":
    asyncio.run(main())
