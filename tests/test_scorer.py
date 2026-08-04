#!/usr/bin/env python3
"""Unit tests for the deterministic scorer, plus the scorer-reliability number.

Run:  .venv/bin/python -m pytest chess-salience/tests -q
  or: .venv/bin/python chess-salience/tests/test_scorer.py     (prints the reliability table)

The hand-labelled cases in hand_labelled.json were written by hand before the scorer was
tuned against them, and they are the source of the "scorer reliability" figure reported in
RESULTS.md. Agreement is exact-match on both metrics.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scorer import (  # noqa: E402
    squares_in, moves_in, score_detection, score_reconstruction, parse_board_claim,
)

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = json.load(open(os.path.join(HERE, "hand_labelled.json")))


# --- extraction primitives --------------------------------------------------

def test_squares_basic():
    assert squares_in("the knight on f3 is loose") == ["f3"]
    assert squares_in("Nxe5 wins a pawn") == ["e5"]
    assert squares_in("e2e4") == ["e2", "e4"]
    assert squares_in("e2-e4") == ["e2", "e4"]


def test_squares_reject_words_and_numbers():
    assert squares_in("Beta4 testing") == []
    assert squares_in("version 2a12") == []
    assert squares_in("about -1.5") == []


def test_squares_dedupe_preserves_order():
    assert squares_in("d4 then e5 then d4 again") == ["d4", "e5"]


def test_moves_san_and_uci():
    assert "Nxe5" in moves_in("I'd play Nxe5 here")
    assert "f3e5" in moves_in("best move: f3e5")
    assert "O-O" in moves_in("castle with O-O")


def test_moves_strip_check_suffix_on_match():
    pos = {"id": "x", "critical_square": "h7", "critical_move_san": "Qh7",
           "accept_squares": ["h7"], "accept_moves": ["Qh7", "d3h7"]}
    s = score_detection(pos, "Qh7# ends it")
    assert s.hit_move and s.hit_square


# --- hand-labelled cases ----------------------------------------------------

def test_hand_labelled_cases():
    for c in CASES:
        s = score_detection(c["position"], c["response"])
        assert s.hit_square == c["hit_square"], f"{c['position']['id']} hit_square: {c['note']}"
        assert s.hit_move == c["hit_move"], f"{c['position']['id']} hit_move: {c['note']}"
        if "min_squares_mentioned" in c:
            assert s.n_squares_mentioned >= c["min_squares_mentioned"], c["note"]


def test_empty_response_flagged():
    pos = CASES[10]["position"]
    s = score_detection(pos, "")
    assert s.empty_response and not s.hit_square and not s.hit_move


# --- reconstruction ---------------------------------------------------------

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def test_recon_from_fen_exact():
    pos = {"id": "r1", "fen": START_FEN, "critical_square": "e2"}
    r = score_reconstruction(pos, "The board is rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR")
    assert r.parsed and r.parse_mode == "fen"
    assert r.exact_board and r.placement_f1 == 1.0 and r.square_accuracy == 1.0
    assert r.critical_square_correct


def test_recon_from_lines():
    fen = "8/8/8/4k3/8/8/4P3/4K3 w - - 0 1"
    pos = {"id": "r2", "fen": fen, "critical_square": "e2"}
    txt = "e1: white king\ne2: white pawn\ne5: black king"
    r = score_reconstruction(pos, txt)
    assert r.parse_mode == "lines" and r.exact_board and r.critical_square_correct


def test_recon_partial_scores_between():
    fen = "8/8/8/4k3/8/8/4P3/4K3 w - - 0 1"
    pos = {"id": "r3", "fen": fen, "critical_square": "e2"}
    txt = "e1: white king\ne3: white pawn\ne5: black king"     # pawn on the wrong square
    r = score_reconstruction(pos, txt)
    assert not r.exact_board
    assert 0.0 < r.placement_f1 < 1.0
    assert not r.critical_square_correct
    assert not r.critical_square_occupied_correct


def test_recon_unparseable():
    pos = {"id": "r4", "fen": START_FEN, "critical_square": "e2"}
    r = score_reconstruction(pos, "I can't reliably reconstruct the board from this.")
    assert not r.parsed and r.parse_mode == "none" and r.n_predicted == 0
    assert not r.exact_board


def test_recon_uncoloured_claim_is_unscoreable_not_a_free_hit():
    pos = {"id": "r5", "fen": "8/8/8/8/8/8/4P3/4K3 w - - 0 1", "critical_square": "e2"}
    got, mode = parse_board_claim("e2: pawn\ne1: king")
    assert mode == "none" and got == {}


# --- reliability report -----------------------------------------------------

def reliability():
    agree_sq = agree_mv = 0
    rows = []
    for c in CASES:
        s = score_detection(c["position"], c["response"])
        ok_sq = s.hit_square == c["hit_square"]
        ok_mv = s.hit_move == c["hit_move"]
        agree_sq += ok_sq
        agree_mv += ok_mv
        rows.append((c["position"]["id"], ok_sq, ok_mv, c["note"]))
    n = len(CASES)
    print(f"hand-labelled cases: n={n}")
    print(f"  hit_square agreement: {agree_sq}/{n} = {agree_sq/n:.3f}")
    print(f"  hit_move   agreement: {agree_mv}/{n} = {agree_mv/n:.3f}")
    for pid, a, b, note in rows:
        if not (a and b):
            print(f"  DISAGREE {pid}  square={a} move={b}  {note}")
    return agree_sq, agree_mv, n


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL {name}: {e}")
    print()
    reliability()
    sys.exit(1 if failures else 0)
