# Gap sentence — chess salience / advisory omission

*Written 2026-08-04, before any data was collected. This is the paragraph the study exists to satisfy.*

## The paragraph

Board state is demonstrably represented inside chess-trained transformers — linear probes recover it
and activation edits change downstream play (Karvonen, 2403.15498) — and a chess-as-LLM-eval line has
grown up around general models, with ChessQA (2510.23948) reporting persistent weakness across five
ascending competence categories and LLM CHESS (2512.01992) benchmarking move quality and blunder rate
across 50+ models. In parallel, a detection–elicitation literature has established that models encode
information at the representation layer that they do not surface at the output layer: *LLMs Know More
Than They Show* (2410.02707) recovers correctness signals probes can read but generations do not
express, with brittleness (2510.11905) and belief-versus-retraction (2505.16170) mapping how far that
dissociation generalises. **What is missing is the intersection.** Every existing chess evaluation
interrogates the model directly — *what is the best move, is this position winning, find the tactic* —
so no published number tells us what a general chat assistant in an *advisory* role volunteers about
the same position when it is not asked the tactical question. That means no current result can separate
**"the model never represented the threat"** from **"the model represented the threat and did not raise
it"**, and those two failures have opposite remedies: the first is a capability problem, the second is
an elicitation and interface problem. **This study settles that separation.** Holding the position
fixed and varying only the framing — advisory coaching (C1) against direct interrogation (C2), with a
board-reconstruction ceiling (C3) above and a position-withheld guess floor below — it yields a
per-position detection rate under each framing on generated, contamination-free positions with a
deterministic engine-anchored scorer. A large C2 − C1 gap with C3 intact licenses the claim that
advisory framing suppresses the surfacing of a threat the model can otherwise report — a
detection–elicitation gap in a deployed advisory role. C1 ≈ C2 with both at the floor, or C3 collapsed,
licenses only the weaker and already-reported claim that the model holds no reliable board state; that
is a negative result, it is publishable as one, and knowing which of the two obtains is the point.

## What it does *not* claim

- Not "LLMs are bad at chess" — ChessQA and LLM CHESS own that, and it is not a contribution.
- Not a mechanistic claim. No probe is run here (out of scope for 15 Aug, needs open weights). The
  dissociation established is behavioural: same input, different framing, different output.
- Not cross-vendor generality. Three Claude models is within-family variation (see RESULTS.md
  limitations).

## Citations used above

| id | short |
|---|---|
| 2403.15498 | Karvonen — board state linearly probed in chess-trained transformers |
| 2510.23948 | ChessQA — five-category chess eval, persistent weakness across all |
| 2512.01992 | LLM CHESS — 50+ models, agentic play, move-quality/blunder metrics |
| 2410.02707 | LLMs Know More Than They Show — internal correctness signal not surfaced |
| 2510.11905 | truthfulness-probe brittleness |
| 2505.16170 | retraction and model belief |
