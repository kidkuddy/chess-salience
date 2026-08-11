# Labelling protocol — semantic threat detection

**Status: written 2026-08-11, before any response in the sample was read for labelling.**
This document fixes the construct, the sample, the stopping rule and the analysis before
the labels exist, for the same reason `PREREGISTRATION.md` did. Nothing here may be
changed once labelling begins; if something has to change, it gets appended with a date
and a reason rather than edited.

## Why this exists

`RESULTS.md` reports a pre-registered equivalence result on `hit_square`, which fires
when the engine's critical square appears anywhere in the response. Two problems with
that metric surfaced after the run:

1. `robustness.py` measured the chance-hit rate at 0.213 (advisory) and 0.180 (direct).
   Roughly a fifth of the headline is accidental.
2. Responses frequently open by transcribing the board. A response that lists every
   piece and its square hits the critical square by construction, then may go on to
   conclude that nothing is wrong. A worked example is in §6.

So `hit_square` conflates *naming a square* with *reporting a threat*. Those are
different constructs and the paper's claim is about the second one.

A regex probe over threat vocabulary (see §6) puts the advisory-direct difference
anywhere between +0.036 and +0.225 depending on the word list, against +0.020 for
`hit_square` and +0.049 for `hit_move`. That spread is the reason for this exercise. The
probe is not a metric and its number will not appear in any paper. It establishes only
that the conclusion is metric-dependent, and that the metric has never been validated
against human judgement beyond the 50-response audit in `RESULTS.md` §5.

## 1. The construct

> **Detected**: the response identifies the engine's critical square as the location of a
> threat or an opportunity, in a way that a player reading the answer would act on.

The test is behavioural, not linguistic. The question is not whether the response used
the right vocabulary. It is whether a club player who read only this response would look
at that square and understand that something is at stake there.

## 2. The three labels

Every sampled response gets exactly one of:

| label | name | rule |
|---|---|---|
| **2** | detected | The critical square (or a move to/from it) is named **and** the response attributes a threat, a weakness, a capture, a tactic or an opportunity to it. |
| **1** | named only | The critical square appears, but only as board transcription, as an item in an undifferentiated list of candidate ideas, or in a statement that dismisses it. |
| **0** | absent | The critical square is never named, in any notation. |

A fourth marker, **`?` unsure**, is available during labelling. Every `?` must be resolved
to 0, 1 or 2 by the second rater before analysis. An unresolved `?` is dropped and the
count of dropped items is reported.

### Bright lines

These are fixed now so that the hard cases are decided by rule and not by mood. They were
written from the failure modes visible in aggregate statistics, not from reading sampled
responses.

- **Board transcription is not detection.** "White: Ra1, Qb1, Nd4, pawns a3, c4, e4" is a
  **1**, however accurate, and regardless of what the response says later about other
  squares.
- **Dismissal is not detection.** "Your bishop on c4 is fine" or "c4 is defended, so no
  issue" is a **1**. The model named the square and got the assessment wrong.
- **An undifferentiated candidate list is not detection.** "Ideas include Bf3, Qf3, or
  something on c4" with no assessment attached to c4 is a **1**. If the response singles
  the square out for a reason, it is a **2**.
- **The threat may be either direction.** The critical square can be the site of the
  model's own hanging piece (vulnerability) or of a capture it can make (opportunity).
  Both count as **2**.
- **Correct square, wrong reason still counts.** If the response says "c4 is hanging" and
  the engine says c4 is a mate-in-1 square, that is a **2**. The construct is whether the
  square was surfaced as significant, not whether the model's chess analysis was right.
- **Hedged detection counts.** "c4 might be loose, worth checking" is a **2**. Confidence
  is not part of the construct.
- **Vocabulary is not required.** A response that says "you can just take on c4 and win a
  piece" is a **2** without using any of the words in the probe's lexicon. This is exactly
  the case the regex cannot see and the human can.
