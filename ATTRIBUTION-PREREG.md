# Pre-registration — attribution and conversational load (C6, C4)

**Status: FROZEN 2026-08-12, before any C4 or C6 call was made.**

Committed together with `run_arms.py` and `score_arms.py`, which implement exactly what is
written here. This is the third frozen document in this study, and the same rule applies:
nothing below may be edited after the first call; corrections get appended with a date and
a reason.

## 1. Why

`RESULTS.md` and the retrofit leave one number unexplained and it is the largest in the
paper. The model reconstructs the critical square in **0.981** of C3 calls and flags it in
**0.539** of advisory and direct answers. The Discussion says, correctly, that the design
cannot tell whether that shortfall is a reasoning failure or an elicitation failure, and
stops there. Five of six external reviewers named that gap.

The C1/C2 contrast cannot settle it because the two arms are separate conversations: a
model that misses the threat in C1 and finds it in C2 might have known it both times, or
might have found it only on the second, independent attempt.

**C6 settles it by putting both questions in one conversation.** If the model misses the
threat when asked openly and then names it when asked directly *in the same session*, the
information was available and went unreported. That is elicitation, and it is the salience
hypothesis in a form the original design could not see. If it misses both, it never had the
threat, and the 0.98 ceiling is measuring board reading rather than tactical search.

**C4 tests whether the null survives conversational load.** It was specified in
`PROMPTS.md` §7, never run, and disclosed as a deviation. Both the paper and three
reviewers identify it as the most informative missing arm.

## 2. C6 — advisory then tactical, one conversation

The 270 C1.a sessions from the original run are still on disk. Each is **resumed and
forked**, and a second user turn is added:

```
{{POSITION}}

Is anything hanging, and is there a mate in 1? Name the square.
Keep your answer under 150 words.
```

That is C2.a from `prompts.py`, verbatim, including the position block — the model gets
exactly the direct question it would have got standalone.

**Turn 1 is the original C1.a response.** It is already recorded in `data/full_raw.jsonl`,
already scored, and already has a self-report extraction from the retrofit. Nothing is
regenerated. Sessions are forked, so the recorded transcripts cannot change.

A third turn then asks for the self-report, using the **verbatim extraction prompt from
`RETROFIT-PREREG.md` §2**, so `detected_self` on turn 2 is the same construct as everywhere
else in the study.

Scope: all 90 positions × 3 repeats of C1.a = 270 sessions × 2 calls = **540 calls**.

## 3. C4 — advisory under conversational load

`prompts/c4_prefix.json` holds eight frozen user turns of ordinary chess chat with no board
information and no tactical content.

**The prefix is played once.** The eight user turns are sent in sequence against the model,
the realised assistant turns are recorded verbatim to `data/c4_prefix_realized.json`, and
every C4 call **forks that single session**. Three consequences, all deliberate:

- the prefix is byte-identical across all 270 C4 calls, which is what a control requires;
- it is a real conversation rather than a synthetic transcript;
- it costs eight calls rather than eight per position.

This is a deviation from `PROMPTS.md` §7, which implies scripted assistant turns. It is
recorded here rather than silently taken, and the realised prefix is committed so it is
diffable exactly as §7 intended.

The final user turn is **C1.a verbatim**, then a self-report extraction turn as above.

Scope: 90 positions × 3 repeats = 270 sessions × 2 calls = **540 calls**, plus 8 to build
the prefix.

## 4. Metrics

Both arms use `detected_self` — the critical square appears in the model's own list of
squares it flagged — parsed exactly as `RETROFIT-PREREG.md` §3 specifies.

For C6, turn 1's `detected_self` is taken from the retrofit's existing records, and turn
2's is computed from the new extraction.

## 5. Validity checks, thresholds fixed now

Run before any primary estimate is looked at.

