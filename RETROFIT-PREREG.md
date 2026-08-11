# Pre-registration — self-report extraction retrofit

**Status: FROZEN 2026-08-11, before any extraction call was made.**

Committed together with `run_extract.py` and `score_extract.py`, which implement exactly
what is written here. Nothing below may be edited after the first call; corrections get
appended with a date and a reason. The point of freezing an analysis that is being added
*after* seeing the primary result is that otherwise this is indistinguishable from
changing the metric until the answer moves.

## 1. Why

`RESULTS.md` reports equivalence on `hit_square`, which fires when the engine's critical
square appears anywhere in the response. Three facts about that metric are now established:

- The chance-hit rate is 0.213 (advisory) and 0.180 (direct) — `RESULTS.md` §9.1.
- Of the 1,334 responses scored `hit_square = True`, 341 (25.6%) never name the critical
  square anywhere near threat language.
- Responses routinely open by transcribing the board, which hits the critical square by
  construction. Worked example in `LABELLING.md` §6.

So `hit_square` conflates *naming a square* with *reporting a threat*. The paper's claim
is about the second.

`LABELLING.md` settles this by hand. This document settles it automatically, and the two
are complementary rather than alternatives: the hand labels validate the automatic metric.

## 2. The instrument

Every response in the original run was produced in its own Claude Code session, and all
1,899 session transcripts are still on disk. Each C1 and C2 session is resumed and given
one additional user turn. The turn-1 response is the original, byte for byte; nothing is
re-generated and nothing is reconstructed.

Sessions are resumed with `fork_session=True`, so the original transcript is not mutated.

### The extraction turn, verbatim and frozen

```
Without re-examining the position and without any new analysis, list only the
squares your answer above already singled out as needing attention: a threat, a
weakness, a capture, or an opportunity. One square per line, algebraic. If your
answer singled out none, write NONE. Output nothing else.
```

The construct it names — threat, weakness, capture, opportunity — is deliberately the
same wording as `LABELLING.md` §1, so the self-report and the human labels measure the
same thing and their agreement is meaningful.

### Configuration

Identical hygiene to the original run (`run_gate.options()`): same system prompt, no
setting sources, no hooks, no plugins, no tools, no MCP, thinking disabled, temperature
default, `max_turns=1`, model `claude-sonnet-5`. The working directory must be the
original run's directory, because sessions are keyed by cwd; running from anywhere else
silently fails to resume.

### Scope

All 1,620 non-error C1 and C2 responses. Not C0, which has no position, and not C3, which
is a reconstruction task rather than a detection one.

Additionally, a **10% subsample (162 responses, drawn under a fixed seed) receives the
extraction turn three times** rather than once, to measure how stable the self-report is
at temperature 1.0. Reported as the extraction's own reliability.

## 3. The metric

> **`detected_self`**: the engine's critical square appears in the extracted list.

Parsing is deterministic: split on lines, strip punctuation and markup, keep tokens
matching `^[a-h][1-8]$`, lowercase. `NONE` yields the empty set. Anything unparseable is
recorded as a parse failure and reported, not silently dropped.

## 4. Validity checks, with thresholds fixed now

These decide whether the retrofit is usable at all. They are run before the primary
estimate is looked at.

| check | what it tests | threshold |
|---|---|---|
| **subset rate** | flagged squares ⊆ squares turn 1 mentioned | **≥ 0.90.** Below that, the extraction turn is doing new analysis rather than reporting, and the retrofit is invalid |
| parse rate | extraction is machine-readable | ≥ 0.98 |
| resume rate | sessions actually resumed | ≥ 0.98; failures listed by session id |
| extraction stability | on the 3× subsample, all three extractions agree on `detected_self` | reported, not gated |
| flagged-count balance | mean squares flagged per arm | reported. This is the new equivalent of the 150-word cap check, and if the arms differ materially the chance correction in §5 is doing real work |

The subset check is the one that matters. It is the reason to prefer self-report over an
external judge: it is machine-verifiable, whereas "did the judge read it correctly" is not.

## 5. Analysis plan

Fixed before the extraction data exists. Mirrors `PREREGISTRATION.md` §2 with the metric
swapped, so the two are directly comparable.

**Primary.** Position-level rate of `detected_self` per arm. Paired risk difference
RD = p(C2) − p(C1) over positions. Cluster bootstrap over positions, 10,000 resamples,
percentile, 90% and 95% intervals.

