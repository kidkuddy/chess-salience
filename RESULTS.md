# Results — chess-salience full run

Run 2026-08-09. Model `claude-sonnet-5`, temperature 1.0, thinking off, no tools/hooks/
project context. 1{,}899 calls, **0 errors**, $14.40. 90 positions, FEN format,
3 paraphrases × 3 repeats per position for C1 and C2.

Analysis is `pilot_report.py` against the frozen `PREREGISTRATION.md` (confirmatory) and
`exploratory_report.py` against `EXPLORATORY.md` (exploratory). Neither script chooses a
metric or a threshold; both read them off their documents.

---

## 1. The position set

| dimension | composition |
|---|---|
| severity band | minor 30 · major 30 · decisive 30 |
| motif | hanging 83 · mate\_in\_1 7 |
| threat direction | opportunity 42 · vulnerability 48 |
| phase | opening 73 · middlegame 17 |
| side to move | white 43 · black 47 |

Bands are cut on the engine's centipawn margin, fixed in the generator before any data:
minor 150–300, major 300–600, decisive ≥600.

**Mate-in-1 is under-represented and is not analysed as a motif contrast.** Random-walk
sampling yields it rarely; 7 of 90 is too few to support a claim, and all 7 fall in the
decisive band by construction (a mate score sets `severity_cp` to 100000). This is scoped
out explicitly rather than left to be noticed later, and it is the confound §4 handles.

## 2. Floor and ceiling

**Floor.** p(C0) = **0.000** over 9 position-withheld calls (Wilson 95% [0.000, 0.299]).
The model named no square at all when given no position, rather than guessing centre
squares as anticipated: mean `n_squares_mentioned` in C0 is **0.00**.

*Revised 2026-08-11.* This section previously read "the floor is therefore cleaner than
the pre-registration assumed and every arm is measured against zero." That is wrong. C0
refused rather than guessed, so p(C0) = 0 records a refusal rate and says nothing about
how often a C1 or C2 answer hits the critical square by accident — and those answers name
~11 squares each. The chance-hit rate is estimated separately in §9, and the primary
contrast is re-run against it there.

**Ceiling (C3, board reconstruction, 270 calls).**

| metric | value |
|---|---|
| `critical_square_correct` | **0.981** |
| `critical_square_occupied_correct` | 0.985 |
| `placement_f1` | 0.971 |
| `square_accuracy` | 0.977 |
| `exact_board` | 0.393 |
| parse rate | 1.000 |

The ceiling is intact and slightly above the screening gate's 0.967. Whatever C1 misses,
it is **not** because the model cannot say what stands on the critical square. Note the
gap between `critical_square_correct` (0.981) and `exact_board` (0.393): the model holds
the square that matters far better than it holds the whole board, which is precisely why
the pre-registration gated on the former.

## 3. Primary result — the pre-registered contrast

Unit of analysis: the position. Metric `hit_square`. CIs are cluster bootstraps over
positions, 10{,}000 resamples, percentile.

| arm | detection |
|---|---|
| C1 advisory | **0.814** |
| C2 direct | **0.833** |
| **RD = p(C2) − p(C1)** | **+0.0198** |
| 95% CI | [−0.021, +0.062] |
| 90% CI | [−0.015, +0.054] |

McNemar exact on the position-level majority binarisation: 5 discordant favouring C2,
6 favouring C1, 79 concordant, p = 1.000, OR = 0.83.

Conservative pre-registered headline, as `pilot_report.py` implements it (minimum RD across
C1 paraphrases vs the best C2 paraphrase, which selects **C1.b**): RD = +0.026, 95% CI
[−0.026, +0.078], McNemar p = 0.774.

*Revised 2026-08-11.* This line previously described that number as "worst C1 paraphrase vs
best C2 paraphrase". C1.b is the **best**-detecting C1 paraphrase (0.852), not the worst.
`PREREGISTRATION.md` §2 specifies the pairing both ways in the same section and the two
readings select different variants; §9.2 gives all three rows and the one that inverts under
an equivalence claim.

Per-paraphrase means — the spread the paraphrases exist to expose:

| C1.a | C1.b | C1.c | C2.a | C2.b | C2.c |
|---|---|---|---|---|---|
| 0.807 | 0.852 | 0.781 | 0.841 | 0.878 | 0.781 |

The worst C2 paraphrase (0.781) equals the worst C1 paraphrase (0.781). Wording moves
detection by about 7 points **within** each arm — more than the 2-point difference
**between** arms.

### Which pre-registered branch fires

