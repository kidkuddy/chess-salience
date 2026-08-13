# Independent-vendor Gemini judging protocol

**Frozen after the Haiku result and before the first Gemini label is collected.** This is
a post-hoc triangulation analysis prompted by reviewer concern about judge dependence. It
is not human annotation, independent ground truth, or part of the original confirmatory
analysis.

## Rationale

Sonnet generated the responses and supplied the original semantic judgments. Haiku is a
different model but the same vendor. A Google Gemini judge removes generator--judge vendor
overlap. A chess engine is not used as a prose judge: the engine already supplies the
critical square and accepted moves, but cannot determine whether a natural-language answer
attributes tactical relevance to them.

The fixed judge is the stable model code `gemini-2.5-pro`, called through Gemini CLI
0.47.0 in a fresh process for every label. The runner records the model requested, CLI
version, complete machine-readable CLI response, prompt hash, token statistics, and error
state. No tools are requested or needed.

## Sample, blinding, labels, and gates

The sample and rubric are identical to `HAIKU-JUDGE-PROTOCOL.md`: all 180 shuffled,
condition-blinded stage-1 tasks receive one label, and the 60 preselected reliability
items receive two further labels, for 300 calls. Prompts contain the board, side to move,
engine critical square, accepted engine moves, and response, but no condition, prompt
variant, repeat, original prompt, or prior score.

Labels are `2` (the answer attributes tactical relevance to the square or a move involving
it), `1` (named only), and `0` (absent). Parse rate must be at least 0.98 and exact
three-pass agreement at least 0.80. Failed and unparsable calls are recorded and are not
automatically retried.

## Frozen analysis

`score_gemini_labels.py` reports:

1. Gemini label-2 rates by arm and paired `p(C2)-p(C1)` risk difference with 90% and 95%
   position-bootstrap intervals (10,000 resamples).
2. Label-1 rates, parse rate, and three-pass exact agreement.
3. Pairwise three-level agreement and Cohen's kappa with the Sonnet and Haiku first labels.
4. A descriptive three-judge majority outcome: detected when at least two of Sonnet,
   Haiku, and Gemini assign label 2, with the same paired interval. This panel was defined
   after the Haiku result and cannot rescue or replace the registered outcome.
5. Complete unanimity and three-way disagreement rates, overall and by arm.

Results are reported regardless of direction. No prompt, threshold, or analysis changes
after the first Gemini call.
