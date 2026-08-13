# Independent human validation: recruitment and provenance

This document operationalizes `LABELLING.md` without changing its labels, sample, stopping
rule, or analysis. It was added after automated judges disagreed and after reviewer r8
requested independent human validation.

## Recommended raters

Recruit two adults who were not involved in the study:

- **Rater A:** a publicly verified titled chess player or coach (FIDE title, national
  master title, or a coach profile whose federation rating is verified by the platform).
- **Rater B:** a second independent chess player with a published federation or platform
  rapid/classical rating of at least 1800. A second titled coach is preferable.

Suitable public directories include Lichess Coaches and Chess.com Coaches. Record the
public profile URL, displayed title/rating, access date, fee, and a declaration that the
rater did not see condition identities or aggregate results before exporting labels.
Consent is required before publishing a rater's name or profile; otherwise publish only
the verification class and retain the identity privately for editorial audit.

## Assignment

Both raters independently label all 180 frozen stage-1 items. This is stronger than the
minimum 60-item overlap in `LABELLING.md` and directly addresses whether semantic ambiguity
caused the Sonnet--Haiku disagreement. Neither rater receives the paper, reviewer reports,
condition key, original prompts, Sonnet/Haiku labels, or arm-level results.

Each rater receives only:

1. `LABELLING.md` sections 1--3 (construct, labels, bright lines, blinding);
2. a separately generated copy of the stage-1 UI;
3. the statement: “The engine target is supplied. Judge whether the response directs a
   reader's attention to that target; do not independently choose a better chess move.”

Raters may use an analysis board to parse notation but may not use an LLM to assign or
rewrite labels. They mark `?` when uncertain rather than consulting one another.

## Frozen handling and analysis

- Preserve both original exports unchanged with SHA-256 hashes and UTC receipt times.
- Compute pre-discussion three-level agreement and Cohen's kappa on all 180 items.
- If kappa is below 0.60, follow the existing invalidity branch: revise the rubric and
  collect new labels before using them as validation.
- If kappa is at least 0.60, resolve disagreements in a recorded adjudication pass against
  the existing bright lines. Preserve pre-adjudication labels and publish the adjudicated
  file separately.
- Run `score_labels.py --stages 1 --rater2 <second-export>` and report the stage-1 interval.
  Follow `LABELLING.md`'s existing stopping rule; do not add stages based on which arm wins.
- Report compensation, completion time, credentials, exclusions, unresolved items, and
  whether either rater guessed the study hypothesis.

## Recruitment message

> Subject: Paid blinded annotation of chess-assistant answers for a research paper
>
> I am seeking an independent chess expert to label 180 short answers about chess
> positions for a research validation study. Each item supplies a board, an engine target
> square, and a model answer. Your task is to classify whether the answer highlights that
> target as tactically relevant, merely names it, or omits it. You are not being asked to
> solve each position or assess the AI generally. The web interface is self-contained;
> expected time is 60--90 minutes. Labels are blinded to the experimental condition.
> Please quote a fixed fee and confirm whether I may report your public chess title/rating
> and profile URL as rater credentials. You must complete the labels yourself without an
> AI assistant. Full instructions and an example can be reviewed before accepting.

## Provenance record template

```json
{
  "rater_id": "RATER_A",
  "credential_class": "FIDE-titled / federation-rated / verified coach",
  "public_profile_url": null,
  "displayed_title_or_rating": null,
  "profile_accessed_utc": null,
  "consent_to_publish_identity": false,
  "conflict_of_interest": "none declared",
  "compensation_currency": null,
  "compensation_amount": null,
  "instructions_sha256": null,
  "task_packet_sha256": null,
  "labels_sha256": null,
  "labels_received_utc": null,
  "self_reported_llm_use": false
}
```

This procedure produces the human evidence requested by r8. A third automated judge,
including the frozen Gemini analysis, does not.