| check | tests | threshold |
|---|---|---|
| resume rate | sessions actually resumed | ≥ 0.98 |
| parse rate | extractions machine-readable | ≥ 0.98 |
| subset rate | flagged ⊆ squares that turn mentioned | ≥ 0.90 |
| C4 prefix integrity | realised prefix contains no algebraic square and no exclusion-list word | **exact** — any hit voids C4 |
| C6 turn-1 identity | turn 1 in each forked session matches the recorded C1.a response | **exact** — any mismatch voids C6 |

If a check fails, that arm is reported as attempted and invalid. Written first, as before,
because it is the branch that costs the most to admit.

## 6. C6 — the attribution estimate and its branches

The quantity of interest is the **recovery rate**:

> **R = P(turn 2 detects | turn 1 did not detect)**

computed over positions, with a cluster bootstrap over positions, 10,000 resamples.

The reference point is C2's standalone rate, **0.536**. If the threat was available to the
model during turn 1 and merely unreported, asking directly should recover it at close to
the rate a direct question achieves cold.

| branch | condition | reading |
|---|---|---|
| **elicitation-dominant** | R ≥ 0.40 | ≥ 75% of C2's standalone rate. The model largely had the threat and did not volunteer it. The salience hypothesis is supported in a within-conversation form, and the paper's headline gains a major qualification |
| **reasoning-dominant** | R ≤ 0.15 | ≤ 28% of C2's standalone rate. The model largely did not have the threat. The 0.98 ceiling measures board reading, not tactical search, and the shortfall is a capability gap |
| **mixed** | 0.15 < R < 0.40 | Both mechanisms contribute; report R with its interval and attribute nothing further |

**Declared confound.** Turn 2 has turn 1's own analysis in context, so a turn-2 hit could
reflect a second look rather than a withheld claim. Two things bound it, both reported
regardless of branch:

1. **P(turn 2 detects | turn 1 detected)** — whether turn 2 is simply more accurate overall.
2. **R against C2 standalone (0.536).** R *above* 0.536 means the extra context helped
   beyond being asked, and the elicitation reading weakens accordingly. This is why the
   elicitation threshold sits below C2's rate rather than at it.

## 7. C4 — branches

Primary: `detected_self` for C4 against C1's 0.542, as a paired risk difference over
positions with the same cluster bootstrap and the same ±0.10 margin.

| branch | condition | reading |
|---|---|---|
| **load suppresses** | 95% CI lower > +0.10 | Advisory framing does suppress reporting once there is conversational load. The single-turn null is a ceiling effect of an unrealistically clean setting, and this becomes the paper's headline |
| **null survives load** | 95% CI inside ±0.10 | The equivalence claim extends to a materially more realistic setting. Strengthens the paper substantially |
| **inconclusive** | otherwise | Report the interval |

## 8. What each outcome does to the paper

Committed now, so the writing follows the data.

- **C6 elicitation-dominant.** The Discussion stops refusing to attribute and attributes.
  The paper becomes: framing between conversations does not matter, but *within* a
  conversation the model demonstrably holds back — which is a sharper and more useful claim
  than the current null.
- **C6 reasoning-dominant.** The paper can finally say what the 0.98 → 0.54 shortfall is,
  and the ceiling's interpretation changes: C3 measures board reading, and the study's
  instrument for separating reasoning from elicitation reports "reasoning".
- **C4 load suppresses.** The headline inverts for realistic settings and the single-turn
  result becomes the boundary condition. Best outcome for the paper's interest, worst for
  its current abstract.
- **C4 null survives.** The strongest version of the existing claim.
- **Anything invalid.** Reported as attempted and invalid, with the failing check named.

## 9. Threats declared in advance

- **Both arms are post-hoc** relative to `PREREGISTRATION.md`. C4 was specified there and
  not run; C6 is new and was designed after the retrofit result was known. That is exactly
  why this document exists and why it is committed before any call.