- **Wrong-colour or wrong-piece claims about the right square** are still **2**, by the
  same logic as "correct square, wrong reason."
- **Only the engine's critical square counts.** A response that finds a different, real
  tactic elsewhere on the board and misses the critical square is a **0** or **1**. This
  study measures detection of a specific labelled threat, not general tactical ability.

## 3. Blinding

The labelling file carries, per item: the FEN, an ASCII board, the side to move, the
engine's critical square, the engine's accept-move list, and the response text.

It does **not** carry: which arm the response came from, which paraphrase, which repeat,
the prompt itself, or any scorer output. Items are shuffled under a fixed seed. The key
that maps item to arm lives in a separate file that must not be opened until labelling is
finished.

The labeller knows which square is critical. That is unavoidable, since the construct is
about a specific square, and it is the same exposure the `RESULTS.md` §5 audit had. It
creates a risk of reading detection into ambiguous prose; the bright lines in §2 and the
second rater in §5 are the mitigations.

## 4. Sample

The unit of analysis is the position, matching the primary analysis in
`PREREGISTRATION.md` §2, so the sample is drawn to preserve the pairing: every position
contributes to both arms.

Per stage, for each of the 90 positions and each of C1 and C2, one paraphrase is drawn
and one repeat is drawn at random from that cell. Each stage adds 90 × 2 = 180 items.

Paraphrases are assigned by rotation rather than at random: the positions are shuffled
once under the fixed seed, then position *i* takes the base order rotated by *i* mod 3.
With 90 positions each rotation class holds exactly 30, so every stage contains exactly
30 of each paraphrase in each arm, and across the three stages every (position, arm) cell
is covered by a, b and c exactly once. Verified in `build_labelset.py`.

| stage | items added | cumulative | labels per position per arm |
|---|---:|---:|---:|
| 1 | 180 | 180 | 1 |
| 2 | 180 | 360 | 2 |
| 3 | 180 | 540 | 3 |

### Why three stages and not one batch

Simulating the cluster bootstrap on this design gives median 95% CI half-widths of
±0.128 at stage 1, ±0.094 at stage 2 and ±0.081 at stage 3. That asymmetry matters:

- **To show a large gap**, the observed RD has to exceed roughly +0.23 to clear the
  margin at stage 1, +0.19 at stage 2. A dry run of the pipeline on synthetic labels
  produced RD = +0.211 with a 95% CI of [+0.078, +0.344] at stage 1, which does **not**
  clear +0.10. Expect stage 2 to be necessary even if the effect is large.
- **To defend equivalence**, the interval has to fit inside ±0.10, which needs a
  half-width below 0.10 and therefore stage 3, and even then only if the point estimate
  sits near zero.

Budget for stage 2 and hope to avoid stage 3.

So the cost of labelling depends on which way the answer falls, and there is no reason to
spend stage 3 effort to establish a result that stage 1 already settles.

## 5. Stopping rule (pre-specified)

Run the stages in order. After each, compute the primary estimate in §7 and apply:

- **95% CI lower bound > +0.10** → stop. The advisory arm detects materially less often
  than the direct arm.
- **95% CI entirely inside ±0.10** → stop. Equivalence holds on the validated metric.
- **Anything else** → continue to the next stage. After stage 3, stop and report whatever
  the interval is, including "inconclusive".

Sequential stopping inflates error rates relative to a single fixed-n analysis. This is
accepted deliberately: the study reports intervals rather than a decision at a
significance threshold, the number of looks is fixed at three in advance, and the
alternative (always paying for 540 labels) has its own cost. The stage at which labelling
stopped must be reported alongside the result.

### Reliability

60 items are double-labelled by a second rater, drawn across whichever stages were run.
Cohen's kappa on the three-level scale is reported. Disagreements are resolved by
discussion against §2, and the pre-resolution kappa is the one reported. If kappa falls
below 0.6, the bright lines in §2 are insufficient and the protocol needs revision before
the labels are used, which is itself a reportable finding.

