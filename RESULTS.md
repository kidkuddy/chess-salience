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

**Floor.** p(C0) = **0.000** over 9 position-withheld calls. The model named no square at
all when given no position, rather than guessing centre squares as anticipated. The floor
is therefore cleaner than the pre-registration assumed and every arm is measured against
zero.

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

Conservative pre-registered headline (worst C1 paraphrase vs best C2 paraphrase):
RD = +0.026, 95% CI [−0.026, +0.078], McNemar p = 0.774.

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

**The null is informative, not underpowered.** At n = 90 the design had **0.973** power to
detect the pre-registered RD = 0.25 under McNemar planning at the observed discordance
(0.122); 60 positions would have sufficed. The study could comfortably have found the
effect it was built to find.

Secondary metric `hit_move`: C1 0.125, C2 0.174, RD +0.049, 95% CI [+0.011, +0.089] —
a small but interval-excluding-zero advantage to direct interrogation in naming the *move*
rather than the square. Both arms are low, and this is the metric the pre-registration
declined to make primary precisely because it penalises advisory prose.

Response-length control: C1 and C2 are matched (11.28 vs 11.21 on the logged length
measure), so the null is not a verbosity artifact.

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

**That direction is the one that could in principle hide a gap, so it is bounded.** Taking
the audit's 1-in-50 error rate as an upper bound and charging *all* of it to C2 as false
negatives with none in C1 — the worst case for the null — p(C2) rises to 0.837 and
RD to **+0.023**, still far inside the ±0.10 equivalence margin. Scorer conservatism
cannot account for the null.

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
6. **Scorer error is ~2%** and conservative in the direction that matters; bounded in §5
   and insufficient to explain the null.
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