| branch | condition | fired |
|---|---|---|
| headline | RD ≥ 0.25 and CI lower ≥ 0.15 | **no** |
| collapse | both arms within 0.10 of floor | **no** (both ~0.83 above a floor of 0.000) |
| **equivalence (TOST, ±0.10, 90%)** | 90% CI inside ±0.10 | **YES** — [−0.015, +0.054] |

**The pre-registered claim is therefore: advisory framing does not suppress the surfacing
of a threat the model can report.** This is a null against the study's own thesis, and it
was registered as publishable before the data existed.

**The null is informative, not underpowered.** At n = 90 the design had **0.985** power to
detect the pre-registered RD = 0.25 under McNemar planning at the observed discordance
(0.122); 60 positions would have sufficed. The study could comfortably have found the
effect it was built to find.

*Power method:* Monte Carlo, 4{,}000 simulations, resampling the run's own per-position
rates so the simulation inherits the observed between-position heterogeneity rather than
assuming a common rate, with the C1 rates shifted so the true RD equals the pre-registered
0.25. For reference the same procedure gives 0.971 at n = 80 and 0.993 at n = 100.

Secondary metric `hit_move`: C1 0.125, C2 0.174, RD +0.049, 95% CI [+0.011, +0.089] —
a small but interval-excluding-zero advantage to direct interrogation in naming the *move*
rather than the square. Both arms are low, and this is the metric the pre-registration
declined to make primary precisely because it penalises advisory prose.

Squares-named control: C1 and C2 are matched at 11.28 vs 11.21 distinct squares per
answer. *Revised 2026-08-11:* this was previously described as a response-length control.
No response length was measured. The logged quantity is `n_squares_mentioned`, which is the
one the 150-word cap was there to equalise and the one §9.1 builds the chance correction
on. Matching the count does not by itself rule out a verbosity artifact; §9.1 does.

## 4. Exploratory — detection and threat severity

**Everything in this section is exploratory.** The hypothesis was formed on 2026-08-09 by
looking at the crashed pilot's partial data; `EXPLORATORY.md`, its four-part support
criterion, its power calculation and its analysis code were all committed **before these
positions were generated**. It is tested here on fresh positions. It is not in
`PREREGISTRATION.md` and does not enter the abstract.

The pilot suggested p(C1) flat across severity while p(C2) climbed. On held-out data:

| band | n | p(C1) | p(C2) | RD | 95% CI |
|---|---:|---:|---:|---:|---|
| minor | 30 | 0.781 | 0.778 | −0.004 | [−0.089, +0.074] |
| major | 30 | 0.859 | 0.870 | +0.011 | [−0.056, +0.074] |
| decisive | 30 | 0.800 | 0.852 | +0.052 | [−0.019, +0.126] |

| test | result | predicted |
|---|---|---|
| interaction RD(decisive) − RD(minor) | +0.056, CI [−0.052, +0.167] | CI excludes 0 — **failed** |
| band RDs ordered minor < major < decisive | yes | ordered — **met** |
| decisive RD CI excludes 0 | no | excludes 0 — **failed** |
| C1 slope across bands | +0.009, CI [−0.050, +0.069] | contains 0 — **met** |
| C2 slope across bands | +0.037, CI [−0.031, +0.106] | excludes 0, positive — **failed** |

**Verdict: NOT SUPPORTED.** One of four criteria met, plus the ordering.

Position-clustered Wald cross-check on the interaction: χ² = 1.12, p = 0.570, no
separation detected. It agrees with the bootstrap.

The half that replicated is the half about C1: **advisory detection really is flat across
severity** (slope +0.009, CI comfortably containing 0). The half that did not replicate is
the half that made it a story: C2 does not reliably climb. The pilot's apparent gradient
came from 6 decisive positions and did not survive 30.

**Motif-matched sensitivity (§5c).** Restricting the decisive band to its 23 `hanging`
positions, excluding all 7 mate-in-1: RD = +0.053, 95% CI [−0.019, +0.126]; interaction
vs minor +0.057, CI [−0.048, +0.168]. Materially identical to the unrestricted band, so
the confound is not what killed the result — the result simply is not there.

## 5. Scorer reliability

50 responses sampled stratified over condition × scorer-verdict and hand-labelled blind:
the labelling file was emitted with the response text and the engine's accept lists and
**no scorer output**.

| metric | agreement |
|---|---|
| `hit_square` | **49/50 = 0.98** |
| `hit_move` | **50/50 = 1.00** |

The single disagreement (`C2.b|p0017|r0`, critical square d4) is a boundary case: the
response wrote `Bd4xa7` while rejecting a candidate move, so the critical square appears
only as the *origin* of a move the model was discarding. The scorer extracts the
destination square and recorded a miss; the hand label counted the mention. The scorer is
conservative here, and conservative in the C2 arm.

