# Pre-registration — frozen thresholds

**Status: APPROVED AND FROZEN. Approved 2026-08-05T18:02+01:00.**
Drafted 2026-08-04, written before any model call and before the §1 gate result existed. Nothing here
is a post-hoc number. §1 was approved and executed on 2026-08-04 (result: PASS, mean
`critical_square_correct` 0.967, Wilson95 [0.907, 0.989], parse rate 1.000, n=90); §2–§6 were read and
approved unchanged on 2026-08-05, before any C0/C1/C2 call was made. From this commit the prompt set,
metrics, estimators and thresholds below are frozen; changes require a new commit that says what
changed and why, and any analysis run after such a change is labelled exploratory.

GAP.md commits the study to "a large C2 − C1 gap" and "C1 ≈ C2 at the floor" without saying what
large or at-the-floor mean. That is the hole this file fills. Once the numbers below are approved,
this file gets a timestamped commit and the arms and metrics are frozen; the full run does not start
before that commit exists (spec hard rule).

Every threshold below is stated with the reasoning, because the reasoning is what a reviewer
attacks, not the digit.

---

## 1. Gate threshold — C3 board reconstruction (today, 30 positions, sonnet)

**The measure that gates is `critical_square_correct`** — did the model place the right piece on the
one square the whole experiment turns on — **not** `exact_board`.

This is a deliberate choice and it needs defending. Full-board reconstruction is known to be close to
zero for general chat models, and gating on it would kill the study over a capability the thesis does
not require. The salience claim needs only this: *when C1 fails to mention square X, the model
demonstrably knew what was on square X.* That is `critical_square_correct` and nothing more.

| outcome | condition | consequence |
|---|---|---|
| **PASS** | mean `critical_square_correct` **≥ 0.70**, Wilson 95% lower bound ≥ 0.50, and parse rate ≥ 0.80 | build the full runner; C3 stands as the perception ceiling |
| **GREY** | 0.40 ≤ mean < 0.70 | proceed, but C3 is demoted from "ceiling" to a per-position covariate; the paper claims the gap *conditional on the square being reconstructed*, on the reconstruction-correct subset. Weaker claim, still a paper. |
| **FAIL** | mean < 0.40, or Wilson 95% upper bound < 0.50 | **stop.** The finding is "no reliable board state", which is the negative branch GAP.md already accepts. Write it up, do not improvise a rescue. |

**Why 0.70.** Above this, a C1 miss cannot be waved away as the model not knowing what stands on the
square — the perception explanation is available for under a third of items, and the dissociation is
attributable. **Why 0.40.** Below it, the majority of C1 misses have a perception explanation
available, and no amount of C1/C2 gap separates "did not represent" from "did not surface" — which
is the one thing the study exists to separate. **Why a grey band at all.** The realistic outcome is
partial board state, and forcing that into pass/fail would either overclaim or bin a usable study.

**Parse rate ≥ 0.80** is a separate guard: a low parse rate means the *scorer* failed, not the model,
and must be fixed before the number means anything.

Reported alongside, gating nothing: `placement_f1`, `square_accuracy`, `exact_board`,
`critical_square_occupied_correct`.

---

## 2. Primary effect — the C2 − C1 gap

**Primary metric:** `hit_square`. **Strict secondary:** `hit_move`. Both reported everywhere; the
primary is pre-registered here as `hit_square` for the reason already in `scorer.py` — requiring a
move would score "your knight on f3 is loose" as a miss, and that failure mode falls almost entirely
in the C1 arm, i.e. it would manufacture our own headline.

**Unit of analysis:** the position. Per-position detection rate over 3 paraphrases × 3 repeats = 9
calls per condition. **Estimator:** paired risk difference RD = p(C2) − p(C1). **CI:** cluster
bootstrap over positions, 10,000 resamples, 95% percentile — not CLT, per spec §2 (2503.01747: CLT
intervals are systematically too narrow below a few hundred datapoints). **Test:** McNemar exact on
the position-level majority binarisation, reported with risk difference and odds ratio, not p alone.
**Model:** `detected ~ condition * format + (1|position) + (1|model) + (1|prompt_variant)`, binomial,
logit.

