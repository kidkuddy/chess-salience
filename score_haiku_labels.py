"""Score the frozen Haiku cross-model judge after collection completes."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import pilot_report as P
from score_labels import kappa


HERE = Path(__file__).parent
RAW = HERE / "data" / "haiku_labels_stage1.jsonl"
TASKS = HERE / "data" / "label_tasks_stage1.json"
KEY = HERE / "data" / "label_key_stage1.json"
OUT = HERE / "data" / "haiku_labels_report.json"
BOOT = 10_000
SEED = 20260813
MARGIN = 0.10


def metric_stats(pred: list[bool], truth: list[bool]) -> dict:
    tp = sum(p and t for p, t in zip(pred, truth))
    fp = sum(p and not t for p, t in zip(pred, truth))
    fn = sum((not p) and t for p, t in zip(pred, truth))
    tn = sum((not p) and (not t) for p, t in zip(pred, truth))
    return {
        "agreement": (tp + tn) / len(truth) if truth else None,
        "sensitivity": tp / (tp + fn) if tp + fn else None,
        "specificity": tn / (tn + fp) if tn + fp else None,
        "kappa": kappa([str(x) for x in pred], [str(x) for x in truth]),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }


def paired(labels: dict[str, str], key: dict) -> dict:
    by = defaultdict(lambda: defaultdict(list))
    for uid, label in labels.items():
        row = key[uid]
        by[row["condition"]][row["position_id"]].append(label == "2")
    c1 = {pid: float(np.mean(values)) for pid, values in by["C1"].items()}
    c2 = {pid: float(np.mean(values)) for pid, values in by["C2"].items()}
    ids = sorted(set(c1) & set(c2))
    diffs = {pid: c2[pid] - c1[pid] for pid in ids}
    samples = P.cluster_bootstrap(diffs, ids, np.random.default_rng(SEED), n_boot=BOOT)
    return {
        "n_positions": len(ids),
        "p_c1": float(np.mean([c1[pid] for pid in ids])),
        "p_c2": float(np.mean([c2[pid] for pid in ids])),
        "rd": float(np.mean(list(diffs.values()))),
        "ci90": [float(np.percentile(samples, 5)), float(np.percentile(samples, 95))],
        "ci95": [float(np.percentile(samples, 2.5)), float(np.percentile(samples, 97.5))],
    }


def main() -> None:
    records = [json.loads(line) for line in RAW.read_text().splitlines() if line.strip()]
    tasks = {task["uid"]: task for task in json.loads(TASKS.read_text())}
    key = json.loads(KEY.read_text())

    parse_rate = sum(bool(r.get("parsed")) for r in records) / len(records)
    first = {r["uid"]: r["label"] for r in records
             if r["label_repeat"] == 0 and r.get("parsed")}
    repeated = defaultdict(dict)
    for record in records:
        if record.get("parsed"):
            repeated[record["uid"]][record["label_repeat"]] = record["label"]
    stable_rows = [values for uid, values in repeated.items()
                   if tasks[uid].get("double_rate") and {0, 1, 2} <= values.keys()]
    stability = (sum(len(set(values.values())) == 1 for values in stable_rows) / len(stable_rows)
                 if stable_rows else 0.0)
    valid = parse_rate >= 0.98 and stability >= 0.80 and len(first) == 180

    primary = paired(first, key)
    named_only = {}
    for condition in ("C1", "C2"):
        uids = [uid for uid in first if key[uid]["condition"] == condition]
        named_only[condition] = sum(first[uid] == "1" for uid in uids) / len(uids)

    # Existing Sonnet judge, aligned through the sealed key.
    sonnet_map = {}
    for record in (json.loads(line) for line in
                   (HERE / "data" / "judge_raw.jsonl").read_text().splitlines() if line.strip()):
        if record.get("judge_repeat") == 0 and record.get("parsed"):
            k = (record["position_id"], record["condition"], record["variant"], record["repeat"])
            sonnet_map[k] = record["judge_label"]
    sonnet, haiku = [], []
    for uid, label in first.items():
        row = key[uid]
        k = (row["position_id"], row["condition"], row["variant"], row["repeat"])
        if k in sonnet_map:
            haiku.append(label)
            sonnet.append(sonnet_map[k])
    agreement = sum(a == b for a, b in zip(haiku, sonnet)) / len(haiku)

    truth = [first[uid] == "2" for uid in first]
    extracted = {}
    for record in (json.loads(line) for line in
                   (HERE / "data" / "extract_raw.jsonl").read_text().splitlines()
                   if line.strip()):
        if record.get("extract_repeat") == 0 and not record.get("is_error"):
            k = (record["position_id"], record["condition"],
                 record["variant"], record["repeat"])
            extracted[k] = bool(record["detected_self"])
    detected_self = []
    for uid in first:
        row = key[uid]
        k = (row["position_id"], row["condition"], row["variant"], row["repeat"])
        if k not in extracted:
            raise RuntimeError(f"No detected_self record for {uid}: {k}")
        detected_self.append(extracted[k])
    hit_square = [bool(key[uid]["hit_square"]) for uid in first]
    hit_move = [bool(key[uid]["hit_move"]) for uid in first]
    report = {
        "protocol": "HAIKU-JUDGE-PROTOCOL.md",
        "model": records[0]["model"] if records else None,
        "calls": len(records),
        "errors": sum(bool(r.get("is_error")) for r in records),
        "cost_usd": float(sum(r.get("cost_usd") or 0 for r in records)),
        "validity": {"parse_rate": parse_rate, "parse_threshold": 0.98,
                     "stability_all_three": stability, "stability_n": len(stable_rows),
                     "stability_threshold": 0.80, "passes": valid},
        "label_counts_first_pass": dict(Counter(first.values())),
        "primary": primary,
        "equivalence_continuity_check": bool(-MARGIN < primary["ci90"][0]
                                              and primary["ci90"][1] < MARGIN),
        "named_only_rate": named_only,
        "agreement_with_sonnet_judge": {
            "n": len(haiku), "raw_agreement": agreement,
            "kappa_three_level": kappa(haiku, sonnet),
        },
        "metrics_against_haiku_detected": {
            "detected_self": metric_stats(detected_self, truth),
            "hit_square": metric_stats(hit_square, truth),
            "hit_move": metric_stats(hit_move, truth),
        },
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
