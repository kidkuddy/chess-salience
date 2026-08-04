#!/usr/bin/env python3
"""Deterministic scorer. No LLM anywhere in this file, or in anything that calls it.

Scoring is a string match of the model's free text against an engine-derived target:
the critical square and the critical move. Both are computed by Stockfish at generation
time (gen_positions.py) and stored with the position; nothing here re-decides what the
right answer is.

Two detection metrics, both pre-registered, reported separately everywhere:

  hit_square (PRIMARY)  the response names the critical square as a coordinate token.
                        Primary because under advisory framing (C1) a model that has
                        seen the threat typically says "your knight on f3 is loose"
                        without ever giving a move; requiring a move would score that
                        as a miss and would bias the C1 arm downward — exactly the
                        direction that would manufacture our own headline result.

  hit_move   (STRICT)   the response names the critical move itself (SAN or UCI).
                        Much lower chance rate, so this is the conservative number.

Chance-hit control: n_squares_mentioned is returned with every score. A response that
lists twenty squares can hit the target by accident, and the empirical guess rate comes
from the no-board floor condition (C0), not from an assumption.

Board reconstruction (C3) is scored on the piece placement the model reports, parsed
either from a FEN it emits or from "<square>: <piece>" lines.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Iterable, Optional

import chess

FILES = "abcdefgh"
RANKS = "12345678"
SAN_PREFIX = set("xKQRBN")          # chars that may legally precede a square in SAN
TRAILING_OK = set("+#=!?)],.;:\"'*")  # chars that may follow a square token


# --------------------------------------------------------------------------
# square / move extraction
# --------------------------------------------------------------------------

_SQ = re.compile(r"[a-h][1-8]")

_UCI = re.compile(r"(?<![a-zA-Z0-9])([a-h][1-8][a-h][1-8][qrbnQRBN]?)(?![a-zA-Z0-9])")

_SAN = re.compile(
    r"(?<![a-zA-Z0-9])("
    r"O-O-O|0-0-0|O-O|0-0"
    r"|[KQRBN][a-h1-8]?x?[a-h][1-8]"
    r"|[a-h]x[a-h][1-8](?:=[QRBN])?"
    r"|[a-h][1-8](?:=[QRBN])?"
    r")([+#]?)(?![a-zA-Z0-9])"
)


def _square_ok(text: str, start: int, end: int) -> bool:
    """Is this [a-h][1-8] occurrence really a square reference and not part of a word?"""
    prev = text[start - 1] if start > 0 else ""
    nxt = text[end] if end < len(text) else ""

    if prev:
        if prev.isdigit():
            # A digit before a square is only legal as the rank of the FROM-square of a
            # UCI move: "e2e4" -> the "e4" match has prev='2', and text[start-2:start]
            # is itself the square "e2". Anything else ("12a3", "2026a1") is not a square.
            if not (start >= 2 and text[start - 2] in FILES and prev in RANKS
                    and _square_ok(text, start - 2, start)):
                return False
        elif prev.isalpha() and prev not in SAN_PREFIX:
            return False
    if nxt:
        if nxt.isdigit():
            return False                     # "a12"
        if nxt.isalpha():
            # allow a following square (UCI "e2e4") or a promotion piece
            if not (nxt in FILES and end + 1 < len(text) and text[end + 1] in RANKS):
                if nxt not in "QRBNqrbn":
                    return False
    return True


def squares_in(text: str) -> list[str]:
    """Every coordinate square the response names, in order of first appearance."""
    out: list[str] = []
    for m in _SQ.finditer(text):
        if _square_ok(text, m.start(), m.end()):
            s = m.group(0)
            if s not in out:
                out.append(s)
    return out


def moves_in(text: str) -> list[str]:
    """Every SAN- or UCI-looking move token, normalised (check/mate suffix stripped)."""
    out: list[str] = []
    for m in _UCI.finditer(text):
        tok = m.group(1).lower()
        if tok not in out:
            out.append(tok)
    for m in _SAN.finditer(text):
        tok = m.group(1)
        if tok in ("0-0", "0-0-0"):
            tok = tok.replace("0", "O")
        if tok not in out:
            out.append(tok)
    return out


# --------------------------------------------------------------------------
# detection scoring
# --------------------------------------------------------------------------

@dataclass
class Score:
    position_id: str
    hit_square: bool                 # PRIMARY metric
    hit_move: bool                   # STRICT metric
    critical_square: str
    critical_move_san: str
    squares_mentioned: list = field(default_factory=list)
    moves_mentioned: list = field(default_factory=list)
    n_squares_mentioned: int = 0
    n_moves_mentioned: int = 0
    chance_rate_estimate: float = 0.0   # naive k/64 — a sanity number, NOT the floor
    empty_response: bool = False


def _norm_move(tok: str) -> str:
    return tok.rstrip("+#").replace("0", "O") if "-" in tok else tok.rstrip("+#")


def score_detection(position: dict, response: str) -> Score:
    """position: one record from positions.jsonl. response: raw model text."""
    text = response or ""
    sqs = squares_in(text)
    mvs = moves_in(text)

    accept_sq = {s.lower() for s in position["accept_squares"]}
    accept_mv = {_norm_move(m) for m in position["accept_moves"]}
    accept_mv |= {m.lower() for m in accept_mv}

    seen_mv = {_norm_move(m) for m in mvs}
    seen_mv |= {m.lower() for m in seen_mv}

    return Score(
        position_id=position["id"],
        hit_square=bool(accept_sq & {s.lower() for s in sqs}),
        hit_move=bool(accept_mv & seen_mv),
        critical_square=position["critical_square"],
        critical_move_san=position["critical_move_san"],
        squares_mentioned=sqs,
        moves_mentioned=mvs,
        n_squares_mentioned=len(sqs),
        n_moves_mentioned=len(mvs),
        chance_rate_estimate=round(min(1.0, len(sqs) / 64.0), 4),
        empty_response=not text.strip(),
    )


# --------------------------------------------------------------------------
# board reconstruction scoring (C3)
# --------------------------------------------------------------------------

PIECE_WORDS = {
    "king": "k", "queen": "q", "rook": "r", "bishop": "b", "knight": "n", "pawn": "p",
}

_FEN_BOARD = re.compile(r"(?<![\w/])((?:[rnbqkpRNBQKP1-8]{1,8}/){7}[rnbqkpRNBQKP1-8]{1,8})(?![\w/])")
_LINE = re.compile(
    r"(?<![a-zA-Z0-9])([a-h][1-8])(?![a-zA-Z0-9])\s*[:\-–=]?\s*"
    r"(white|black|w|b)?\s*"
    r"(king|queen|rook|bishop|knight|pawn)",
    re.IGNORECASE,
)


@dataclass
class ReconScore:
    position_id: str
    parsed: bool
    parse_mode: str                  # fen | lines | none
    n_predicted: int
    n_true: int
    exact_board: bool
    placement_precision: float
    placement_recall: float
    placement_f1: float
    square_accuracy: float           # over all 64 squares, incl. correctly-empty
    critical_square_correct: bool    # the piece the whole experiment turns on
    critical_square_occupied_correct: bool  # right occupancy, maybe wrong piece


def parse_board_claim(text: str) -> tuple[dict, str]:
    """Return ({square_name: piece_symbol}, parse_mode)."""
    m = _FEN_BOARD.search(text or "")
    if m:
        try:
            b = chess.Board(m.group(1) + " w - - 0 1")
            return ({chess.square_name(s): p.symbol() for s, p in b.piece_map().items()}, "fen")
        except ValueError:
            pass
    got: dict[str, str] = {}
    for mm in _LINE.finditer(text or ""):
        sq, colour, piece = mm.group(1).lower(), (mm.group(2) or "").lower(), mm.group(3).lower()
        sym = PIECE_WORDS[piece]
        if colour.startswith("w"):
            sym = sym.upper()
        elif colour.startswith("b"):
            sym = sym.lower()
        else:
            continue                  # colour is not optional; an uncoloured claim is unscoreable
        got.setdefault(sq, sym)
    return (got, "lines" if got else "none")


def score_reconstruction(position: dict, response: str) -> ReconScore:
    true_board = chess.Board(position["fen"])
    truth = {chess.square_name(s): p.symbol() for s, p in true_board.piece_map().items()}
    pred, mode = parse_board_claim(response)

    tp = sum(1 for k, v in pred.items() if truth.get(k) == v)
    prec = tp / len(pred) if pred else 0.0
    rec = tp / len(truth) if truth else 0.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0

    correct_squares = 0
    for i in range(64):
        name = chess.square_name(i)
        if truth.get(name) == pred.get(name):
            correct_squares += 1

    cs = position["critical_square"]
    return ReconScore(
        position_id=position["id"],
        parsed=mode != "none",
        parse_mode=mode,
        n_predicted=len(pred),
        n_true=len(truth),
        exact_board=(pred == truth),
        placement_precision=round(prec, 4),
        placement_recall=round(rec, 4),
        placement_f1=round(f1, 4),
        square_accuracy=round(correct_squares / 64.0, 4),
        critical_square_correct=(pred.get(cs) == truth.get(cs)),
        critical_square_occupied_correct=((cs in pred) == (cs in truth)),
    )


__all__ = [
    "squares_in", "moves_in", "score_detection", "score_reconstruction",
    "parse_board_claim", "Score", "ReconScore",
]
