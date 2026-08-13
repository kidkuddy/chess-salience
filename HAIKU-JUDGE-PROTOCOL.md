# Haiku cross-model judging protocol

**Frozen before the first Haiku label is collected.** This is a post-hoc validation of
the semantic outcome, not a human annotation and not a confirmatory outcome from the
original pre-registration.

## Purpose and scope

The primary response generator and the existing blinded judge are both
`claude-sonnet-5`. This follow-up tests whether a smaller, pinned model reaches the same
semantic labels when given the human-labelling rubric. It reduces same-model circularity
but does not supply independent human ground truth because both models are from Anthropic.

The fixed judge is `claude-haiku-4-5-20251001`. Requests explicitly disable thinking,
omit sampling parameters, expose no tools, and request exactly one label token.

## Frozen sample and blinding

The input is the existing frozen stage-1 packet in
`data/label_tasks_stage1.json`: one advisory and one direct response per position, 180
items total, balanced across prompt paraphrases and shuffled. The packet contains the
board, side to move, engine critical square, accepted engine moves, and response. It does
not contain condition, prompt variant, repeat, prompt text, or scorer outputs.

All 180 items receive one label. The 60 items already marked `double_rate` receive two
additional independent labels, for 300 calls total. The subset was selected when the
human-labelling packet was built, before this protocol.

## Labels

- **2 — detected:** the critical square, or a move to/from it, is named and the response
  attributes a threat, weakness, capture, tactic, target, or opportunity to it.
- **1 — named only:** the square appears only as board transcription, an item in an
  undifferentiated list, or a dismissal.
- **0 — absent:** the square and any move involving it are absent.

Bright lines follow `LABELLING.md`: board transcription and dismissal are label 1;
hedged detection is label 2; correct square with a wrong tactical reason is label 2;
vocabulary is not required; a real tactic elsewhere does not count.

## Validity gates

- Parse rate across all calls must be at least 0.98.
- On the 60 three-pass items, all three labels must agree in at least 0.80 of cases.

If either gate fails, the labels are retained but used descriptively only. Calls are
resumable, errors are recorded, and no failed or unparsable call is retried automatically.

## Analysis

After collection, `score_haiku_labels.py` opens the sealed stage-1 key and reports:

1. Haiku label-2 rates by arm and paired risk difference `p(C2) - p(C1)`, with 90% and
   95% position-bootstrap intervals (10,000 resamples).
2. The proportion of label 1 by arm.
3. Three-level agreement and Cohen's kappa against the existing blinded Sonnet judge on
   the same 180 responses.
4. Binary agreement with `detected_self` and sensitivity, specificity, and kappa for
   `hit_square` and `hit_move`, treating Haiku label 2 as the reference.
5. Whether the 90% interval happens to lie inside the original ±0.10 margin, explicitly
   as a post-hoc continuity check rather than a newly confirmatory test.

No prompt, label, gate, threshold, or analysis is changed after the first call.
