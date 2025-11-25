"""Lightweight AI helpers for the Go-like variant."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .engine import GameState, MoveResult


@dataclass
class ScoredMove:
    move: Tuple[int, int]
    captures: int
    liberties: int


class HeuristicAI:
    """Select moves using simple capture/liberty heuristic.

    This is intentionally lightweight for quick responses; it favors moves
    that capture and that leave the played group with healthy liberties.
    """

    def __init__(self, playouts: int = 30) -> None:
        self.playouts = playouts

    def choose_move(self, game: GameState) -> Optional[Tuple[int, int]]:
        candidates: List[ScoredMove] = []
        for x in range(game.size):
            for y in range(game.size):
                legal, _, captured = game.is_legal_move(x, y)
                if not legal:
                    continue
                # Rough liberty estimate via neighbors of the point.
                liberties = len({p for p in game.neighbors(x, y) if game.board[p[0]][p[1]] == "."})
                candidates.append(ScoredMove((x, y), captured, liberties))

        if not candidates:
            return None
        # Prefer max captures, then liberties; add randomness to break ties.
        max_capture = max(m.captures for m in candidates)
        top = [m for m in candidates if m.captures == max_capture]
        max_liberty = max(m.liberties for m in top)
        top = [m for m in top if m.liberties == max_liberty]
        return random.choice(top).move

    def play_move(self, game: GameState) -> MoveResult:
        move = self.choose_move(game)
        if move is None:
            game.pass_turn()
            return MoveResult(True, "AI passed", 0, game.board)
        x, y = move
        return game.play_move(x, y)
