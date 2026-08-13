# Pre-registration — blinded judge validation of `detected_self`

**Status: FROZEN 2026-08-13, before any judge call was made.**

Fifth frozen document in this study. Same rule as the other four: nothing below may be
edited after the first call; corrections are appended with a date and a reason.

## 1. The gap this fills, and the one it does not

`detected_self` is the model reporting on which squares its own answer singled out. Three
internal checks already constrain it:

| check | value |
|---|---|
| subset — flagged squares actually occur in the response text | 0.985 (0.996 in C6b) |
| parse rate | 0.997 |
| test–retest, 162 responses re-extracted three times, all three agree | 0.895 |
| `hit_square` sensitivity against it — it never fires on an absent square | 0.999 |

All four are **reliability**, not **validity**. None of them shows that what the model
calls "singling a square out" is what a reader would call detecting a threat. That is a
construct question and it needs a judgement from outside the self-report.

`LABELLING.md` specifies human labelling and remains the stronger instrument. It is not
being run. **This document does not claim to replace it** — it substitutes a weaker,
cheaper, larger-n instrument and says so in the paper.

## 2. The instrument

An independent judge call applying the `LABELLING.md` §2 rubric verbatim to each response.

**Fresh session per call. No resume, no fork.** The judge must not see the conversation
that produced the response, or it would see the arm.

**What the judge sees:** the ASCII board, the FEN, side to move, the engine's critical
square, the engine's accepted moves, and the response text.

**What the judge never sees:** which arm the response came from, which paraphrase, which
repeat, the prompt that produced it, `detected_self`, `hit_square`, `hit_move`, the probe,
or any other response.

**Output:** a single character, `2`, `1` or `0`, per `LABELLING.md` §2 — which is reused
unchanged, including its bright lines, so this instrument and the human one measure the
same construct and their results are directly comparable if the labelling is ever run.

## 3. Sample

**Every C1 and C2 response with a first extraction: all 1,620.** No sampling, so no
sampling design to defend and no stopping rule. Plus a 162-response subsample judged three
times for stability, matching `RETROFIT-PREREG.md`'s design exactly. 1,944 calls, ~$12.

## 4. Validity gates, checked before any estimate is reported

- **parse ≥ 0.98** — the judge returns exactly one of `2`, `1`, `0`.
- **stability ≥ 0.80** — of the 162 thrice-judged responses, the fraction where all three
  agree. Set below the self-report's own 0.895 because a third-party judgement of someone
  else's prose is a harder task than reporting on your own.
- **blinding intact** — verified in code: the judge prompt is asserted to contain no arm
  label, no prompt template text, and no scorer field.

If any gate fails, no agreement estimate is reported and `detected_self` stands on its
internal checks alone, with §7's limitation stated more strongly.

## 5. Primary estimand

**Cohen's kappa between `detected_self` and (judge label == 2)**, over all 1,620.

## 6. Branches, fixed now

- **κ ≥ 0.60.** `detected_self` is licensed. The level claims — 0.548 detection, the
  0.981 → 0.548 shortfall, R = 0.242 — are reported as stated, with the judge validation
  as their warrant and §7 as their caveat.
- **0.40 ≤ κ < 0.60.** Moderate. The level claims are reported with the judge rate beside
  them, and the paper states that the two instruments disagree on roughly which responses
  count. The equivalence result is unaffected either way — see §8.
- **κ < 0.40.** `detected_self` is **not** licensed as a detection measure. The level
  claims come out, human labelling returns as the only route, and this document's failure
  is reported the way `ATTRIBUTION-PREREG.md` §5's was.

## 7. The limitation, declared in advance

The judge is `claude-sonnet-5` — **the same model that produced the responses and the same
model that self-reported.** Three things separate the measurements, and none of them makes
it a human:

1. The judge performs a **different task**: third-party judgement of given text against a
   rubric, not introspection about what it meant.
2. The judge is **blind to the arm** and sees one response with no conversational context.
3. The rubric is **frozen and external**, written before any of this and for a human.

A shared-family bias that inflates agreement is not excluded by any of that. The paper must
say so in Threats, in those words, and must not describe this as human validation. If the
result matters to a reader, `LABELLING.md` is built, blinded and ready, and 40 human labels
would settle it.

## 8. What this cannot change

**The primary equivalence result does not depend on the outcome here.** `hit_square` has
specificity 0.382 and still recovered the correct risk difference, because its error is
close to symmetric across arms (+0.273 C1, +0.298 C2). A metric can be a poor detector and
an unbiased comparator. What the judge validation bears on is the **level** claims, which
are the ones that need the metric to be right in absolute terms.

## 9. Secondary, reported regardless of branch

- Sensitivity, specificity and kappa of `hit_square`, `hit_move`, the regex probe **and**
  `detected_self`, against the judge label as reference — the same table the retrofit
  produced against `detected_self`, now with an outside reference.
- The **primary risk difference recomputed on the judge label**, cluster bootstrap over
  positions, 10,000 resamples. This is a third independent operationalisation of detection
  and its agreement or disagreement with the other two is reportable either way.
- Rate of label 1 per arm — how much of `hit_square` is transcription in each arm, per
  `LABELLING.md` §7. If it differs by arm, the metric's inflation is not symmetric, which
  would matter to §8.

## 10. Output

`data/judge_raw.jsonl`, append-only, resumable by `(position_id, condition, variant,
repeat, judge_repeat)`. Analysis frozen in `score_judge.py`, written before the run.