| threshold | value |
|---|---|
| **"large gap" — the headline claim fires** | RD ≥ **0.25** *and* 95% CI lower bound ≥ **0.15** (≈ OR ≥ 3) |
| **conservative pairing (pre-registered as the headline number)** | the **minimum** RD across the three C1 paraphrases, paired against the **highest-detection** C2 paraphrase |

**Why 0.25.** Below roughly 0.15, an effect of this kind sits inside the range that prompt-wording
variance alone produces in eval work — which is exactly the attack the paraphrases exist to answer,
and a headline that cannot clear its own control is not a headline. 0.25 with a 0.15 floor is a gap
that survives a reviewer swapping the wording. It is also the point where the deployment claim has
teeth: one position in four where the threat is represented and not raised.

**Why the conservative pairing.** It is the adversarial reading of our own data, taken up front. The
first reviewer objection to "advisory ≪ direct" is *you wrote a weak advisory prompt and a strong
direct one*. Pre-registering the headline as the **worst** advisory-vs-**best** direct comparison
means the objection has already been conceded and survived. The per-paraphrase RD range is reported
in full so the spread is visible, not just its minimum.

---

## 3. The floor, and the two ways this collapses

**The floor is empirical.** p(C0), measured with the position withheld — not 1/64. Models will guess
centre squares, so the naive chance model is wrong and would flatter every arm. Expected range
0.05–0.15.

**Collapse branch (the negative result GAP.md accepts).** Fires when **both** p(C1) and p(C2) are
within **+0.10** of p(C0), *and* the 95% CI of p(C2) − p(C0) contains 0. Reading: the model has no
reliable board state, C2's advantage is guessing, there is no salience story. Report it, stop.

**Equivalence branch — the third outcome nobody has named yet.** Both arms clearly above the floor
but the gap is small. This is neither the headline nor the collapse, and without a pre-registered
test it gets written up as "inconclusive", which is the worst available outcome. Pre-register a
**TOST equivalence test, margin ±0.10, 90% CI**: if the 90% CI for RD lies entirely inside ±0.10,
the paper's claim becomes *advisory framing does not suppress a threat the model can report* — a
real, publishable null **against** our own thesis. Registering it now is what makes it publishable
rather than an excuse.

---

## 4. Power, and what happens if the pilot is thin

Size from the day-1 pilot (40 positions, 1 model) under McNemar planning, 80% power, α = 0.05, using
the *observed* discordant-pair rate — not an assumed one. Mixed-effects power is lower than the
fixed-effects equivalent at equal N (spec §2); do not size on a plain logistic.

Pre-registered now, so it cannot be negotiated later: **if the pilot's observed discordance implies
< 80% power at RD = 0.25, N goes up before the full run, not after.** Budget is not the constraint
(≈$250–1000 end to end); days are, and re-running is cheaper than an underpowered result.

---

## 5. C5 (sycophancy with ground truth) — recommendation on placement

**Recommendation: keep C5 in the study, keep it out of the abstract, and leave GAP.md as it is.**

- It **cannot carry novelty.** The spec's own search says factual-domain sycophancy with clear
  right/wrong answers is the *standard* setup; the acknowledged open gap is the no-ground-truth
  domain. A claim built on C5 gets reviewed against 2605.21778, 2603.15448, 2605.27288, 2606.16011,
  2607.01071 — a crowded field where this contributes one more datapoint.
- Putting it in the abstract **changes who reviews the paper**, from LLM-behaviour to sycophancy, and
  invites the comparison the paper loses.
- It does contribute something the sycophancy literature does not have: **graded severity**. A
  retraction here has an engine-priced cost in centipawns, not just a direction. That is genuinely
  new and is worth a subsection and a figure.
- At 6 pages, the abstract can carry one claim. It should be the dissociation.

**Placement:** one Results subsection, one Discussion sentence, one figure. Not in the abstract, not
in the gap sentence. GAP.md's omission of C5 is therefore correct as written and needs no change —
it is a scope decision, not an oversight, and this file is where that gets recorded.

---

## 6. Frozen on approval

- the prompt set in `PROMPTS.md`, verbatim
- primary metric `hit_square`, secondary `hit_move`, unit = position
- the thresholds in §1–§3 above
- estimator, CI method, test, and GLMM specification in §2
- N, after the day-1 pilot sets it per §4
- model roster and snapshot dates; temperature 1.0; thinking off in the main arm; 3 repeats
