"""Score the frozen Gemini judge and descriptive three-judge panel."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import pilot_report as P
from score_labels import kappa


HERE = Path(__file__).parent
RAW = HERE / "data" / "gemini_labels_stage1.jsonl"
TASKS = HERE / "data" / "label_tasks_stage1.json"
KEY = HERE / "data" / "label_key_stage1.json"
OUT = HERE / "data" / "gemini_labels_report.json"
BOOT, SEED = 10_000, 20260813


def paired(labels: dict[str, bool], key: dict) -> dict:
    by = defaultdict(lambda: defaultdict(list))
    for uid, detected in labels.items():
        row = key[uid]; by[row["condition"]][row["position_id"]].append(detected)
    c1 = {p: float(np.mean(v)) for p, v in by["C1"].items()}
    c2 = {p: float(np.mean(v)) for p, v in by["C2"].items()}
    ids = sorted(set(c1) & set(c2)); diffs = {p: c2[p] - c1[p] for p in ids}
    boot = P.cluster_bootstrap(diffs, ids, np.random.default_rng(SEED), n_boot=BOOT)
    return {"n_positions": len(ids), "p_c1": float(np.mean(list(c1.values()))),
            "p_c2": float(np.mean(list(c2.values()))),
            "rd": float(np.mean(list(diffs.values()))),
            "ci90": [float(np.percentile(boot, 5)), float(np.percentile(boot, 95))],
            "ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]}


def agreement(a: list[str], b: list[str]) -> dict:
    return {"n": len(a), "raw_agreement": sum(x == y for x, y in zip(a, b)) / len(a),
            "kappa_three_level": kappa(a, b)}


def main() -> None:
    records = [json.loads(x) for x in RAW.read_text().splitlines() if x.strip()]
    tasks = {x["uid"]: x for x in json.loads(TASKS.read_text())}
    key = json.loads(KEY.read_text())
    first = {r["uid"]: r["label"] for r in records
             if r["label_repeat"] == 0 and r.get("parsed")}
    repeated = defaultdict(dict)
    for r in records:
        if r.get("parsed"): repeated[r["uid"]][r["label_repeat"]] = r["label"]
    stable = [v for uid, v in repeated.items()
              if tasks[uid].get("double_rate") and {0, 1, 2} <= v.keys()]
    parse_rate = sum(bool(r.get("parsed")) for r in records) / len(records)
    stability = sum(len(set(v.values())) == 1 for v in stable) / len(stable) if stable else 0
    valid = parse_rate >= .98 and stability >= .80 and len(first) == 180

    sonnet_by_key = {}
    for r in (json.loads(x) for x in (HERE / "data/judge_raw.jsonl").read_text().splitlines()
              if x.strip()):
        if r.get("judge_repeat") == 0 and r.get("parsed"):
            sonnet_by_key[(r["position_id"], r["condition"], r["variant"], r["repeat"])] = r["judge_label"]
    haiku = {r["uid"]: r["label"] for r in
             (json.loads(x) for x in (HERE / "data/haiku_labels_stage1.jsonl").read_text().splitlines()
              if x.strip()) if r["label_repeat"] == 0 and r.get("parsed")}
    sonnet = {}
    for uid, row in key.items():
        k = (row["position_id"], row["condition"], row["variant"], row["repeat"])
        sonnet[uid] = sonnet_by_key[k]

    uids = sorted(first)
    majority = {uid: sum(x == "2" for x in (sonnet[uid], haiku[uid], first[uid])) >= 2
                for uid in uids}
    unanimous = {uid: len({sonnet[uid], haiku[uid], first[uid]}) == 1 for uid in uids}
    three_way = {uid: len({sonnet[uid], haiku[uid], first[uid]}) == 3 for uid in uids}
    by_arm = {}
    for arm in ("C1", "C2"):
        arm_uids = [uid for uid in uids if key[uid]["condition"] == arm]
        by_arm[arm] = {"unanimity": float(np.mean([unanimous[u] for u in arm_uids])),
                       "three_way_disagreement": float(np.mean([three_way[u] for u in arm_uids]))}
    report = {
        "protocol": "GEMINI-JUDGE-PROTOCOL.md", "model": records[0]["model"],
        "cli_version": records[0]["cli_version"], "calls": len(records),
        "errors": sum(bool(r.get("is_error")) for r in records),
        "validity": {"parse_rate": parse_rate, "parse_threshold": .98,
                     "stability_all_three": stability, "stability_n": len(stable),
                     "stability_threshold": .80, "passes": valid},
        "label_counts_first_pass": dict(Counter(first.values())),
        "primary": paired({uid: label == "2" for uid, label in first.items()}, key),
        "named_only_rate": {arm: float(np.mean([first[u] == "1" for u in uids
                                  if key[u]["condition"] == arm])) for arm in ("C1", "C2")},
        "agreement": {"sonnet": agreement([first[u] for u in uids], [sonnet[u] for u in uids]),
                      "haiku": agreement([first[u] for u in uids], [haiku[u] for u in uids])},
        "three_judge_majority_detected": paired(majority, key),
        "three_judge_disagreement": {"unanimity": float(np.mean(list(unanimous.values()))),
                                     "three_way_disagreement": float(np.mean(list(three_way.values()))),
                                     "by_arm": by_arm},
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
