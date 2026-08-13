# Roadmap

Where this study stands after six external reviews, what is decided, and what happens
next in what order. Written 2026-08-11. Update the status column as things land; the
reasoning underneath is meant to survive being read cold in a month.

## Result 3 — 2026-08-13, C6b and the final analyses

**Experimental work is finished.** Nothing below is blocked on an API call.

**C6b — attribution is mixed.** The corrected arm passes every gate C6 failed: subset
**0.9963** against 0.759, parse 1.000, resume 1.000. 270 records, zero errors, $3.57.
**R = P(turn 2 detects | turn 1 missed) = 0.242, 95% CI [0.151, 0.336]** — between the
0.15 reasoning threshold and the 0.40 elicitation one, so `C6B-PREREG.md` §3's **mixed**
branch fires and the pre-registration forbids attributing further.

Both declared confound bounds are reported and they help. P(turn 2 detects | turn 1
detected) is **0.481**, *below* C2's standalone 0.536 — the second question does not buy
general accuracy, so 0.242 is hard to dismiss as a re-analysis artifact.

Descriptively, and not pre-specified: of the 0.433 shortfall between reconstruction
(0.981) and advisory reporting (0.548), about **0.109 (25%) is recoverable by asking
directly** and 0.343 (79%) is not. The shortfall is mostly the model not having the
threat, with a real but minority elicitation component.

**The four free analyses, all on `detected_self`.** Severity is *still* not supported and
now fails differently — band RDs are unordered (+0.011 / +0.007 / −0.037), the interaction
flips sign to −0.048, and C1's slope (+0.100) exceeds C2's (+0.052), the opposite of
`EXPLORATORY.md`'s prediction. The pre-registered GLMM is fitted at last (binomial GEE
clustered on position; statsmodels has no crossed-RE binomial): condition coefficient
−0.0249, p = 0.849, with variant coefficients ~5× larger. Equivalence fires at **±0.075**
and above and fails at ±0.05, so the defensible claim is "smaller than 7.5 points".

**The paraphrase pairing that breached the margin does not survive.** On `detected_self`
all three C1 variants against the best C2 give RD +0.022 to +0.063 with every CI containing
zero. The +0.096 that created the pre-registration contradiction was a `hit_square`
artifact — which changes the Threats section from an argument into a disclosure.

## Result 2 — 2026-08-12, arms C6 and C4

540 calls, zero errors, $6.05.

**C4 — null survives conversational load.** C1 without load 0.548, C4 after fifteen turns
of unrelated chat 0.522, **RD −0.026, 95% CI [−0.093, +0.041]** — inside the ±0.10 margin,
so §7's "null survives load" branch fires. Read it honestly: the point estimate leans
toward suppression and the interval admits up to 9.3 points of it, so the claim is
"load does not suppress by more than about nine points", not "load does nothing".

**C6 — attempted and invalid.** Subset rate 0.759 against a 0.90 threshold. 64 of its 65
failures are squares from turn 1, which sits in context: the extraction prompt's "your
answer above" is ambiguous in a two-answer conversation, so C6 measured a
conversation-level flag list rather than a turn-2 one. **No recovery rate was computed.**
There is an argument that R survives the defect and it is not being made — see
ATTRIBUTION-PREREG.md Amendment 3. A corrected C6 is a one-word prompt change, ~$4, and
needs its own frozen document.

## Result — 2026-08-12

The retrofit ran: 1,944 extractions, zero errors, all validity checks passed, **branch 3**.
`detected_self` gives C1 0.542, C2 0.536, **RD −0.006**, 95% CI [−0.069, +0.058] — inside
the ±0.10 margin. **The equivalence conclusion survives a metric that excludes board
transcription**, which the current draft cannot claim.

