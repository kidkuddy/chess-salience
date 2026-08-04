#!/usr/bin/env python3
"""Generate chess positions for the salience experiment.

Positions are GENERATED, never scraped. No Lichess puzzle DB, no tactics set, nothing
that could plausibly be in pretraining. Generation is a seeded random walk from the
start position; labelling is Stockfish.

Two motifs:
  hanging   — a piece can be won (or is about to be lost) for a material swing >= a
              threshold, and the engine's best move is unique by a margin so that
              a single square/move is an unambiguous scoring target.
  mate_in_1 — the side to move has a forced mate in one, and exactly one legal move
              delivers it.

Two threat directions, because "is anything hanging?" is asymmetric:
  opportunity   — the OPPONENT has a piece hanging; the side to move can take it.
  vulnerability — the SIDE TO MOVE has a piece hanging; the opponent takes it next.
                  Detected by flipping the side to move and re-analysing (a null move).

Every position is emitted in all three input formats (FEN, PGN, move-list) whether or
not format ends up being a factor in the design.

Usage:
  python gen_positions.py --n 240 --out data/positions.jsonl --seed 20260804
  python gen_positions.py --n 30  --out data/gate_positions.jsonl --seed 20260804 --gate
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
from dataclasses import dataclass, asdict, field
from typing import Optional

import chess
import chess.engine
import chess.pgn

STOCKFISH = os.environ.get("STOCKFISH_PATH", "/opt/homebrew/bin/stockfish")

# --- labelling thresholds ---------------------------------------------------
# A position only enters the pool if the engine's preferred continuation beats the
# next-best by MARGIN_CP. That is what makes the scoring target unique: there is one
# right square to name, not a family of reasonable ones.
MARGIN_CP = 150
# Minimum material swing for a "hanging piece" to count as hanging at all.
MIN_SWING_CP = 150
LABEL_DEPTH = 18        # depth for the authoritative label
PREFILTER_DEPTH = 10    # cheap pass that decides whether the label is worth computing
PREFILTER_MARGIN_CP = 100   # deliberately looser than MARGIN_CP so the prefilter cannot
                            # reject something the authoritative pass would have kept
WALK_DEPTH = 6          # depth for the guided random walk (cheap)
WALK_WINDOW_CP = 200    # sample uniformly among moves within this of best
BLUNDER_RATE = 0.30     # per-ply chance of a uniformly random legal move instead

SEVERITY_BANDS = [(MIN_SWING_CP, 300, "minor"), (300, 600, "major"), (600, 10**9, "decisive")]


def severity_band(cp: int) -> str:
    for lo, hi, name in SEVERITY_BANDS:
        if lo <= cp < hi:
            return name
    return "minor"


def phase_of(board: chess.Board) -> str:
    n = len(board.piece_map())
    if n >= 26:
        return "opening"
    if n >= 13:
        return "middlegame"
    return "endgame"


@dataclass
class Position:
    id: str
    fen: str
    pgn: str
    movelist: str
    side_to_move: str
    motif: str                 # hanging | mate_in_1
    threat_direction: str      # opportunity | vulnerability | mate (own mate is always opportunity)
    severity_cp: int
    severity_band: str
    phase: str
    piece_count: int
    ply: int
    critical_move_san: str
    critical_move_uci: str
    critical_square: str       # the square the answer must name
    critical_piece: str        # symbol of the piece on critical_square (or mated king square)
    margin_cp: int             # best minus second-best, the uniqueness guarantee
    legal_move_count: int
    accept_squares: list       # squares that count as naming the target (usually 1)
    accept_moves: list         # SAN/UCI strings that count as naming the move
    engine: str = ""
    label_depth: int = LABEL_DEPTH
    seed: int = 0
    walk_id: int = 0


# --- format emitters --------------------------------------------------------

def to_pgn(moves: list[chess.Move], walk_id: int) -> str:
    game = chess.pgn.Game()
    game.headers["Event"] = "generated"
    game.headers["Site"] = "chess-salience"
    game.headers["Round"] = str(walk_id)
    game.headers["White"] = "?"
    game.headers["Black"] = "?"
    game.headers["Result"] = "*"
    for h in ("Date",):
        game.headers.pop(h, None)
    node = game
    for m in moves:
        node = node.add_variation(m)
    exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
    return game.accept(exporter)


def to_movelist(moves: list[chess.Move]) -> str:
    """Plain SAN move list, no numbering, no headers — the third input format."""
    b = chess.Board()
    out = []
    for m in moves:
        out.append(b.san(m))
        b.push(m)
    return " ".join(out)


# --- engine helpers ---------------------------------------------------------

def cp_from_pov(score: chess.engine.PovScore, turn: bool) -> Optional[int]:
    s = score.pov(turn)
    if s.is_mate():
        m = s.mate()
        return 100000 - abs(m) * 100 if m > 0 else -(100000 - abs(m) * 100)
    return s.score()


def analyse_top2(engine, board, depth):
    infos = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=2)
    if isinstance(infos, dict):
        infos = [infos]
    return infos


def stackless(board: chess.Board) -> chess.Board:
    """A board with the same position and NO move history.

    python-chess sends a board with a move stack to the engine as
    `position fen <root> moves ...`, i.e. it replays the history rather than
    setting the position. Anything that edits board state directly (below) is
    then silently discarded — the engine analyses the pre-edit position. Every
    board handed to the engine for labelling goes through here.
    """
    return chess.Board(board.fen())


def null_moved(board: chess.Board) -> Optional[chess.Board]:
    """The position with the side to move passed — the vulnerability probe.

    Built from the FEN, not by mutating a copy, for the reason in stackless().
    Returns None when passing is not a legal thing to ask about.
    """
    piece_placement, turn, castling, _ep, _half, full = board.fen().split()
    flipped = "b" if turn == "w" else "w"
    probe = chess.Board(" ".join([piece_placement, flipped, castling, "-", "0", full]))
    if not probe.is_valid():        # the side that just passed was in check — illegal
        return None
    if probe.is_check():            # opponent is already in check; a different motif
        return None
    return probe


def stockfish_version(path: str) -> str:
    try:
        out = subprocess.run([path], input="uci\nquit\n", capture_output=True, text=True, timeout=10).stdout
        for line in out.splitlines():
            if line.startswith("id name"):
                return line[len("id name "):].strip()
    except Exception:
        pass
    return "unknown"


# --- the walk ---------------------------------------------------------------

def random_walk(engine, rng: random.Random, max_plies: int) -> list[tuple[chess.Board, list[chess.Move]]]:
    """Play a game with engine-guided moves punctuated by uniform-random blunders.

    Pure uniform-random play produces positions no human game reaches, which a reviewer
    will (rightly) attack as off-distribution. Pure engine play produces almost no
    hanging pieces. Mixing gives game-like positions where someone has just blundered —
    which is the target motif. Neither mode touches any external position database.
    """
    board = chess.Board()
    moves: list[chess.Move] = []
    snapshots = []
    for _ in range(max_plies):
        if board.is_game_over():
            break
        legal = list(board.legal_moves)
        if rng.random() < BLUNDER_RATE:
            mv = rng.choice(legal)
        else:
            infos = engine.analyse(stackless(board), chess.engine.Limit(depth=WALK_DEPTH), multipv=5)
            if isinstance(infos, dict):
                infos = [infos]
            best = cp_from_pov(infos[0]["score"], board.turn)
            pool = []
            for i in infos:
                c = cp_from_pov(i["score"], board.turn)
                if c is not None and best is not None and best - c <= WALK_WINDOW_CP:
                    pool.append(i["pv"][0])
            mv = rng.choice(pool) if pool else rng.choice(legal)
        board.push(mv)
        moves.append(mv)
        snapshots.append((board.copy(), list(moves)))
    return snapshots


# --- labelling --------------------------------------------------------------

def label_mate_in_1(board: chess.Board) -> Optional[dict]:
    maters = []
    for m in board.legal_moves:
        board.push(m)
        if board.is_checkmate():
            maters.append(m)
        board.pop()
    if len(maters) != 1:
        return None            # uniqueness: exactly one mating move, or it is not scoreable
    m = maters[0]
    san = board.san(m)
    return {
        "motif": "mate_in_1",
        "threat_direction": "opportunity",
        "severity_cp": 100000,
        "critical_move_san": san,
        "critical_move_uci": m.uci(),
        "critical_square": chess.square_name(m.to_square),
        "critical_piece": (board.piece_at(m.from_square).symbol() if board.piece_at(m.from_square) else "?"),
        "margin_cp": 100000,
        "accept_squares": [chess.square_name(m.to_square)],
        "accept_moves": sorted({san, san.rstrip("+#"), m.uci(),
                                chess.square_name(m.from_square) + chess.square_name(m.to_square)}),
    }


def label_hanging(engine, board: chess.Board, direction: str) -> Optional[dict]:
    """direction='opportunity': side to move can win material.
       direction='vulnerability': side to move is ABOUT to lose material (null-move probe)."""
    if direction == "vulnerability":
        probe = null_moved(board)
        if probe is None:
            return None
    else:
        probe = stackless(board)

    if probe.is_game_over():
        return None

    # cheap structural prefilter: depth-18 multipv on every snapshot is ~8s and most
    # snapshots are not scoreable. A shallow pass rejects those for ~50ms. The
    # authoritative label is still the depth-LABEL_DEPTH analysis below; this only
    # decides what is worth spending it on.
    quick = analyse_top2(engine, probe, PREFILTER_DEPTH)
    if len(quick) < 2:
        return None
    q_best = cp_from_pov(quick[0]["score"], probe.turn)
    q_second = cp_from_pov(quick[1]["score"], probe.turn)
    if q_best is None or q_second is None:
        return None
    if not probe.is_capture(quick[0]["pv"][0]):
        return None
    if q_best - q_second < PREFILTER_MARGIN_CP:
        return None

    infos = analyse_top2(engine, probe, LABEL_DEPTH)
    if len(infos) < 2:
        return None
    best_cp = cp_from_pov(infos[0]["score"], probe.turn)
    second_cp = cp_from_pov(infos[1]["score"], probe.turn)
    if best_cp is None or second_cp is None:
        return None
    # A mate score on EITHER side of the margin makes this a mate position wearing a
    # hanging-piece costume. If the second-best move loses to mate, margin is ~99000 and
    # severity_cp — which is what the severity stratum is cut on — stops describing how
    # much material is hanging and starts describing how fast the alternative loses.
    if abs(best_cp) >= 90000 or abs(second_cp) >= 90000:
        return None
    margin = best_cp - second_cp
    if margin < MARGIN_CP:
        return None            # not unique enough to score on one square
    mv = infos[0]["pv"][0]
    if not probe.is_capture(mv):
        return None            # the point has to be that something is hanging
    victim = probe.piece_at(mv.to_square)
    if victim is None:         # en passant
        return None
    swing = margin
    if swing < MIN_SWING_CP:
        return None
    san = probe.san(mv)
    sq = chess.square_name(mv.to_square)
    return {
        "motif": "hanging",
        "threat_direction": direction,
        "severity_cp": int(swing),
        "critical_move_san": san,
        "critical_move_uci": mv.uci(),
        "critical_square": sq,
        "critical_piece": victim.symbol(),
        "margin_cp": int(margin),
        "accept_squares": [sq],
        "accept_moves": sorted({san, san.rstrip("+#"), mv.uci(),
                                chess.square_name(mv.from_square) + chess.square_name(mv.to_square)}),
    }


def label(engine, board: chess.Board) -> Optional[dict]:
    if board.is_game_over():
        return None
    lab = label_mate_in_1(board)
    if lab:
        return lab
    for direction in ("opportunity", "vulnerability"):
        lab = label_hanging(engine, board, direction)
        if lab:
            return lab
    return None


# --- stratified collection --------------------------------------------------

def stratum_key(p: Position) -> tuple:
    return (p.motif, p.threat_direction, p.severity_band, p.phase, p.side_to_move)


def generate(n: int, seed: int, max_per_stratum: int, verbose: bool = True) -> list[Position]:
    rng = random.Random(seed)
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH)
    engine.configure({"Threads": 4, "Hash": 256})
    version = stockfish_version(STOCKFISH)
    out: list[Position] = []
    seen_fen: set[str] = set()
    strata: dict[tuple, int] = {}
    walk_id = 0
    try:
        while len(out) < n:
            walk_id += 1
            plies = rng.randint(8, 70)
            snaps = random_walk(engine, rng, plies)
            # look at a random sample of snapshots from this walk, not all of them,
            # so one game cannot dominate the pool
            rng.shuffle(snaps)
            for board, moves in snaps[:6]:
                if len(out) >= n:
                    break
                key_fen = board.board_fen() + " " + ("w" if board.turn else "b")
                if key_fen in seen_fen:
                    continue
                lab = label(engine, board)
                if lab is None:
                    continue
                pos = Position(
                    id=f"p{len(out):04d}",
                    fen=board.fen(),
                    pgn=to_pgn(moves, walk_id),
                    movelist=to_movelist(moves),
                    side_to_move=("white" if board.turn == chess.WHITE else "black"),
                    severity_band=severity_band(lab["severity_cp"]),
                    phase=phase_of(board),
                    piece_count=len(board.piece_map()),
                    ply=len(moves),
                    legal_move_count=board.legal_moves.count(),
                    engine=version,
                    seed=seed,
                    walk_id=walk_id,
                    **{k: lab[k] for k in (
                        "motif", "threat_direction", "severity_cp", "critical_move_san",
                        "critical_move_uci", "critical_square", "critical_piece",
                        "margin_cp", "accept_squares", "accept_moves")},
                )
                sk = stratum_key(pos)
                if strata.get(sk, 0) >= max_per_stratum:
                    continue
                strata[sk] = strata.get(sk, 0) + 1
                seen_fen.add(key_fen)
                out.append(pos)
                if verbose:
                    print(f"[{len(out):3d}/{n}] {pos.motif:9s} {pos.threat_direction:13s} "
                          f"{pos.severity_band:8s} {pos.phase:11s} {pos.critical_square} "
                          f"({pos.severity_cp}cp)", file=sys.stderr)
    finally:
        engine.quit()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=240)
    ap.add_argument("--out", default="data/positions.jsonl")
    ap.add_argument("--seed", type=int, default=20260804)
    ap.add_argument("--max-per-stratum", type=int, default=8)
    args = ap.parse_args()

    if not os.path.exists(STOCKFISH):
        sys.exit(f"stockfish not found at {STOCKFISH}; set STOCKFISH_PATH")

    positions = generate(args.n, args.seed, args.max_per_stratum)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        for p in positions:
            f.write(json.dumps(asdict(p)) + "\n")

    # stratum report to stderr so the caller can see the balance
    from collections import Counter
    for dim in ("motif", "threat_direction", "severity_band", "phase", "side_to_move"):
        c = Counter(getattr(p, dim) for p in positions)
        print(f"{dim:18s} {dict(c)}", file=sys.stderr)
    print(f"wrote {len(positions)} -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