## 6. What is already known, and by whom

Full disclosure, because it affects how this protocol should be read.

Before writing this document I read two full responses while diagnosing the metric, and I
ran an automated regex probe over all 1,620 C1/C2 responses. The probe's aggregate result
is known: it puts the advisory-direct difference at +0.222 under a broad threat lexicon,
+0.225 with prompt-echoed words removed, and +0.036 under a narrow lexicon. The bright
lines in §2 were written in response to the failure modes that probe exposed, principally
board transcription and dismissal.

The worked example that motivated the transcription rule, a response scored
`hit_square = True` on critical square c4:

> **FEN breakdown:** White: Ra1, Qb1, Nd4, Bf1, Ke1, pawns a3, c7, e4, f2, g2, h4.
> Black: Ra8, Bc8, Bd6, Nh6, Kf7, Qe5, pawns b7, **c4**, f5, g3, h5. […]
> Given no clean mate is found, answer: no mate in one

The human labeller has not seen the probe's per-response output and will not see it
before labelling. The probe's per-item labels are held out and compared against the human
labels in §7 as a validation of the probe, not as an input to it.

## 7. Analysis plan

Fixed before the labels exist.

**Primary.** Position-level rate of label == 2 in each arm. Paired risk difference
RD = p(C2) − p(C1) over positions. Cluster bootstrap over positions, 10,000 resamples,
percentile, reporting 90% and 95% intervals. This mirrors `PREREGISTRATION.md` §2 exactly,
with the metric swapped.

**Secondary.**
- The same estimate with labels 1 and 2 collapsed, which approximates `hit_square` and
  should reproduce it. A large discrepancy means the sampling or the labelling is off.
- Per-paraphrase rates, so the paraphrase-dominance finding can be re-tested on the
  validated metric.
- Rate of label == 1 per arm: how much of `hit_square` is transcription in each arm. If
  this differs by arm it is itself a finding, since it means the metric's inflation is not
  symmetric.

**Metric validation.** Against the human label as reference, for each of `hit_square`,
`hit_move` and the regex probe: sensitivity, specificity, and Cohen's kappa. This is what
lets the paper say how good its primary metric was rather than asserting it.

**Status of these analyses.** All of it is post-hoc relative to `PREREGISTRATION.md`. It
is a validation of the primary metric, not a new confirmatory test, and it will be
reported as such. The ±0.10 margin is reused for continuity with the original analysis;
`RESULTS.md` will state that the margin was never derived from an external criterion, which
is a separate open criticism.

## 8. What each outcome means for the paper

Committed now, so that the writing follows the labels rather than the labels being read
in light of a preferred write-up.

- **RD inside ±0.10.** The equivalence claim survives on a validated metric. The paper
  keeps its conclusion and gains a metric-validation section that answers the strongest
  objection against it.
- **RD above +0.10.** The pre-registered null was an artifact of a permissive metric. The
  paper inverts: the salience hypothesis is supported, and the contribution becomes the
  demonstration that a plausible, deterministic, LLM-judge-free detection metric
  manufactured a null in an otherwise clean pre-registered study. The original result is
  reported in full as the thing that was wrong.
- **Interval straddling +0.10.** Neither claim. The paper becomes a metric-sensitivity
  study: the same data yields risk differences from +0.02 to +0.22 depending on how
  detection is operationalised, and no operationalisation is privileged. This is the least
  satisfying outcome and still a publishable one.

In all three cases the equivalence result as currently written in `RESULTS.md` cannot
stand unqualified, because it is now known to be metric-dependent.

## 9. Running it

```sh
.venv/bin/python build_labelset.py --stage 1     # writes tasks, key, and label_ui.html
open label_ui.html                                # label; exports data/labels_stage1.json
.venv/bin/python score_labels.py --stages 1      # unblinds and applies §5 and §7
```

`build_labelset.py` refuses to overwrite an existing key file, so a stage cannot be
silently redrawn after its labels exist.
