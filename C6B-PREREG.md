# Pre-registration — C6b, the corrected attribution arm

**Status: FROZEN 2026-08-13, before any C6b call was made.**

Fourth frozen document in this study. Same rule: nothing below may be edited after the
first call; corrections get appended with a date and a reason.

## 1. Why there is a second attempt

C6 was reported as **attempted and invalid** under `ATTRIBUTION-PREREG.md` §5: subset rate
0.759 against a 0.90 threshold. The failed run is kept at `data/arms_raw.jsonl` and its
verdict stands — nothing below revises it.

The cause is diagnosed and is in the instrument, not the finding. 64 of 65 subset failures
are squares the model named in **turn 1**, which sits in the conversation context. The
extraction prompt asks for "the squares your answer above already singled out", and once a
conversation has two answers, *"your answer above"* is ambiguous. C6 measured a
conversation-level flag list rather than the turn-2 quantity `ATTRIBUTION-PREREG.md` §6
defines.

**What is being fixed is a prompt, not a threshold, a metric, an estimand, or a branch.**
Every one of those is carried over unchanged from `ATTRIBUTION-PREREG.md` §4–§6 and
restated in §3 below so this document stands alone.

## 2. The two changes

**(a) The extraction prompt.** "your answer above" → "your most recent answer", with an
explicit instruction to ignore earlier turns:

```
Considering ONLY your most recent answer and ignoring everything said earlier in
this conversation, list only the squares that answer singled out as needing
attention: a threat, a weakness, a capture, or an opportunity. One square per line,
algebraic. If that answer singled out none, write NONE. Output nothing else.
```

**(b) The subset check is computed against turn 2 only** — the direct-question answer —
which is what §5's check was always meant to test and what the C6 implementation got wrong
by comparing against a single turn while the model answered for two.

## 3. Everything carried over unchanged

- **Metric.** `detected_self`: the critical square appears in the model's own flagged list,
  parsed exactly as `RETROFIT-PREREG.md` §3 specifies.
- **Design.** Resume and fork each recorded C1.a session, add C2.a verbatim as turn 2, then
  the extraction turn. Turn 1 is the original response; nothing is regenerated.
- **Validity thresholds.** resume ≥ 0.98, parse ≥ 0.98, subset ≥ 0.90, turn-1 identity exact.
- **Estimand.** R = P(turn 2 detects | turn 1 did not detect), cluster bootstrap over
  positions, 10,000 resamples.
- **Branches.** R ≥ 0.40 elicitation-dominant; R ≤ 0.15 reasoning-dominant; between, mixed.
- **Confound and its two bounds.** P(turn 2 detects | turn 1 detected), and R against C2's
  standalone 0.536.
- **What each outcome does to the paper.** `ATTRIBUTION-PREREG.md` §8, unchanged.

## 4. Attempt budget

**C6b is the final attempt.** If it fails any §3 validity threshold, the attribution
question is reported as unresolved in the paper, both failed runs are reported with their
subset rates, and no recovery rate is computed from either. No third attempt.

## 5. What this run cannot fix

The confound declared in `ATTRIBUTION-PREREG.md` §6 is unchanged and is not a defect of the
instrument: turn 2 still has turn 1's analysis in context, so a turn-2 hit may reflect a
second look rather than a withheld claim. The two bounds are reported regardless of branch,
and a high R must be read against them rather than as clean evidence of elicitation.

## 6. Cost

270 sessions × 2 calls = **540 calls**, roughly $4. Output to `data/c6b_raw.jsonl`,
resumable by `(position_id, repeat)`, append-only. The failed C6 records stay in
`data/arms_raw.jsonl` and are not overwritten.
