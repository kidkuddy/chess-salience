# chess-salience

A pre-registered behavioural test of whether advisory framing suppresses what a language
model reports about a chess position it can demonstrably read.

The question: a deployed assistant is usually asked something open ("what should I be
thinking about here?") rather than interrogated ("is anything hanging?"). If models hold
back what they represent, advisory framing is where that should show up. Holding the
position fixed and varying only the framing, does the model still name the critical square?

On the pre-registered metric the answer is that it does, at statistically equivalent
rates. That null was registered in advance as a publishable outcome, against the
hypothesis this study was built to confirm.

**That result is currently under challenge from its own metric.** `hit_square` counts the
critical square appearing anywhere in the response, and a quarter of its hits are board
transcription rather than detection. Depending on how "detected" is operationalised the
same data gives a risk difference anywhere from +0.020 to +0.225. `LABELLING.md` is the
protocol for settling it by hand, and it commits in advance to inverting the conclusion if
the labels go that way. Read the headline below with that pending.

This repository holds the whole experiment: the frozen protocol, the generator, the prompts,
the scorer, the raw model outputs, the analysis, and the results. Every number in
`RESULTS.md` is reproducible from `data/` with the scripts here.

## Headline result

| | |
|---|---|
| advisory detection, p(C1) | 0.814 |
| direct detection, p(C2) | 0.833 |
| risk difference | +0.020, 90% CI [−0.015, +0.054] |
| pre-registered equivalence margin | ±0.10 — **inside it** |
| chance-corrected risk difference | +0.034, 90% CI [−0.009, +0.075] — still inside |
| board-reconstruction ceiling | 0.981 |
| position-withheld floor | 0.000 (a refusal, not a guess; see `RESULTS.md` §2) |
| calls / errors / cost | 1,899 / 0 / $14.40 |

The secondary finding is the more portable one: which paraphrase was used moved detection
about three times as much as which framing was used. Detection ranges 0.781 to 0.852 across
three advisory wordings, against a 0.020 gap between arms.

## Reproducing

```sh
python -m venv .venv && .venv/bin/pip install -r requirements.txt
brew install stockfish                        # only needed to regenerate positions

.venv/bin/python pilot_report.py --raw data/full_raw.jsonl \
    --positions data/full_positions.jsonl --json /tmp/check.json --sims 4000
.venv/bin/python exploratory_report.py        # the severity follow-up
.venv/bin/python robustness.py                # chance correction, pairings, branch power
.venv/bin/python tests/test_scorer.py         # scorer unit tests + hand-label agreement
.venv/bin/python tests/test_prompts.py        # prompts match PROMPTS.md verbatim
```

Re-running the model calls (`run_pilot.py`, `run_gate.py`) needs API credentials and will
not reproduce the recorded outputs: temperature is 1.0 and hosted models are not
deterministic. Repeats are how that variance is handled, not seeds. The generator
(`gen_positions.py`) is seeded and its seed is recorded per position.

## Map

**Frozen protocol, written before data.** Read these first; the analysis scripts read
their thresholds off these documents rather than restating them.

| file | what it fixes | written |
|---|---|---|
| `GAP.md` | the gap sentence the study exists to satisfy, with its citations | 2026-08-04 |
| `PREREGISTRATION.md` | arms, metrics, estimators, thresholds, the three outcome branches | drafted 08-04, frozen 08-05T18:02+01:00 |
| `PROMPTS.md` | every prompt verbatim, the exclusion word list, the cell budget | drafted 08-04, frozen 08-05T18:02+01:00 |
| `EXPLORATORY.md` | the severity hypothesis and its support criteria, committed before its confirming positions existed | 2026-08-09 |

The ordering those dates assert is checkable here rather than taken on trust. This
repository carries the original 17-commit history, so `git log` shows
`docs(exploratory): pre-specify condition x severity before the full run exists` landing
before `results(chess-salience): equivalence branch fires`, and the pre-registration
freezing before the gate runner exists. Two caveats on that history: the paper's commits
were filtered out when this repository was split off, and `data/` was gitignored in the
original working repo, so the raw outputs arrive in a single commit and their timestamps
are not independently attested by git.

**Instruments.**

| file | role |
|---|---|
| `gen_positions.py` | random-walk generator, Stockfish labelling, band sampling |
| `prompts.py` | renders the frozen templates; substitutes only the position block |
| `scorer.py` | deterministic square/move extraction and board reconstruction. No LLM judge |
| `run_gate.py` | the C3 screening gate that had to pass before the study was allowed to run |
| `run_pilot.py` | the run driver, used for both the pilot and the full run |
| `audit_scorer.py` | samples responses for blind hand-labelling |

**Analysis.**

| file | produces |
|---|---|
| `gate_report.py` | the gate decision |
| `pilot_report.py` | the confirmatory analysis, per `PREREGISTRATION.md` §2–§4 |
| `exploratory_report.py` | the severity follow-up, per `EXPLORATORY.md` |
| `robustness.py` | chance correction, both paraphrase pairings, branch power, Wilson intervals |
| `RESULTS.md` | the write-up of all of the above |

**Data.** Nothing here is derived by hand.

| file | contents |
|---|---|
| `data/full_raw.jsonl` | 1,899 records: every prompt, response, score, cost and duration |
| `data/full_positions.jsonl` | the 90 reported positions with engine labels |
| `data/full_report.json` | confirmatory analysis output |
| `data/exploratory_full.json` | severity follow-up output |
| `data/robustness.json` | robustness analyses (`RESULTS.md` §9) |
| `data/pilot_*` | the pilot. It crashed partway: 568 of 849 calls, 23 position pairs |
| `data/gate_*` | the C3 screening gate, 90 calls over 30 positions |
| `data/audit_*` | the 50-response blind scorer audit and its labels |

## What is not here, and why

Listed because a reader is entitled to know what was specified and not done.

**Specified in the protocol, not run.**

1. **C4**, the advisory arm placed after roughly fifteen turns of unrelated conversation
   (`PROMPTS.md` §7). The most informative of the omissions and the obvious next run.
   Its conversational prefix was to live at `prompts/c4_prefix.json`, which was never
   written.
2. **The thinking-on secondary arm** on a 40-position subset (`PROMPTS.md` §0). Matters
   because extended thinking plausibly turns the advisory arm into a de-facto direct one.
3. **C5**, sycophancy with graded severity (`PREREGISTRATION.md` §5, which rules to keep it
   in the study).
4. **The GLMM** `detected ~ condition * format + (1|position) + (1|model) +
   (1|prompt_variant)` (`PREREGISTRATION.md` §2). The model and format terms are unusable
   with one model and one format; `(1|position)` and `(1|prompt_variant)` are estimable and
   were not fitted. This one was an oversight rather than a resource decision.
5. **Scale.** `PROMPTS.md` §9 budgets 240 positions across 3 models. The reported run is 90
   positions on one model, `claude-sonnet-5`. The 90 is justified on its own terms:
   `PREREGISTRATION.md` §4 sizes N from the pilot, and the full run's own power curve puts
   the requirement at 60. The single model is not justified, and is the study's primary
   limitation.

**Deliberately excluded from this repository.**

- The paper, its LaTeX sources and its build artifacts. This repo is the experiment.
- Per-call progress logs. Every field they carried is already in `data/*.jsonl`.

## Verification status

Every quantitative claim in `RESULTS.md` was re-checked against `data/` on 2026-08-11:
run totals, cost, position-set composition, the six prompt wordings against `PROMPTS.md`,
the C1 exclusion word list, the gate, the ceiling metrics, the primary rates, the McNemar
cell counts, the secondary metric, the floor, and the scorer audit. All agreed.

Also checked: the three position sets (gate, pilot, full) share no FEN, so no position
appears in more than one phase, and all 90 reported FENs are distinct.

The citations in `GAP.md` were re-verified against the arXiv abstracts. They hold, with one
exception: LLM CHESS (2512.01992) is described there as reporting "move quality and blunder
rate". Its abstract reports move quality but never mentions blunder rate.

Two documentation inconsistencies worth knowing about:

- `PREREGISTRATION.md` §2 specifies the adversarial paraphrase pairing twice and the two do
  not agree. The threshold table says *minimum RD across C1 paraphrases*, which selects
  C1.b (+0.026). The rationale ten lines later says *worst advisory against best direct*,
  which selects C1.c (+0.096). `pilot_report.py` implements the first. `RESULTS.md` §9.2
  reports all three rows and does not hide the second.
- `tests/test_scorer.py`'s docstring calls its 15 hand-labelled cases "the source of the
  scorer-reliability figure reported in RESULTS.md". They are not. That figure is 49/50
  from the blind audit in `data/audit_labels.json`. The tests are a separate, earlier check.

## Licence and use

Model responses in `data/full_raw.jsonl` are outputs of `claude-sonnet-5` collected in
August 2026 under normal API terms. Session identifiers are present in the records.

## Where this is going

`ROADMAP.md` is the ordered plan: what is done, what is next, what each step costs and
what it unblocks. Read it first if you are picking this up cold.

The short version: the primary metric is under challenge from its own permissiveness, an
automatic fix is frozen and ready to run in `RETROFIT-PREREG.md`, and which paper gets
written is decided by that result rather than by preference.

## Metric validation (in progress, added 2026-08-11)

The primary metric `hit_square` fires when the engine's critical square appears anywhere
in the response. Two facts about it surfaced after the run:

- `robustness.py` puts the chance-hit rate at 0.213 (advisory) and 0.180 (direct).
- Responses often open by transcribing the board, which hits the critical square by
  construction. Of the 1,334 responses scored `hit_square = True`, 341 (25.6%) never name
  the critical square anywhere near threat language.

A regex probe over threat vocabulary puts the advisory-direct difference between +0.036
and +0.225 depending on the word list, against +0.020 for `hit_square` and +0.049 for
`hit_move`. The conclusion in `RESULTS.md` is therefore metric-dependent, and the metric
has never been validated against human judgement beyond the 50-response audit in §5.

`LABELLING.md` fixes a protocol for settling that by hand, written before any sampled
response was read: the construct, the bright lines, a position-paired stratified sample,
a three-stage stopping rule, and what each outcome means for the paper. It commits in
advance to inverting the paper's conclusion if the labels go that way.

| file | role |
|---|---|
| `LABELLING.md` | the protocol. Read before touching anything else here |
| `build_labelset.py` | draws a stage, blinds it, writes the tasks, the sealed key and the UI |
| `label_ui.template.html` | offline labelling tool; no network, no dependencies |
| `score_labels.py` | unblinds, applies the stopping rule, validates each metric against the labels |
| `data/label_tasks_stage1.json` | stage 1: 180 items, 90 per arm, 30 per paraphrase per arm |
| `data/label_key_stage1.json` | the mapping back to arm and paraphrase. Committed before labelling so the draw is timestamped; not to be opened until the labels exist |

```sh
.venv/bin/python build_labelset.py --stage 1
open label_ui.html                      # 2 / 1 / 0 / u, exports labels_stage1.json
.venv/bin/python score_labels.py --stages 1
```

Until this is done, the equivalence result in `RESULTS.md` should be read as holding for
`hit_square` specifically rather than for threat detection generally.