**That direction is the one that could in principle hide a gap.** Charging *all* of the
audit's 1-in-50 error rate to C2 as false negatives with none in C1 — the worst case for
the null — p(C2) rises to 0.837 and RD to **+0.023**, still far inside the ±0.10
equivalence margin.

*Revised 2026-08-11.* This calculation is done at the **point estimate**, and this section
previously described the 2% as "an upper bound". It is not one. 1/50 has a Wilson 95%
interval of [0.004, 0.105]; at the top of that interval, charged entirely to one arm, the
worst-case argument no longer protects the margin. 50 labels support an estimate of scorer
error, not a bound on it. The honest statement is that scorer conservatism does not account
for the null at the observed error rate, and that ruling it out at the interval's upper end
would need more labels.

## 6. What this does and does not say

**It says:** in this model, on these positions, asking an open coaching question surfaces a
tactical threat about as often as asking the tactical question outright — 0.814 vs 0.833,
with the interval tight enough to call it equivalence at a ±0.10 margin. The "advisory
framing suppresses what the model knows" hypothesis, as operationalised here, is wrong.

**It does not say** that no detection–elicitation gap exists. There is a large unexplained
gap in these data — the model reconstructs the critical square 0.981 of the time but
names it in only ~0.82 of tactical answers. **This design cannot attribute that gap.**
C3 asks the model to *report the board*; C1 and C2 ask it to *find the tactic*. The
shortfall between them may be tactical reasoning rather than elicitation, and nothing here
separates those two. The C1/C2 contrast was the instrument for separating them, and it
came back flat.

**It does not say** anything about other models. One model, one family. Not generality.

## 7. Threats to validity

1. **Single model, single family.** `claude-sonnet-5` only. Three Claude models would have
   been within-family variation; one is less again. The pre-registration's GLMM carries a
   `(1|model)` term that this run cannot use.
2. **FEN only.** PGN and move-list are emitted by the generator and named as a factor in
   the pre-registered model, but the run is not powered for a format contrast and does not
   attempt one. Format may interact with framing; unknown.
3. **The severity analysis is exploratory** and came back not supported. It is reported in
   full, including the one criterion that did replicate, and it does not enter the
   abstract.
4. **Motif is confounded with severity** in the decisive band (7 mate-in-1, all decisive).
   Handled by the motif-matched analysis in §4; the conclusion does not change.
5. **Position distribution is opening-heavy** (73 opening / 17 middlegame), a consequence
   of random-walk sampling. Detection may behave differently in endgames, which are absent.
6. **Scorer error is ~2%** and conservative in the direction that matters. That is a point
   estimate from 50 labels (Wilson 95% [0.004, 0.105]), not a bound; see §5.
7. **Equivalence is a claim about a margin, not about zero.** The 90% CI is
   [−0.015, +0.054]. A true effect of, say, 0.04 is entirely compatible with these data.
   The claim is that the effect is smaller than 0.10, not that it is nothing.
8. **Advisory prompts are one operationalisation.** Three paraphrases were used and their
   spread (0.781–0.852) exceeds the between-arm difference. A more strongly advisory
   framing — longer, more distracting, more committed to a plan — might behave differently.
   That is what the unrun C4 (advisory under conversational load) arm was for.

## 8. Artifact note

Raw outputs (`data/full_raw.jsonl`, 1{,}899 records with every prompt and response),
positions, and both analysis JSONs live under `chess-salience/data/`, which is
**gitignored** by repo policy. Publishing an artifact alongside the paper means shipping
that directory deliberately; it is not in the repository history.

## 9. Robustness — analyses added 2026-08-11

Not pre-registered. `robustness.py` → `data/robustness.json`, seed 20260811. Each of these
exists because a reviewer can ask for it from artifacts already published above, and
computing it is better than leaving it to be computed against us.

### 9.1 Chance-hit correction

§2 recorded that C0 refused rather than guessed, so the pre-registered floor does not bound
accidental hits. Two nulls were computed instead. The **permutation null** holds each
response fixed and swaps in a critical square drawn from a different position in the same
set (200 draws per response). The **uniform null** is the scorer's own per-response
`chance_rate_estimate` under a uniformly random critical square.

| | C1 advisory | C2 direct | difference |
|---|---:|---:|---:|
| mean `n_squares_mentioned` | 11.28 | 11.21 | −0.07 |
| observed detection | 0.814 | 0.833 | +0.020 |
| permutation null | **0.213** | **0.180** | −0.033 |
| uniform null | 0.176 | 0.175 | −0.001 |
| chance-corrected (p−k)/(1−k) | 0.763 | 0.797 | **+0.034** |

