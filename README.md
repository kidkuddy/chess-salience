# chess-salience

A pre-registered behavioural test of whether advisory framing suppresses what a language
model reports about a chess position it can demonstrably read.

The question: a deployed assistant is usually asked something open ("what should I be
thinking about here?") rather than interrogated ("is anything hanging?"). If models hold
back what they represent, advisory framing is where that should show up. Holding the
position fixed and varying only the framing, does the model still name the critical square?

It does. And the more portable finding is about how that was measured: the same 1,620
responses, scored three ways, give detection rates from 0.51 to 0.83 and the same answer to
the comparison.

This repository holds the whole experiment — five frozen protocols, the generator, the
prompts, the scorer, every raw model response, the analysis and the results. Every number
below is reproducible from `data/` with the scripts here.

## Headline result

One contrast, three operationalisations of "detected", on the same responses.

| metric | advisory C1 | direct C2 | risk difference | 90% CI |
|---|---|---|---|---|
| `hit_square` (pre-registered) | 0.814 | 0.833 | +0.020 | [−0.016, +0.057] |
| `detected_self` (model self-report) | 0.542 | 0.536 | −0.006 | [−0.059, +0.047] |
| blinded judge | 0.512 | 0.526 | +0.014 | [−0.033, +0.063] |
| `hit_move` (strict secondary) | 0.125 | 0.174 | +0.049 | [+0.017, +0.081] |

All inside the pre-registered ±0.10 equivalence margin. The null was registered in advance
as a publishable outcome, against the hypothesis this study was built to confirm.

| | |
|---|---|
| board-reconstruction ceiling | 0.981 |
| position-withheld floor | 0.000 (a refusal, not a guess) |
| advisory under 8 exchanges of unrelated chat | 0.522 vs 0.548, RD −0.026, 95% CI [−0.093, +0.041] |
| smallest margin at which equivalence holds | ±0.075 (fails at ±0.05) |
| calls / errors / cost, five runs | 6,597 / 0 / $52.62 |

**Wording beats framing by 14×.** Detection spreads 0.089 across the three advisory
wordings against a 0.006 gap between arms. A binomial GEE agrees: the condition coefficient
is −0.025 (p = 0.849), the paraphrase coefficients +0.119 and +0.104.

## The metric result

The pre-registered metric, `hit_square`, fires when the critical square appears anywhere in
the response. Measured against the blinded judge over all 1,620 responses:

| metric | sensitivity | specificity | κ |
|---|---|---|---|
| `hit_square` | 0.986 | 0.352 | 0.346 |
| `detected_self` | 0.779 | 0.720 | 0.500 |
| `hit_move` | 0.277 | 0.988 | 0.258 |

`hit_square` is a near-perfect recall device and a poor classifier — it inflates advisory by
0.273 and direct by 0.298. Because that inflation is close to symmetric (difference +0.025,
95% CI [−0.033, +0.084]), the paired contrast is still estimated correctly while the
absolute rates are not. Symmetry, not accuracy, is what a paired contrast requires, and it
is measurable on data a study already has.

The judge's three levels also separate the arms in a way no binary metric can. Advisory
names the critical square without attributing anything to it in 0.295 of answers against
0.220 for direct, and fails to name it at all in 0.193 against 0.254. Advisory casts a
wider net (6.03 flagged squares per answer) and direct is narrower (3.79); net detection
comes out equal by two different routes.

## Attributing the shortfall

The model reconstructs the critical square in 0.981 of C3 calls and reports it in 0.548 of
advisory answers. Resuming each advisory session and asking the direct question inside the
same conversation recovers **R = 0.242** of the misses, 95% CI [0.151, 0.336] — between the
pre-registered thresholds for elicitation-dominant (≥0.40) and reasoning-dominant (≤0.15),
so the mixed branch fires and the protocol forbids attributing further.

The declared confound bound is informative on its own: P(turn 2 detects | turn 1 detected)
is 0.481, *below* the 0.536 the direct question achieves standing alone. The second question
does not make the model sharper.

## Frozen protocol

Read these first. The analysis scripts read their thresholds off these documents rather
than restating them. Each fixes its own validity checks and its own failure branch before
the run it governs.

| file | what it fixes | frozen |
|---|---|---|
| `GAP.md` | the gap sentence the study exists to satisfy, with citations | 2026-08-04 |
| `PREREGISTRATION.md` | arms, metrics, estimators, thresholds, three outcome branches | 2026-08-05T18:02+01:00 |
| `PROMPTS.md` | every prompt verbatim, the exclusion word list, the cell budget | 2026-08-05T18:02+01:00 |
| `EXPLORATORY.md` | the severity hypothesis and its support criteria, committed before its confirming positions existed | 2026-08-09 |
| `RETROFIT-PREREG.md` | the self-report metric, its extraction prompt and validity gates | 2026-08-12 |
| `ATTRIBUTION-PREREG.md` | the C4 load arm and the C6 attribution arm | 2026-08-12 |
| `C6B-PREREG.md` | the corrected attribution arm, declared the final attempt | 2026-08-13 |
| `JUDGE-PREREG.md` | the blinded judge validation and its limits | 2026-08-13 |
| `LABELLING.md` | the human labelling protocol — built, blinded, **not run** | 2026-08-11 |

**One of these fired its own invalidity branch.** C6's extraction prompt asked for "the
squares your answer above already singled out", which is ambiguous once a conversation has
two answers. Its subset rate came back at 0.759 against a 0.90 threshold and it is reported
as attempted and invalid; no recovery rate was computed from it, though an argument exists
that one survives. `C6B-PREREG.md` corrected the prompt and passes the same check at 0.996.
The failed run is still in `data/arms_raw.jsonl`. Both rejected C4 conversational prefixes
are kept too, at `data/c4_prefix_realized_attempt*_FAILED.json`.

The ordering those dates assert is checkable rather than taken on trust: this repository
carries the original commit history, so `git log` shows the exploratory hypothesis landing
before the run that tests it, and the pre-registration freezing before the gate runner
exists. Two caveats — the paper's commits were filtered out when this repository was split
off, and `data/` was gitignored in the original working repo, so the first raw outputs
arrive in one commit and their timestamps are not independently attested by git.

## Map

**Instruments.**

| file | role |
|---|---|
| `gen_positions.py` | random-walk generator, Stockfish 18 labelling at depth 18, band sampling |
| `prompts.py` | renders the frozen templates; substitutes only the position block |
| `scorer.py` | deterministic square/move extraction and board reconstruction. No LLM judge |
| `run_gate.py` | the C3 screening gate that had to pass before the study could run |
| `run_pilot.py` | the run driver, used for both the pilot and the full run |
| `run_extract.py` | the self-report retrofit; forks each recorded session, adds one turn |
| `run_arms.py` | the C4 load arm and the C6 attribution arm |
| `run_c6b.py` | the corrected attribution arm |
| `run_judge.py` | the blinded judge; asserts blinding on each prompt before spending |
| `build_labelset.py` | draws a labelling stage, blinds it, writes tasks, sealed key and UI |

**Analysis.**

| file | produces |
|---|---|
| `gate_report.py` | the gate decision |
| `pilot_report.py` | the confirmatory analysis, per `PREREGISTRATION.md` §2–§4 |
| `exploratory_report.py` | the severity follow-up, per `EXPLORATORY.md` |
| `robustness.py` | chance correction, both paraphrase pairings, branch power, Wilson intervals |
| `score_extract.py` | the retrofit's validity gates and primary estimate |
| `score_arms.py` | C4 and C6, with the per-arm validity checks |
| `score_c6b.py` | the recovery rate and its confound bounds |
| `score_judge.py` | judge validity, agreement, and every metric against it |
| `final_analyses.py` | severity on the clean metric, the GEE, the margin curve, pairings, config |
| `score_labels.py` | unblinds hand labels and validates each metric against them |
| `RESULTS.md` | the write-up |

**Data.** Nothing here is derived by hand.

| file | contents |
|---|---|
| `data/full_raw.jsonl` | 1,899 records: every prompt, response, score, cost and duration |
| `data/extract_raw.jsonl` | 1,944 self-report extractions, including a 3× stability subsample |
| `data/arms_raw.jsonl` | 540 records: C4 and the invalid C6 |
| `data/c6b_raw.jsonl` | 270 records: the corrected attribution arm |
| `data/judge_raw.jsonl` | 1,944 judge labels, including a 3× stability subsample |
| `data/full_positions.jsonl` | the 90 reported positions with engine labels |
| `data/*_report.json` | the frozen analysis output for each run |
| `data/final_analyses.json` | severity, GEE, margin curve, pairings, configuration |
| `data/pilot_*` | the pilot. It crashed partway: 568 of 849 calls |
| `data/gate_*` | the C3 screening gate, 90 calls over 30 positions |
| `data/label_*` | the blinded labelling stage 1, drawn and unrun |

## Reproducing

```sh
python -m venv .venv && .venv/bin/pip install -r requirements.txt
brew install stockfish                        # only to regenerate positions

.venv/bin/python pilot_report.py --raw data/full_raw.jsonl \
    --positions data/full_positions.jsonl --json /tmp/check.json --sims 4000
.venv/bin/python robustness.py                # chance correction, pairings, branch power
.venv/bin/python score_extract.py             # the self-report metric
.venv/bin/python score_arms.py                # C4, and C6's invalidity
.venv/bin/python score_c6b.py                 # the recovery rate
.venv/bin/python score_judge.py               # judge validation and the metric table
.venv/bin/python final_analyses.py            # severity, GEE, margins, pairings, config
.venv/bin/python tests/test_scorer.py         # scorer unit tests
.venv/bin/python tests/test_prompts.py        # prompts match PROMPTS.md verbatim
```

Re-running the model calls needs API credentials and will not reproduce the recorded
outputs: temperature is 1.0 and hosted models are not deterministic. Repeats are how that
variance is handled, not seeds. The generator is seeded and its seed is recorded per
position. The retrofit and attribution runners resume recorded sessions by id, which only
works from the original working directory.

## Limitations

Stated here because the repository is the evidence and a reader is entitled to the same
list the paper carries.

- **Single model.** Everything is `claude-sonnet-5`. This is the primary limitation.
- **The judge shares a family with the subject.** It performs a different task, is blind to
  the arm, sees one response with no context, and applies a rubric frozen in advance and
  written for humans — none of which excludes a shared-family bias. It is not human
  validation. `LABELLING.md` and its harness are here, built and unrun; κ = 0.500 between
  the self-report and the judge is where a human would arbitrate.
- **The retrofit and the judge are post-hoc**, pre-registered before their own runs but
  conceived after the primary result was known.
- **`PREREGISTRATION.md` §2 contradicts itself** on the adversarial paraphrase pairing. The
  threshold table says *minimum RD across C1 paraphrases* (selects C1.b, +0.026); the
  rationale ten lines later says *worst advisory against best direct* (selects C1.c,
  +0.096). `pilot_report.py` implements the first and `RESULTS.md` reports both. On the
  clean metric the disagreement dissolves: all three pairings give +0.022 to +0.063 with
  every interval containing zero.
- **The ±0.10 margin was not derived** from user impact or prior work.
- **Opening-heavy sample**: 73 of 90 positions, no endgames, and mate-in-1 is confounded
  with the decisive severity band.
- **C3 may not be a clean ceiling** — asking for board reconstruction may itself make the
  critical square salient.

**Specified in the protocol and still not run:** the thinking-on secondary arm on a
40-position subset (`PROMPTS.md` §0), and C5, sycophancy with graded severity
(`PREREGISTRATION.md` §5). `PROMPTS.md` §9 budgeted 240 positions across three models; the
reported run is 90 positions on one.

**Deliberately excluded from this repository:** the paper and its LaTeX sources — this repo
is the experiment. Per-call progress logs, whose every field is already in `data/*.jsonl`.

## Licence and use

Model responses are outputs of `claude-sonnet-5` collected in August 2026 under normal API
terms. Session identifiers are present in the records.