- **C6's turn-2 context confound** is bounded but not eliminated — see §6.
- **The C4 prefix is one realised conversation.** Every C4 call shares it, so any quirk in
  those eight assistant turns is common to all of them. That is the point (it is a
  control), but it means C4 measures load *under this prefix*, not load in general.
- **Turn 1 of C6 is not independent of the retrofit**, which already forked those sessions
  for extraction. Forking does not mutate, so the transcripts are unchanged, and §5 checks
  turn-1 identity rather than assuming it.

## 10. Cost

At the measured $0.0076/call: 540 + 540 + 8 = **1,088 calls, roughly $8**, about ten
minutes. Output goes to `data/arms_raw.jsonl`, one record per call, resumable by
`(arm, position_id, repeat, stage)` and append-only.

---

## Amendment 1 — 2026-08-12, before any C4 or C6 data call

The first realised C4 prefix **failed §5's prefix-integrity check** and is retained at
`data/c4_prefix_realized_attempt1_FAILED.json` rather than deleted.

Two failures, one of which §5 did not anticipate:

1. **Caught by the check.** The word *tactic* appears in a realised assistant turn. §5
   makes this an exact threshold and it was violated.
2. **Not caught by the check, and worse.** The final assistant turn reads: *"whether that's
   'what should I be thinking about here' or you just want to talk through the plans"* —
   the model pre-echoed **the C1.a prompt itself**. A prefix that quotes the question under
   test primes the exact behaviour C4 is supposed to measure under neutral load.

**Root cause.** The final frozen user turn ("Anyway, I have a game paused in front of me at
the moment") invites an offer of help, and the model obliged by proposing the advisory
framing verbatim.

**What changes.** Two things, both to the instrument, neither to any hypothesis, threshold,
metric or branch:

- The frozen user turns are amended so the last one does not solicit an offer of help.
- §5 gains a third prefix check, which should have been there from the start:
  **no realised turn may contain any substring of the C1.a or C2.a prompt text** (checked
  on any run of five or more consecutive words). Violation voids C4 exactly as the other
  two do.

**Attempt budget, fixed now.** The prefix may be rebuilt at most **three times** in total.
If no attempt passes all three checks, C4 is reported as attempted and invalid, and the
attempt count is reported either way. This attempt is 1 of 3.

**Why this is not p-hacking.** The prefix is the instrument, not the data — no C4 or C6
outcome has been observed, and the failing artifact is committed alongside the passing one.
The distinction that matters is that the checks were written before the prefix existed and
are being enforced against it, rather than relaxed to accommodate it.

## Amendment 2 — 2026-08-12, still before any C4 or C6 data call

Attempt 2 also failed §5, and worse on the vocabulary check: *threat*, *tactic* and
*blunder* all appear. The prompt-echo failure from Amendment 1 was fixed. Artifact kept at
`data/c4_prefix_realized_attempt2_FAILED.json`.

**This is a design fault, not bad luck.** `PROMPTS.md` §7 asks for eight turns of ordinary
chess chat; the exclusion list is a list of ordinary chess words. Any genuine conversation
about chess will reach for them. My user turns made it worse by dwelling on playing speed
and thinking time, which invite exactly that vocabulary.

**I considered relaxing the check and decided against it, and the reasoning matters.** One
could argue generic chess vocabulary in social chat is not "tactical content *about this
position*", which is what §7 actually cares about. But tactical priming would inflate C4's
detection rate, which biases toward the "null survives load" branch — the branch that
agrees with the paper's current conclusion. A threshold must not be loosened in the
direction of the answer one already believes. **The check stands as written.**

**What changes: the user turns, not the threshold.** They are rewritten to be about the
social and logistical side of club chess — the venue, travel, the people — giving the model
no hook to discuss how chess is played.

**This is attempt 3 of 3.** If it fails, C4 is reported as attempted and invalid under §5,
C6 proceeds regardless, and the paper says the load arm could not be run with a clean
prefix. That outcome is pre-committed and will be reported with all three failed artifacts.