Chance-corrected RD **+0.034**, 90% CI **[−0.009, +0.075]**, 95% CI [−0.017, +0.084]
(cluster bootstrap over positions, 10,000 resamples).

Two readings. The 150-word cap equalised the *count* of squares named (11.28 vs 11.21) but
not the *chance-hit probability* (0.213 vs 0.180): the arms name different squares, not
just the same number of them, and the uniform null cannot see the difference because it
ignores which squares are actually critical in this set. And correcting for it moves the
framing effect **up**, to +0.034, while leaving it inside the ±0.10 margin. The equivalence
conclusion survives the strongest attack available to it.

### 9.2 The adversarial pairing, both directions

`PREREGISTRATION.md` §2 specifies the pairing twice and the two do not agree. The threshold
table (line 70) says *minimum RD across the three C1 paraphrases* against the
highest-detection C2, which selects **C1.b**. The rationale ten lines later (line 80) says
*worst advisory vs best direct*, which selects **C1.c**, the least-detecting C1 wording.
`pilot_report.py` implements the first. All three rows, against C2.b (0.878):

| C1 | p(C1) | RD | 95% CI | McNemar |
|---|---:|---:|---|---:|
| C1.a open coaching | 0.807 | +0.070 | [+0.011, +0.133] | 0.143 |
| **C1.b plan request** (code) | 0.852 | **+0.026** | [−0.026, +0.078] | 0.774 |
| **C1.c priority** (rationale) | 0.781 | **+0.096** | [+0.033, +0.159] | 0.031 |

The +0.096 row breaches the ±0.10 margin at its upper end. Three caveats, all of which
belong in the paper next to the number: it is the maximum of nine pairings and is biased
outward by that selection, so its nominal CI and p are both optimistic; minimising the RD
was the conservative direction for the *superiority* branch the pre-registration expected
to fire, and under an *equivalence* claim the conservative direction inverts; and neither
row is the pre-registered primary, which is the arm-level contrast in §3.

### 9.3 Power for the branches as written

`pilot_report.py` computes the power of a bare exact McNemar test. The pre-registered
headline fires on a **conjunction** (observed RD ≥ 0.25 *and* 95% CI lower ≥ 0.15), and the
equivalence branch was never given an operating characteristic at all. Simulated at n = 90
on the run's own per-position rates, 2,000 studies each with a 10,000-resample bootstrap
inside:

| | value |
|---|---:|
| McNemar power at true RD = 0.25 (4,000 sims) | **0.9852** |
| P(headline branch fires) at true RD = 0.25 | **0.503** |
| P(equivalence branch fires) at true RD = 0.00 | **0.966** |
| P(equivalence branch fires) at true RD = 0.05 | **0.591** |

A threshold set *at* the hypothesised value is cleared about half the time by symmetry, so
0.985 is the power of a difference test and not of the branch that was written down. The
branch that did fire is well powered under a true null and cannot separate a true 0.05 from
zero, which is the same thing §7 item 7 says in words.

The McNemar curve is also recomputed here at the 4,000 sims §3 quotes, on the grid §3
quotes: 0.8902 (n=60), 0.9705 (n=80), **0.9852 (n=90)**, 0.9928 (n=100). `full_report.json`
carries this curve at the script default of 2,000 sims and without an n = 90 point, which
is why the n = 90 figure appeared in prose with no artifact behind it. It reproduces.

### 9.4 Interval estimates for two reported point rates

| rate | point | Wilson 95% |
|---|---:|---|
| floor p(C0), 0/9 | 0.000 | [0.000, 0.299] |
| scorer error, 1/50 | 0.020 | [0.004, 0.105] |
| scorer agreement, 49/50 | 0.980 | [0.895, 0.996] |

### 9.5 Deviations from the pre-registration

Four specified items were not run or not reported. The paper lists all four in Threats.

1. **C4**, advisory under ~15 turns of conversational load (`PROMPTS.md` §7). Not run.
2. **Thinking-on secondary arm** on a 40-position subset (`PROMPTS.md` §0). Not run.
   Relevant because extended thinking plausibly turns C1 into a de-facto C2.
3. **C5**, sycophancy with graded severity (`PREREGISTRATION.md` §5, which rules to keep it
   in the study). Not run.
4. **The GLMM** `detected ~ condition * format + (1|position) + (1|model) +
   (1|prompt_variant)` (`PREREGISTRATION.md` §2). Not fitted. The model and format terms are
   unusable with one model and one format; `(1|position)` and `(1|prompt_variant)` are
   estimable, and given that the secondary finding is that prompt variant dominates,
   `(1|prompt_variant)` is the term a reader most wants to see. This one was an oversight
   rather than a resource decision.