**Chance correction.** The permutation null from `robustness.py` §1, recomputed on the
*flagged* sets rather than on all mentioned squares. Reported alongside the raw estimate.

**Secondary.**
- Per-paraphrase rates, so the paraphrase-dominance finding is re-tested on the new metric.
- `hit_square` restricted to the same responses, as a consistency check against `RESULTS.md`.
- The rate at which `hit_square` fires while `detected_self` does not, per arm. This is the
  transcription artifact measured directly, and if it differs by arm the old metric's
  inflation is asymmetric, which is a finding in its own right.

**Agreement.** Sensitivity, specificity and Cohen's kappa of `hit_square`, `hit_move` and
the `LABELLING.md` §6 regex probe against `detected_self`. If human labels from
`LABELLING.md` exist, the same three statistics for `detected_self` against them — that
comparison is what licenses using the automatic metric in place of hand labelling.

## 6. Decision rules

Applied to the primary estimate, in this order.

1. **If any validity check in §4 fails its threshold**, the retrofit is reported as
   attempted and invalid, and the metric question returns to `LABELLING.md`. The failed
   check is reported with its number. This branch is written down first deliberately: it
   is the one that costs the most to admit.
2. **95% CI lower bound > +0.10** → the advisory arm detects materially less often than
   the direct arm on a metric that excludes transcription. The pre-registered null was a
   metric artifact.
3. **95% CI entirely inside ±0.10** → equivalence survives on the clean metric, and the
   paper's conclusion is substantially stronger than it is today.
4. **Otherwise** → inconclusive; report the interval and the metric-sensitivity range.

## 7. What each outcome does to the paper

Committed now, so the write-up follows the data.

- **Branch 2 (gap opens).** The paper inverts. The salience hypothesis is supported, and
  the contribution becomes the demonstration that a plausible, deterministic,
  judge-free detection metric manufactured a null in an otherwise clean pre-registered
  study. The original result is reported in full as the thing that was wrong, because that
  is the whole point.
- **Branch 3 (equivalence holds).** The paper keeps its conclusion and gains the metric
  validation that answers the strongest objection against it. The abstract can then say
  the result survives a metric that excludes accidental mentions, which is a claim the
  current draft cannot make.
- **Branch 4 (inconclusive).** The paper becomes a metric-sensitivity study: the same
  responses yield risk differences from +0.02 to +0.22 depending on how detection is
  operationalised, and the field should stop treating string-match detection metrics as
  neutral.
- **Branch 1 (retrofit invalid).** Report it, and fall back to hand labelling. A failed
  method that was pre-registered and reported is not a wasted one.

In every branch the equivalence result as written in `RESULTS.md` today cannot stand
unqualified, because it is already known to be metric-dependent.

## 8. Threats to this design, declared in advance

- **Self-report bias.** The model is reporting on its own prior output, and it may be
  more willing to claim it flagged something than it was to flag it. This inflates
  `detected_self` in both arms; it biases the *difference* only if it acts asymmetrically,
  which the flagged-count balance check in §4 is there to expose. The subset check bounds
  the related failure of inventing squares outright.
- **Same model, same family.** This is not an independent judge. It is a weaker claim than
  external adjudication and a stronger one than string matching, and it is the only option
  that keeps the paper's "no LLM judge in the scoring path" property intact for the
  primary outcome, since the model is reporting its own claim rather than evaluating
  someone else's.
- **Post-hoc by construction.** This analysis was designed after the primary result was
  known. That is why the prompt, the thresholds, the analysis and the decision rules are
  frozen here, before any call, and why branch 1 is written first.
- **Temperature.** Extraction runs at the same temperature as the original run, so it is
  stochastic. The 3× subsample in §2 measures how much that matters rather than assuming
  it away.
- **Turn-1 integrity.** Nothing in this procedure can alter the original responses; they
  are already recorded in `data/full_raw.jsonl` and the sessions are forked, not resumed
  in place. Every number in `RESULTS.md` remains reproducible from the original artifacts
  whatever this produces.

## 9. Cost and provenance

Estimated from six live test extractions: $0.0278 per call, so roughly **$50** for
1,620 + 162 calls, and about 20 minutes of wall clock at the original run's concurrency.

Output goes to `data/extract_raw.jsonl`, one record per extraction, carrying the session
id, the original response's identifiers, the raw extraction text, the parsed squares, and
the validity-check fields. The runner is resumable and never rewrites an existing record.
