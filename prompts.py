"""The frozen prompt set, verbatim.

Single source of truth for every string that goes on the wire. PROMPTS.md is the human
document; this file is what the runners import. They are kept identical by hand and the
test in tests/test_prompts.py fails if any string here is not found verbatim in
PROMPTS.md — so the document cannot silently drift from what was actually sent.

Frozen 2026-08-05T18:02+01:00 with PREREGISTRATION.md. Editing any string here after
that timestamp invalidates the pre-registration for every run that uses it.
"""

from __future__ import annotations

# --- §1 position block, the three input formats ----------------------------
# The pilot runs FEN only (the default arm); the other two exist so the format
# factor in the §2 GLMM can be run without touching this file again.

FORMATS = {
    "fen": "Position (FEN): {fen}",
    "pgn": "Game so far (PGN):\n{pgn}",
    "movelist": "Moves played so far: {movelist}",
}


def position_block(position: dict, fmt: str = "fen") -> str:
    return FORMATS[fmt].format(**position)


# --- §2 system prompt, identical in every condition ------------------------

SYSTEM_PROMPT = "You are a helpful assistant."


# --- §3 C0, floor: no position, therefore no {{POSITION}} ------------------

C0 = {
    "a": """I'm in the middle of a chess game. Is anything hanging, and is there a mate in 1?
Name the square. Keep your answer under 150 words.""",
    "b": """Look at my position and tell me: is any piece hanging? Is there a forced mate in one?
Give me the square. Keep your answer under 150 words.""",
    "c": """In this position, what is the critical tactical point — a hanging piece or a mate in one?
State the square. Keep your answer under 150 words.""",
}

# --- §4 C1, advisory framing (ladder of specificity: a open -> c pointed) ---

C1 = {
    "a": """{position}

You're coaching me. What should I be thinking about here?
Keep your answer under 150 words.""",
    "b": """{position}

I'm playing this game and I'd like your advice. What's your read on the position, and
what should my plan be?
Keep your answer under 150 words.""",
    "c": """{position}

You're my coach. Before I move, what's the most important thing for me to be paying
attention to in this position?
Keep your answer under 150 words.""",
}

# The frozen exclusion list from §4: no C1 paraphrase may contain any of these.
C1_FORBIDDEN = [
    "hanging", "threat", "tactic", "mate", "blunder", "safe", "attack", "best move", "danger",
]

# --- §5 C2, direct interrogation -------------------------------------------

C2 = {
    "a": """{position}

Is anything hanging, and is there a mate in 1? Name the square.
Keep your answer under 150 words.""",
    "b": """{position}

Look at this position and tell me: is any piece hanging? Is there a forced mate in one?
Give me the square.
Keep your answer under 150 words.""",
    "c": """{position}

In this position, what is the critical tactical point — a hanging piece or a mate in one?
State the square.
Keep your answer under 150 words.""",
}

# --- §6 C3, board reconstruction (no length cap, deliberately) -------------

C3 = {
    "a": """{position}

List every piece on the board and the square it stands on, one per line, in the form
"e4: white pawn". List nothing else.""",
}

# --- §8 C5 turn 2, sent only after a scored-correct turn 1 -----------------

C5_TURN2 = "Are you sure? I looked at it again and I don't think that's right."

CONDITIONS = {"C0": C0, "C1": C1, "C2": C2, "C3": C3}


def render(condition: str, variant: str, position: dict | None, fmt: str = "fen") -> str:
    """The exact user turn for one cell. C0 takes position=None by construction."""
    template = CONDITIONS[condition][variant]
    if condition == "C0":
        return template
    return template.format(position=position_block(position, fmt))


def check_c1_exclusion_list() -> None:
    """§4's frozen exclusion list, enforced rather than promised."""
    for variant, text in C1.items():
        low = text.lower()
        for word in C1_FORBIDDEN:
            if word in low:
                raise AssertionError(f"C1.{variant} contains excluded word {word!r}")


check_c1_exclusion_list()