The regex probe that motivated this work was wrong (it predicted +0.222; its specificity
against the self-report is 0.633 and it over-fires on C2's tactical register). `hit_square`
is confirmed over-inclusive — specificity 0.382, kappa 0.398 — but its error is roughly
symmetric across arms, which is why the original conclusion held. Full write-up in the
canvas "Retrofit result". Paragraph below is superseded and kept for the record.

## The one-paragraph state of play (superseded — see Result above)

The experiment is sound and every number in `RESULTS.md` reproduces from `data/`. The
problem is upstream of the writing: the primary metric, `hit_square`, counts the critical
square appearing anywhere in the response, including inside a board transcription. A
quarter of its hits never name the square near threat language, and four defensible
operationalisations of "detected" give risk differences of +0.020, +0.036, +0.049 and
+0.222 on the same responses. **The paper's equivalence conclusion is metric-dependent and
currently rests on the most permissive reading.** Everything below is ordered by that.

## Status

| # | step | status | cost | blocks |
|---|---|---|---|---|
| 0 | reviewer synthesis and ranking | done | — | — |
| 1 | artifact repository, public-ready | done | — | 8 |
| 2 | `LABELLING.md` protocol + harness | done, unrun | 15–60 min human | 3 |
| 3 | `RETROFIT-PREREG.md` + frozen scripts | **done, unrun** | — | 4 |
| 4 | run the extraction retrofit | **done — branch 3** | $11.15 actual | — |
| 5 | **rewrite the paper (5b)** | **next — nothing blocks it** | — | 8 |
| 6a | C4 conversational load | done — null survives | $6.05 | — |
| 6b | C6 attribution | done — C6 invalid, **C6b mixed, R = 0.242** | $3.57 | — |
| 6d | free analyses: severity, GLMM, margins, pairings, config | **done** | free | — |
| 6c | v2 remainder: models, positions | deferred to a second paper | ~$140 | 7 |
| 7 | second paper or extended version | blocked on 5, 6 | — | — |
| 8 | submit | blocked on 5 | — | — |

## Step 4 — the extraction retrofit (do this next)

All 1,899 original sessions are still on disk and resumable, so the metric can be fixed on
the data already collected. Each C1/C2 session gets one extra turn asking the model which
squares its own answer singled out. Turn 1 is the original response untouched; sessions
are forked, so nothing in `data/full_raw.jsonl` can change.

Everything is frozen in `RETROFIT-PREREG.md`, including the branch where the retrofit
turns out to be invalid, which is written first deliberately.

```sh
# 6 calls, check the output looks right, then stop
.venv/bin/python run_extract.py --cwd ~/Desktop/ept/chess-salience --probe

# the full retrofit; resumable, safe to interrupt
.venv/bin/python run_extract.py --cwd ~/Desktop/ept/chess-salience

.venv/bin/python score_extract.py
```

`--cwd` must be the **original run's directory**. Sessions are keyed by working directory
and resuming from anywhere else fails. `run_extract.py` checks this before spending
anything.

1,944 calls: 1,620 extractions plus a 162-response subsample run three times to measure how
stable the self-report is at temperature 1.0. Measured at $0.0076/call, so roughly $15 and
15 minutes — the earlier $54 estimate came from six probe calls, one of which was an outlier.

### What comes back, and what it means

`score_extract.py` runs the validity checks first and refuses to report a primary estimate
if any fails. Then one of four branches from `RETROFIT-PREREG.md` §6:

- **Gap opens (95% CI lower > +0.10).** The null was a metric artifact. → step 5a.
- **Equivalence holds (CI inside ±0.10).** The claim survives on a clean metric. → step 5b.
- **Inconclusive.** → step 5c.
- **Retrofit invalid.** Fall back to `LABELLING.md`. → step 2.

## Step 5 — the paper, three versions

Which one gets written is decided by step 4, not by preference. The commitment is in
`RETROFIT-PREREG.md` §7 so that this stays true.

**5a — the gap opens.** The paper inverts and gets better. The salience hypothesis is
supported, and the contribution becomes the demonstration that a plausible, deterministic,
judge-free detection metric manufactured a null in an otherwise clean pre-registered
study. The original result is reported in full as the thing that was wrong. Few people can
publish that because few keep the artifacts to prove it; this repository is the proof.

**5b — equivalence holds.** The paper keeps its conclusion and gains the metric validation
that answers the strongest objection against it. The abstract can then say the result
survives a metric that excludes accidental mentions, which the current draft cannot claim.

**5c — inconclusive.** The paper becomes a metric-sensitivity study: the same responses
yield risk differences from +0.02 to +0.22 depending on operationalisation, and the field
should stop treating string-match detection as neutral.

In all three the current `RESULTS.md` wording has to change, because it is already known
to be metric-dependent.


## Running things without losing them

Two sessions died mid-run during the v1 retrofit. The runs were never the problem — both
resumed with zero duplicate or corrupt records — but a background job started from a Claude
Code session dies when that session is recycled. Detach it:

```sh
nohup .venv/bin/python run_extract.py --cwd ~/Desktop/ept/chess-salience \
  >> /tmp/extract_run.log 2>&1 &
disown
```

Measured throughput is 2.13 calls/s at concurrency 8, $0.0076 per call, so a 10-minute
chunk is ~1,280 calls and ~$9.70. The chunk manifest for v2, sized against those rates and
ordered so every chunk leaves the dataset analyzable, is in the canvas
"Chunked execution plan". Standing rules: always detach; log `usage` not just `cost_usd`;
check `cache_read_input_tokens` (v1's was 0 while 90% of input was an identical preamble);
resume by key, append only; verify between chunks.

## Step 6 — v2 run

Everything the reviewers asked for that is a matter of collecting data rather than
arguing. Roughly $190 across 25,110 calls and 3.3 hours, run in chunks (see "Running
things without losing them" above). Worth doing *after* step 4, because adding
models to a metric you cannot defend multiplies an unresolved measurement error.

| what | why | who asked | cost |
|---|---|---|---|
| two more model families | the only complaint all six reviewers made | all six | ~$60 |
| C4, advisory under ~15 turns of conversational load | the most informative unrun arm; suppression should live here if anywhere | r2 r4 r5 | ~$8 |
| new arm: advisory *then* tactical in one session | separates reasoning from elicitation, which the current design admits it cannot | r1 r2 r4 r5 r6 | ~$8 |
| thinking-on arm on 40 positions | pre-registered, unrun; thinking plausibly turns advisory into de-facto direct | prereg | ~$12 |
| 90 more middlegame/endgame positions | the set is 73/90 opening with no endgames | r1 | Stockfish + run |
| fit the GLMM | pre-registered, never fitted; `(1\|prompt_variant)` is the term readers want | prereg | free |

`prompts/c4_prefix.json` does not exist and has to be written before C4 can run.

## Step 7 — free fixes, do them whenever

None of these need data and all of them are real.

- Scope the title and abstract to `claude-sonnet-5`. Unanimous across six reviewers.
- Replace "contamination-free" with "not drawn from published puzzle sets". Random-walk
  generation makes contamination unlikely, not impossible.
- Report the equivalence result across a **range** of margins instead of defending ±0.10,
  which was never derived from anything. This turns r1's sharpest objection into a figure.
- Cite the artifact repository with a commit hash.
- Add a full configuration table: API model identifier, provider, run dates, sampling
  parameters, max tokens, thinking configuration, retry logic. All recoverable from
  `data/full_raw.jsonl`.
- State that the cluster bootstrap resamples the entire chance correction, nulls included,
  rather than treating the chance rate as fixed. It does; the paper should say so.
- Concede that C3 may itself make the critical square salient in a way C1/C2 do not, which
  weakens "what the model can demonstrably read".
- Name the pre-registration self-contradiction as a process failure rather than a neutral
  disclosure, and say what would be done differently.
- Promote the paraphrase-dominance finding out of Section V. It is the most transferable
  thing in the paper and arguably belongs in the title.
- Discuss the 150-word cap and the tactical-vocabulary exclusion list as possible causes of
  the result, not only as controls.

## Step 2 — hand labelling, and when it is still worth it

`LABELLING.md` and its harness are built and unrun. After step 4 its role changes:

- If the retrofit is **valid**, hand labelling shrinks to about 40 items as a check that
  the model's self-report agrees with a human reading. That comparison is what licenses
  using the automatic metric, and `score_extract.py --labels` computes it.
- If the retrofit is **invalid**, `LABELLING.md` becomes the primary route again and the
  full three-stage plan applies.

So do not start labelling before step 4. It may save an hour, and it cannot cost anything
to wait.

## Open questions that no amount of running fixes

- **Why ±0.10?** It was never derived from user impact or prior work. A margin-sensitivity
  curve sidesteps having to defend one number, but somebody should still say what size of
  drop would matter to a person acting on the advice.
- **Does any of this generalise past chess?** Chess is unusually structured and the board
  state is known to be linearly represented. Advisory dynamics in legal or medical
  settings may behave differently. That is a different paper, and r2 is right to raise it.
- **Is self-report the right operationalisation of "what the model volunteered"?**
  It is defensible and machine-checkable, and it is the same model reporting on itself.
  The honest position is in `RETROFIT-PREREG.md` §8.

## Decisions already taken, so they are not re-litigated

- **Don't rewrite the prose again.** That problem was real, was fixed, and is not the
  bottleneck. The paper reads clean and every number in it checks out.
- **Don't add models before the metric is settled.** Reviewer consensus says otherwise;
  the consensus is wrong on sequencing.
- **Don't submit as is.** Two of six reviewers would accept today. The metric measurement
  in this document is why they should not.
- **Don't drop the paper.** The experiment is sound, the data is real, and every branch
  above leads somewhere publishable.
