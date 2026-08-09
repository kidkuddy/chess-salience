# Exploratory pre-specification — condition × severity

**Written 2026-08-09, before the full-run positions were generated and before any full-run
model call was made. Committed before `data/full_positions.jsonl` exists. That ordering is
the point of this file and is checkable in git.**

This is **not** part of `PREREGISTRATION.md` and does not amend it. That document is frozen
and stays frozen. Everything specified here is **exploratory** and is reported as
exploratory in every table, figure caption and sentence it touches. It may not be promoted
to confirmatory, and it may not lead the abstract.

---

## 1. How this hypothesis was formed — stated plainly, because it matters

It was formed by looking at pilot data. On 2026-08-09 the crashed pilot's partial output
(568 of 849 calls, 23 positions with paired C1/C2 coverage) was analysed for the first time.
The pre-registered primary contrast came back null — pooled RD = 0.053, 95% CI
[−0.014, 0.126], headline threshold RD ≥ 0.25 not met. Splitting those same calls by the
generator's existing engine-severity band produced this:

| severity band | n calls C1 | p(C1) | n calls C2 | p(C2) | RD |
|---|---:|---:|---:|---:|---:|
| minor | 171 | 0.830 | 99 | 0.859 | +0.028 |
| major | 135 | 0.785 | 63 | 0.905 | +0.120 |
| decisive | 54 | 0.796 | 37 | 1.000 | +0.204 |

The pilot drew 19 minor / 15 major / 6 decisive positions, so the minor band — the one with
almost no effect — dominates the pooled average.

This is a post-hoc observation on a small, unbalanced, partially-collected sample. Six
decisive positions. It is exactly the kind of subgroup split that does not replicate. It is
written down here, before the confirming data exists, so that it cannot later be presented
as anything other than what it is.

## 2. Why the test is nonetheless meaningful

**The full run generates fresh positions with a new seed.** The pilot's 40 positions are not
carried forward and are not pooled in. The hypothesis was formed on the pilot and is tested
on held-out data. That is the one structural property that makes an exploratory result worth
collecting rather than merely worth confessing.

## 3. The claim, stated so it can fail

> Advisory framing (C1) surfaces threats at a rate that is **insensitive to how severe the
> threat is**, while direct interrogation (C2) surfaces them at a rate that **rises with
> severity**. The pooled C2 − C1 null is therefore an artifact of severity composition, not
> evidence that framing does not matter.

Note which half carries the weight. The interesting quantity is the **flatness of C1**, not
the size of the gap. A model whose advisory behaviour ignores a 1000-centipawn threat as
readily as a 200-centipawn one is the finding; the gap is how it becomes visible.

## 4. Sampling, fixed now

Target **~30 positions per severity band** (90 total). Bands are the generator's existing
cuts on `severity_cp` — `minor` / `major` / `decisive` — **unchanged**. The band definitions
are not to be re-cut, re-thresholded or collapsed after seeing the results. If the generator
cannot reach 30 in a band, the achieved distribution is reported as achieved and the analysis
proceeds on it; the bands are not rebalanced by discarding positions.

## 5. The analysis, fixed now

Unit of analysis is the **position**, as in the frozen prereg: a per-position detection rate
over 3 paraphrases × 3 repeats = 9 calls per condition. Primary metric `hit_square`, as
frozen.

1. **Descriptive.** p(C1) and p(C2) by band, with cluster-bootstrap 95% CIs over positions
   within band (10,000 resamples, percentile).
2. **Band-wise effect.** RD = p(C2) − p(C1) within each band, same bootstrap.
3. **Interaction test.** The headline is a **cluster-bootstrap CI on the interaction
   contrast** `RD_decisive − RD_minor`, resampling positions within band, 10,000
   resamples, 95% percentile. Support requires the CI to exclude 0. Reported alongside,
   as a parametric cross-check: a binomial GLM with logit link,
   `detected ~ condition * severity_band`, fitted with position-clustered robust
   covariance, Wald test on the interaction terms.

   *Amendment, 2026-08-09, made before `data/full_positions.jsonl` existed and before any
   full-run model call — see git order.* This slot originally specified a GLMM
   likelihood-ratio test. statsmodels 0.14.6 ships no frequentist binomial GLMM that
   yields one (`BinomialBayesMixedGLM` is variational Bayes; an LRT is not defined for
   it). Rather than fake the test or silently drop it, the estimator moves to the cluster
   bootstrap — which is what `PREREGISTRATION.md` §2 already uses for every confirmatory
   CI in this study, so the exploratory analysis and the frozen one now share an
   inferential engine. The frozen document is untouched.
4. **C1 flatness test.** Severity band as an ordered numeric contrast (minor=0, major=1,
   decisive=2), C1 rows only: slope with bootstrap 95% CI. The claim predicts a CI
   **containing** 0 — an unusual direction to pre-register, and the reason it is written
   before the data exists.
5. **C2 sensitivity test.** The same slope on C2 rows only. The claim predicts a CI
   **excluding** 0 and positive.

## 5b. Power at 30 positions per band — computed 2026-08-09, before the run

Monte-Carlo, resampling the pilot's position-level rates within band, 9 calls per cell,
asking how often a cluster-bootstrap 95% CI on that band's RD excludes 0:

| band | pilot n_pos | pilot p(C1) | pilot p(C2) | pilot RD | n=20 | **n=30** | n=40 |
|---|---:|---:|---:|---:|---:|---:|---:|
| minor | 11 | 0.889 | 0.859 | −0.030 | 0.01 | **0.01** | 0.00 |
| major | 7 | 0.778 | 0.905 | +0.127 | 0.70 | **0.88** | 0.94 |
| decisive | 5 | 0.867 | 1.000 | +0.133 | 1.00 | **1.00** | 1.00 |

(Position-level rates, so these differ slightly from the call-level table in §1 — the
position is the pre-registered unit of analysis and equal-weights positions, not calls.)

30 per band is adequate: ~0.88 power on major and effectively 1.00 on decisive, where
C2's near-ceiling rate collapses the variance. The minor row is not a failure — a
correctly-behaved 1% is what a genuinely null band should produce, and it is the
within-study control that says the other two bands are not an artifact of the method.

## 6. What counts as support — all four, or it is not support

- the interaction contrast `RD_decisive − RD_minor` (§5.3) has a 95% CI excluding 0, **and**
- band-wise RDs (§5.2) are ordered minor < major < decisive, **and**
- the decisive-band RD 95% CI excludes 0, **and**
- the C1 flatness CI (§5.4) contains 0 while the C2 slope CI (§5.5) excludes 0.

Anything less is reported as **not supported**. Partial patterns — for instance an ordered
set of RDs with a non-significant interaction — are reported as the numbers they are, in one
sentence, with the word "not supported" attached. They do not get a paragraph of
interpretation and they do not enter the abstract.

## 7. Forbidden, now that it is written down

- Re-cutting severity bands, adding a fourth band, or merging two.
- Switching the primary metric to `hit_move` because it looks better by band.
- Dropping the minor band as "a ceiling artifact".
- Adding positions to a band after seeing that band's result.
- Re-running the generator with a new seed to get a distribution that works better.
- Pooling the pilot's 23 positions in to raise n.

If the result is not supported, the paper reports the frozen pre-registered outcome and this
section as a null exploratory follow-up. That is a complete and honest paper, and it is the
outcome this file exists to make survivable.
